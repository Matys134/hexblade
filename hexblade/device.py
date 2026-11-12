"""Low-level access to the Hexblade configuration interface via Linux hidraw.

The keyboard (SONiX, USB 0c45:8006) exposes its configuration channel on
USB interface 0 as a 64-byte HID *feature* report without a report ID.
"""

from __future__ import annotations

import fcntl
import glob
import os
import time
from dataclasses import dataclass

VENDOR_ID = 0x0C45
PRODUCT_ID = 0x8006
REPORT_SIZE = 64
COMMAND_DELAY = 0.015  # seconds, same as the vendor tool (CommandDelayTime=15)
RETRIES = 5


def _ioc(direction: int, type_: int, nr: int, size: int) -> int:
    return (direction << 30) | (size << 16) | (type_ << 8) | nr


_HIDIOCSFEATURE = _ioc(3, ord("H"), 0x06, REPORT_SIZE + 1)
_HIDIOCGFEATURE = _ioc(3, ord("H"), 0x07, REPORT_SIZE + 1)


class DeviceError(RuntimeError):
    pass


class DeviceNotFound(DeviceError):
    pass


@dataclass
class DeviceInfo:
    path: str
    interface: int
    name: str


def find_devices() -> list[DeviceInfo]:
    """Return the configuration hidraw node(s) of every connected Hexblade."""
    found: list[DeviceInfo] = []
    for node in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        try:
            with open(os.path.join(node, "device", "uevent")) as f:
                uevent = dict(
                    line.split("=", 1) for line in f.read().splitlines() if "=" in line
                )
        except OSError:
            continue
        hid_id = uevent.get("HID_ID", "")
        try:
            _bus, vid, pid = (int(x, 16) for x in hid_id.split(":"))
        except ValueError:
            continue
        if (vid, pid) != (VENDOR_ID, PRODUCT_ID):
            continue
        # .../<usb-dev>:<config>.<interface>/<hid-dev>
        real = os.path.realpath(os.path.join(node, "device"))
        usb_if = os.path.basename(os.path.dirname(real))
        try:
            interface = int(usb_if.rsplit(".", 1)[1])
        except (IndexError, ValueError):
            interface = -1
        if interface != 0:
            continue
        found.append(
            DeviceInfo(
                path="/dev/" + os.path.basename(node),
                interface=interface,
                name=uevent.get("HID_NAME", "SONiX USB DEVICE"),
            )
        )
    return found


class Device:
    """An open handle to the keyboard's configuration interface."""

    def __init__(self, path: str | None = None):
        if path is None:
            devices = find_devices()
            if not devices:
                raise DeviceNotFound(
                    "Klávesnice CZC.Gaming Hexblade (0c45:8006) nebyla nalezena."
                )
            path = devices[0].path
        self.path = path
        try:
            self._fd = os.open(path, os.O_RDWR)
        except PermissionError as exc:
            raise DeviceError(
                f"Nemám přístup k {path}. Nainstaluj udev pravidlo "
                "(udev/70-hexblade.rules) a klávesnici odpoj a znovu připoj."
            ) from exc

    # -- context manager -------------------------------------------------
    def close(self) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None

    def __enter__(self) -> "Device":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- raw feature reports ---------------------------------------------
    def send(self, data: bytes) -> None:
        if len(data) > REPORT_SIZE:
            raise ValueError("report too long")
        buf = bytearray(REPORT_SIZE + 1)  # [0] = report id 0
        buf[1 : 1 + len(data)] = data
        fcntl.ioctl(self._fd, _HIDIOCSFEATURE, bytes(buf))

    def receive(self) -> bytes:
        buf = fcntl.ioctl(self._fd, _HIDIOCGFEATURE, bytes(REPORT_SIZE + 1))
        return bytes(buf[1:])

    def command(self, data: bytes) -> bytes:
        """Send a command and return the device's reply (byte 3 == 1 → ACK)."""
        self.send(data)
        time.sleep(COMMAND_DELAY)
        return self.receive()

    # -- block transfer ----------------------------------------------------
    def write_block(self, cmd: int, payload: bytes, progress=None) -> None:
        """Write a configuration block (lighting / keymap / macros).

        Protocol (reverse engineered from GamingKeyboardWriter.dll):
          1. ``04 <cmd> 00 00 00 00 00 00 <packets:u16le>`` → wait for ACK
          2. ``packets`` × 64 bytes of raw payload
          3. ``04 02`` → reply carries ACK and the u32le byte sum the device
             received, which must equal the sum of the payload.
        """
        packets = (len(payload) + REPORT_SIZE - 1) // REPORT_SIZE
        payload = payload + bytes(packets * REPORT_SIZE - len(payload))
        header = bytes([0x04, cmd, 0, 0, 0, 0, 0, 0, packets & 0xFF, packets >> 8])

        for _ in range(RETRIES):
            reply = self.command(header)
            if reply[3] == 1:
                break
        else:
            raise DeviceError(f"Klávesnice nepotvrdila příkaz 04 {cmd:02x}.")

        for i in range(packets):
            self.send(payload[i * REPORT_SIZE : (i + 1) * REPORT_SIZE])
            time.sleep(COMMAND_DELAY)
            if progress:
                progress(i + 1, packets)

        reply = self.command(bytes([0x04, 0x02]))
        device_sum = int.from_bytes(reply[4:8], "little")
        if reply[3] != 1 or device_sum != sum(payload):
            raise DeviceError(
                "Kontrolní součet nesouhlasí "
                f"(klávesnice {device_sum}, odesláno {sum(payload)})."
            )
