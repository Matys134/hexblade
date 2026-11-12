"""Qt (PySide6) GUI for the CZC.Gaming Hexblade."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import sys
import threading
import time

from PySide6.QtCore import QObject, QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (QAction, QColor, QFont, QIcon, QKeySequence, QPainter,
                           QPainterPath, QPalette, QPen, QPixmap)
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QColorDialog,
                               QComboBox, QFileDialog, QFrame, QGridLayout,
                               QHBoxLayout, QInputDialog, QLabel, QListWidget,
                               QListWidgetItem, QMainWindow, QMessageBox,
                               QPushButton, QSizePolicy, QSlider, QStackedWidget,
                               QStatusBar, QTabWidget, QToolButton, QVBoxLayout,
                               QWidget)

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDoubleSpinBox

from . import __version__
from . import profile as prof
from . import scripting
from .device import Device, DeviceError, find_devices
from .layout import HEIGHT_UNITS, KEYS, KEYS_BY_ID, NON_REMAPPABLE, WIDTH_UNITS
from .protocol import (BRIGHTNESS_MAX, CMD_KEYMAP, CMD_LIGHTING, DIRECTIONS,
                       KEY_USAGES, MEDIA_USAGES, MOD_LABELS, MODE_LABELS, MODES,
                       MOUSE_ACTIONS, SPEED_MAX, describe_action, encode_keymap,
                       encode_lighting)

ACCENT = QColor("#ff6a3d")
BG = QColor("#16181d")
PANEL = QColor("#1e2128")
CAP = QColor("#2a2e37")

PRESET_COLORS = ["#ff0000", "#ff6a00", "#ffd000", "#00ff40", "#00ffd5", "#0090ff",
                 "#2a00ff", "#b000ff", "#ff00a0", "#ffffff"]

# Modes where the preview animates as a moving rainbow / wave
_WAVE_MODES = {"scrolling", "rolling", "flowing", "tilt", "shuttle", "rotating",
               "outward", "falling"}
# Modes that react to key presses (preview simulates typing)
_REACTIVE_MODES = {"single_on", "single_off", "ripples", "explode", "launch"}


def _keymap_hash(keymap: dict) -> str:
    return hashlib.sha1(encode_keymap(keymap)).hexdigest()


# ---------------------------------------------------------------------------
# Background writer
# ---------------------------------------------------------------------------

class Writer(QObject):
    """Serialises writes to the keyboard on a worker thread."""

    finished = Signal(bool, str)
    progress = Signal(str)

    def __init__(self):
        super().__init__()
        self._lock = threading.Lock()
        self._pending: tuple[dict, dict | None] | None = None
        self._event = threading.Event()
        threading.Thread(target=self._run, daemon=True).start()

    def submit(self, lighting: dict, keymap: dict | None) -> None:
        with self._lock:
            if self._pending and self._pending[1] is not None and keymap is None:
                keymap = self._pending[1]  # never drop a queued keymap write
            self._pending = (copy.deepcopy(lighting), copy.deepcopy(keymap))
        self._event.set()

    def _run(self):
        while True:
            self._event.wait()
            with self._lock:
                job, self._pending = self._pending, None
                self._event.clear()
            if job is None:
                continue
            lighting, keymap = job
            try:
                with Device() as dev:
                    self.progress.emit("Nahrávám podsvícení…")
                    dev.write_block(CMD_LIGHTING, encode_lighting(lighting))
                    if keymap is not None:
                        self.progress.emit("Nahrávám mapování kláves…")
                        dev.write_block(CMD_KEYMAP, encode_keymap(keymap))
                msg = "Uloženo do klávesnice" + (" (včetně mapování kláves)" if keymap is not None else "")
                self.finished.emit(True, msg)
            except (DeviceError, OSError) as exc:
                self.finished.emit(False, str(exc))


# ---------------------------------------------------------------------------
# Keyboard canvas
# ---------------------------------------------------------------------------

class KeyboardView(QWidget):
    keyClicked = Signal(str, object)  # key id, Qt.KeyboardModifiers
    keyDragged = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setMinimumSize(760, 250)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.colors: dict[str, QColor] = {}
        self.selected: set[str] = set()
        self.badges: dict[str, str] = {}
        self.legend = "cz"
        self.dim_keys: set[str] = set()
        self._hover: str | None = None
        self._dragging = False
        self._rects: dict[str, QRectF] = {}

    def sizeHint(self):
        return QSize(1100, 330)

    def _layout(self):
        margin = 14
        unit = min((self.width() - 2 * margin) / WIDTH_UNITS,
                   (self.height() - 2 * margin) / HEIGHT_UNITS)
        ox = (self.width() - unit * WIDTH_UNITS) / 2
        oy = (self.height() - unit * HEIGHT_UNITS) / 2
        gap = max(2.0, unit * 0.07)
        self._unit = unit
        self._rects = {
            k.id: QRectF(ox + k.x * unit + gap / 2, oy + k.y * unit + gap / 2,
                         k.w * unit - gap, k.h * unit - gap)
            for k in KEYS
        }

    def resizeEvent(self, e):
        self._layout()
        super().resizeEvent(e)

    def key_at(self, pos) -> str | None:
        for kid, r in self._rects.items():
            if r.contains(pos):
                return kid
        return None

    def paintEvent(self, e):
        if not self._rects:
            self._layout()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        # keyboard body
        body = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        p.setPen(QPen(QColor("#2c3039"), 1))
        p.setBrush(QColor("#101216"))
        p.drawRoundedRect(body, 14, 14)

        font = QFont(self.font())
        radius = self._unit * 0.12
        for k in KEYS:
            r = self._rects[k.id]
            led = self.colors.get(k.id, QColor(0, 0, 0))
            dim = k.id in self.dim_keys
            intensity = max(led.redF(), led.greenF(), led.blueF())
            # glow under the cap
            if intensity > 0.02 and not dim:
                glow = QColor(led)
                glow.setAlphaF(0.35)
                p.setPen(Qt.NoPen)
                p.setBrush(glow)
                p.drawRoundedRect(r.adjusted(-2, -2, 2, 2), radius + 2, radius + 2)
            # cap
            cap = QColor(CAP)
            if dim:
                cap = QColor("#1c1f25")
            p.setBrush(cap)
            border = QColor(led) if intensity > 0.02 and not dim else QColor("#3a3f4a")
            if k.id == self._hover:
                border = border.lighter(160) if intensity > 0.02 else QColor("#6b7280")
            p.setPen(QPen(border, 1.4))
            p.drawRoundedRect(r, radius, radius)
            # inner face tinted by the LED
            face = r.adjusted(r.width() * 0.08, r.height() * 0.06,
                              -r.width() * 0.08, -r.height() * 0.16)
            tint = QColor(led)
            tint.setAlphaF(0.0 if dim else 0.22 * intensity + 0.05)
            p.setPen(Qt.NoPen)
            p.setBrush(tint)
            p.drawRoundedRect(face, radius * 0.8, radius * 0.8)
            # legend
            label = k.cz if self.legend == "cz" else k.us
            if label:
                # always light legends, only tinted by the LED hue, so they stay
                # readable on dark colours too
                txt = QColor("#555b66") if dim else QColor("#eef0f4")
                if not dim and intensity > 0.02 and led.hsvSaturationF() > 0.15 and led.hsvHueF() >= 0:
                    txt = QColor.fromHsvF(led.hsvHueF(), 0.28, 1.0)
                font.setPixelSize(max(9, int(self._unit * (0.28 if len(label) <= 2 else 0.22))))
                font.setBold(True)
                p.setFont(font)
                p.setPen(txt)
                p.drawText(face, Qt.AlignCenter, label)
            # badge (remapped)
            if k.id in self.badges:
                p.setPen(Qt.NoPen)
                p.setBrush(ACCENT)
                d = max(6.0, self._unit * 0.16)
                p.drawEllipse(QRectF(r.right() - d - 3, r.top() + 3, d, d))
            # selection
            if k.id in self.selected:
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(QColor("#ffffff"), 2.2))
                p.drawRoundedRect(r.adjusted(-1, -1, 1, 1), radius, radius)
        p.end()

    def mousePressEvent(self, e):
        kid = self.key_at(e.position())
        if kid and e.button() == Qt.LeftButton:
            self._dragging = True
            self.keyClicked.emit(kid, e.modifiers())

    def mouseMoveEvent(self, e):
        kid = self.key_at(e.position())
        if kid != self._hover:
            self._hover = kid
            if kid:
                k = KEYS_BY_ID[kid]
                tip = f"{k.cz if self.legend == 'cz' else k.us or 'Mezerník'}  ({k.id})"
                if kid in self.badges:
                    tip += f"\n→ {self.badges[kid]}"
                self.setToolTip(tip)
            else:
                self.setToolTip("")
            self.update()
        if self._dragging and kid and e.buttons() & Qt.LeftButton:
            self.keyDragged.emit(kid)

    def mouseReleaseEvent(self, e):
        self._dragging = False

    def leaveEvent(self, e):
        self._hover = None
        self.update()


# ---------------------------------------------------------------------------
# Small widgets
# ---------------------------------------------------------------------------

class ColorButton(QPushButton):
    colorChanged = Signal(str)

    def __init__(self, color="#ff0000", parent=None):
        super().__init__(parent)
        self.setFixedSize(46, 30)
        self.setCursor(Qt.PointingHandCursor)
        self._color = color
        self.clicked.connect(self._pick)
        self._refresh()

    def color(self) -> str:
        return self._color

    def setColor(self, color: str, emit=False):
        self._color = color
        self._refresh()
        if emit:
            self.colorChanged.emit(color)

    def _refresh(self):
        self.setStyleSheet(
            f"QPushButton {{ background: {self._color}; border: 2px solid #3a3f4a;"
            f" border-radius: 6px; }} QPushButton:hover {{ border-color: #9aa3b2; }}")

    def _pick(self):
        c = QColorDialog.getColor(QColor(self._color), self, "Vyber barvu")
        if c.isValid():
            self.setColor(c.name(), emit=True)


class Swatches(QWidget):
    picked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("plain")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(5)
        for c in PRESET_COLORS:
            b = QToolButton()
            b.setFixedSize(22, 22)
            b.setCursor(Qt.PointingHandCursor)
            b.setToolTip(c)
            b.setStyleSheet(f"QToolButton {{ background: {c}; border: 1px solid #3a3f4a;"
                            f" border-radius: 11px; }} QToolButton:hover {{ border: 2px solid white; }}")
            b.clicked.connect(lambda _=False, c=c: self.picked.emit(c))
            lay.addWidget(b)
        lay.addStretch(1)


def labeled_slider(minimum, maximum, left="", right=""):
    s = QSlider(Qt.Horizontal)
    s.setRange(minimum, maximum)
    s.setPageStep(1)
    s.setTickPosition(QSlider.TicksBelow)
    s.setTickInterval(1)
    value = QLabel()
    value.setMinimumWidth(26)
    value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    s.valueChanged.connect(lambda v: value.setText(str(v)))
    row = QHBoxLayout()
    if left:
        l = QLabel(left)
        l.setObjectName("hint")
        row.addWidget(l)
    row.addWidget(s, 1)
    if right:
        r = QLabel(right)
        r.setObjectName("hint")
        row.addWidget(r)
    row.addWidget(value)
    return s, row


def section(title: str) -> QLabel:
    l = QLabel(title.upper())
    l.setObjectName("section")
    return l


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hexblade")
        self.resize(1180, 760)
        self.state = prof.load_state()
        self.profile = self._initial_profile()
        self._loading = False
        self._t0 = time.monotonic()
        self.writer = Writer()
        self.writer.finished.connect(self._write_done)
        self.writer.progress.connect(lambda m: self.status.showMessage(m))

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(18, 14, 18, 10)
        root.setSpacing(12)

        root.addLayout(self._build_header())
        self.kb = KeyboardView()
        self.kb.keyClicked.connect(self._key_clicked)
        self.kb.keyDragged.connect(self._key_dragged)
        root.addWidget(self.kb, 5)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_lighting_tab(), "Podsvícení")
        self.tabs.addTab(self._build_custom_tab(), "Vlastní barvy")
        self.tabs.addTab(self._build_keymap_tab(), "Mapování kláves")
        self.tabs.addTab(self._build_scripts_tab(), "Skripty")
        self.tabs.currentChanged.connect(self._tab_changed)
        root.addWidget(self.tabs, 4)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.device_label = QLabel()
        self.status.addPermanentWidget(self.device_label)

        self._autosave_timer = QTimer(self, singleShot=True, interval=400)
        self._autosave_timer.timeout.connect(self._autosave)
        self._autoapply_timer = QTimer(self, singleShot=True, interval=350)
        self._autoapply_timer.timeout.connect(lambda: self.apply(include_keymap=False))
        self._anim = QTimer(self, interval=33)
        self._anim.timeout.connect(self._update_preview)
        self._anim.start()
        self._dev_timer = QTimer(self, interval=2000)
        self._dev_timer.timeout.connect(self._check_device)
        self._dev_timer.start()
        self._check_device()

        save = QAction(self)
        save.setShortcut(QKeySequence("Ctrl+S"))
        save.triggered.connect(lambda: self.apply())
        self.addAction(save)

        self._reload_profile_list()
        self._load_into_ui()

    # -- profile management ------------------------------------------------
    def _initial_profile(self) -> dict:
        names = prof.list_profiles()
        if not names:
            p = prof.default_profile()
            prof.save_profile(p)
            names = [p["name"]]
        name = self.state.get("profile")
        if name not in names:
            name = names[0]
        p = prof.load_profile(name)
        if "keymap_hash" not in self.state:
            # Assume the keyboard already holds this profile's keymap so that
            # nothing is overwritten until the user edits a key.
            self.state["keymap_hash"] = _keymap_hash(p["keymap"])
        self.state["profile"] = p["name"]
        prof.save_state(self.state)
        return p

    def _reload_profile_list(self):
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        names = prof.list_profiles()
        self.profile_combo.addItems(names)
        self.profile_combo.setCurrentText(self.profile["name"])
        self.profile_combo.blockSignals(False)
        self.btn_delete.setEnabled(len(names) > 1)

    def _switch_profile(self, name: str):
        if not name or name == self.profile["name"]:
            return
        self._autosave()
        self.profile = prof.load_profile(name)
        self.state["profile"] = name
        prof.save_state(self.state)
        self._load_into_ui()
        if self.auto_apply.isChecked():
            self.apply()

    def _new_profile(self, duplicate=False):
        title = "Duplikovat profil" if duplicate else "Nový profil"
        name, ok = QInputDialog.getText(self, title, "Název profilu:")
        name = name.strip()
        if not ok or not name:
            return
        if name in prof.list_profiles():
            QMessageBox.warning(self, title, "Profil s tímto názvem už existuje.")
            return
        self._autosave()
        p = copy.deepcopy(self.profile) if duplicate else prof.default_profile(name)
        p["name"] = name
        if not duplicate:
            p["keymap"] = copy.deepcopy(self.profile["keymap"])
        prof.save_profile(p)
        self.profile = p
        self.state["profile"] = name
        prof.save_state(self.state)
        self._reload_profile_list()
        self._load_into_ui()

    def _rename_profile(self):
        old = self.profile["name"]
        name, ok = QInputDialog.getText(self, "Přejmenovat profil", "Nový název:", text=old)
        name = name.strip()
        if not ok or not name or name == old:
            return
        if name in prof.list_profiles():
            QMessageBox.warning(self, "Přejmenovat profil", "Profil s tímto názvem už existuje.")
            return
        prof.delete_profile(old)
        self.profile["name"] = name
        prof.save_profile(self.profile)
        self.state["profile"] = name
        prof.save_state(self.state)
        self._reload_profile_list()

    def _delete_profile(self):
        name = self.profile["name"]
        if QMessageBox.question(self, "Smazat profil", f"Opravdu smazat profil „{name}“?") \
                != QMessageBox.Yes:
            return
        prof.delete_profile(name)
        names = prof.list_profiles()
        self.profile = prof.load_profile(names[0])
        self.state["profile"] = self.profile["name"]
        prof.save_state(self.state)
        self._reload_profile_list()
        self._load_into_ui()

    def _export_profile(self):
        path, _ = QFileDialog.getSaveFileName(self, "Exportovat profil",
                                              f"{self.profile['name']}.json", "Profil (*.json)")
        if path:
            with open(path, "w") as f:
                json.dump(self.profile, f, ensure_ascii=False, indent=2)
            self.status.showMessage(f"Exportováno do {path}", 4000)

    def _import_profile(self):
        path, _ = QFileDialog.getOpenFileName(self, "Importovat profil", "", "Profil (*.json)")
        if not path:
            return
        try:
            p = prof.load_profile(path)
        except (OSError, ValueError, KeyError) as exc:
            QMessageBox.warning(self, "Import", f"Soubor nelze načíst: {exc}")
            return
        base, n = p["name"], 2
        while p["name"] in prof.list_profiles():
            p["name"] = f"{base} ({n})"
            n += 1
        prof.save_profile(p)
        self.profile = p
        self.state["profile"] = p["name"]
        prof.save_state(self.state)
        self._reload_profile_list()
        self._load_into_ui()

    def _changed(self, lighting=True):
        if self._loading:
            return
        self._autosave_timer.start()
        if lighting and self.auto_apply.isChecked():
            self._autoapply_timer.start()
        self._refresh_keymap_badges()

    def _autosave(self):
        prof.save_profile(self.profile)

    # -- header ----------------------------------------------------------
    def _build_header(self):
        row = QHBoxLayout()
        title = QLabel("HEXBLADE")
        title.setObjectName("title")
        row.addWidget(title)
        sub = QLabel("CZC.Gaming")
        sub.setObjectName("subtitle")
        row.addWidget(sub)
        row.addSpacing(24)

        row.addWidget(QLabel("Profil"))
        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(180)
        self.profile_combo.currentTextChanged.connect(self._switch_profile)
        row.addWidget(self.profile_combo)

        menu_btn = QToolButton()
        menu_btn.setText("⋯")
        menu_btn.setPopupMode(QToolButton.InstantPopup)
        menu_btn.setToolTip("Správa profilů")
        from PySide6.QtWidgets import QMenu
        m = QMenu(menu_btn)
        m.addAction("Nový profil…", self._new_profile)
        m.addAction("Duplikovat…", lambda: self._new_profile(duplicate=True))
        m.addAction("Přejmenovat…", self._rename_profile)
        m.addSeparator()
        m.addAction("Importovat…", self._import_profile)
        m.addAction("Exportovat…", self._export_profile)
        m.addSeparator()
        self.btn_delete = m.addAction("Smazat profil", self._delete_profile)
        menu_btn.setMenu(m)
        row.addWidget(menu_btn)

        row.addStretch(1)
        self.legend_combo = QComboBox()
        self.legend_combo.addItems(["Popisky CZ", "Popisky US"])
        self.legend_combo.setCurrentIndex(0 if self.state.get("legend", "cz") == "cz" else 1)
        self.legend_combo.currentIndexChanged.connect(self._legend_changed)
        row.addWidget(self.legend_combo)

        self.auto_apply = QCheckBox("Měnit živě")
        self.auto_apply.setToolTip("Změny podsvícení se hned posílají do klávesnice")
        self.auto_apply.setChecked(self.state.get("auto_apply", True))
        self.auto_apply.toggled.connect(self._auto_apply_toggled)
        row.addWidget(self.auto_apply)

        self.apply_btn = QPushButton("Nahrát do klávesnice")
        self.apply_btn.setObjectName("primary")
        self.apply_btn.setToolTip("Ctrl+S")
        self.apply_btn.clicked.connect(lambda: self.apply())
        row.addWidget(self.apply_btn)
        return row

    def _legend_changed(self, i):
        self.kb.legend = "cz" if i == 0 else "us"
        self.state["legend"] = self.kb.legend
        prof.save_state(self.state)
        self.kb.update()

    def _auto_apply_toggled(self, on):
        self.state["auto_apply"] = on
        prof.save_state(self.state)

    # -- lighting tab ----------------------------------------------------
    def _build_lighting_tab(self):
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(20)

        self.mode_list = QListWidget()
        self.mode_list.setFixedWidth(230)
        for num, mid, label in MODES:
            it = QListWidgetItem(f"{label}")
            it.setData(Qt.UserRole, mid)
            self.mode_list.addItem(it)
        for mid, label in (("custom", "Vlastní barvy kláves"), ("off", "Vypnuto")):
            it = QListWidgetItem(label)
            it.setData(Qt.UserRole, mid)
            self.mode_list.addItem(it)
        self.mode_list.currentItemChanged.connect(self._mode_selected)
        lay.addWidget(self.mode_list)

        self.mode_stack = QStackedWidget()
        # page 0: effect settings
        page = QWidget()
        g = QGridLayout(page)
        g.setContentsMargins(0, 0, 0, 0)
        g.setHorizontalSpacing(16)
        g.setVerticalSpacing(10)
        self.mode_title = QLabel()
        self.mode_title.setObjectName("modeTitle")
        g.addWidget(self.mode_title, 0, 0, 1, 2)

        g.addWidget(section("Barva"), 1, 0, 1, 2)
        crow = QHBoxLayout()
        self.color_btn = ColorButton()
        self.color_btn.colorChanged.connect(self._mode_color)
        crow.addWidget(self.color_btn)
        sw = Swatches()
        sw.picked.connect(lambda c: (self.color_btn.setColor(c), self._mode_color(c)))
        crow.addWidget(sw, 1)
        g.addLayout(crow, 2, 0, 1, 2)
        self.rainbow = QCheckBox("Duhové barvy (místo jedné barvy)")
        self.rainbow.toggled.connect(lambda v: self._mode_set("rainbow", v))
        g.addWidget(self.rainbow, 3, 0)
        self.bg_host = QWidget()
        self.bg_host.setObjectName("plain")
        bgrow = QHBoxLayout(self.bg_host)
        bgrow.setContentsMargins(0, 0, 0, 0)
        self.bg_check = QCheckBox("Barva pozadí mezi stisky")
        self.bg_check.setToolTip("Klávesnice nebude mezi stisky zhasnutá, ale bude svítit touto barvou")
        self.bg_btn = ColorButton("#0020a0")
        self.bg_check.toggled.connect(lambda _: self._bg_changed())
        self.bg_btn.colorChanged.connect(lambda _: (self.bg_check.setChecked(True), self._bg_changed()))
        bgrow.addWidget(self.bg_check)
        bgrow.addWidget(self.bg_btn)
        bgrow.addStretch(1)
        g.addWidget(self.bg_host, 3, 1)

        g.addWidget(section("Jas"), 4, 0)
        self.bright, brow = labeled_slider(1, BRIGHTNESS_MAX, "☾", "☀")
        self.bright.valueChanged.connect(lambda v: self._mode_set("brightness", v))
        g.addLayout(brow, 5, 0)
        g.addWidget(section("Rychlost"), 4, 1)
        self.speed, srow = labeled_slider(1, SPEED_MAX, "Pomalu", "Rychle")
        self.speed.valueChanged.connect(lambda v: self._mode_set("speed", v))
        g.addLayout(srow, 5, 1)

        g.addWidget(section("Směr"), 6, 0)
        drow = QHBoxLayout()
        self.dir_group = QButtonGroup(self)
        for d in range(DIRECTIONS):
            b = QPushButton(f"{d + 1}")
            b.setCheckable(True)
            b.setFixedWidth(44)
            b.setObjectName("seg")
            self.dir_group.addButton(b, d)
            drow.addWidget(b)
        drow.addStretch(1)
        self.dir_group.idClicked.connect(lambda d: self._mode_set("direction", d))
        g.addLayout(drow, 7, 0)
        note = QLabel("Náhled efektu nahoře je jen orientační – skutečná animace běží v klávesnici.")
        note.setObjectName("hint")
        note.setWordWrap(True)
        g.addWidget(note, 8, 0, 1, 2)
        g.setRowStretch(9, 1)
        self.mode_stack.addWidget(page)

        # page 1: custom colours info
        cpage = QWidget()
        cl = QVBoxLayout(cpage)
        cl.setContentsMargins(0, 0, 0, 0)
        t = QLabel("Vlastní barvy kláves")
        t.setObjectName("modeTitle")
        cl.addWidget(t)
        cl.addWidget(section("Jas"))
        self.custom_bright, cbrow = labeled_slider(1, BRIGHTNESS_MAX, "☾", "☀")
        self.custom_bright.valueChanged.connect(self._custom_brightness)
        cl.addLayout(cbrow)
        go = QPushButton("Upravit barvy kláves →")
        go.clicked.connect(lambda: self.tabs.setCurrentIndex(1))
        go.setFixedWidth(220)
        cl.addWidget(go)
        cl.addStretch(1)
        self.mode_stack.addWidget(cpage)

        # page 2: off
        opage = QWidget()
        ol = QVBoxLayout(opage)
        ol.setContentsMargins(0, 0, 0, 0)
        t = QLabel("Podsvícení vypnuto")
        t.setObjectName("modeTitle")
        ol.addWidget(t)
        ol.addStretch(1)
        self.mode_stack.addWidget(opage)

        lay.addWidget(self.mode_stack, 1)
        return w

    def _cur_mode(self) -> str:
        return self.profile["lighting"]["mode"]

    def _mode_selected(self, item, _prev=None):
        if item is None:
            return
        mid = item.data(Qt.UserRole)
        if not self._loading:
            self.profile["lighting"]["mode"] = mid
        self._show_mode_settings(mid)
        self._changed()

    def _show_mode_settings(self, mid: str):
        was = self._loading
        self._loading = True
        if mid == "custom":
            self.mode_stack.setCurrentIndex(1)
            self.custom_bright.setValue(self.profile["lighting"]["custom_brightness"])
        elif mid == "off":
            self.mode_stack.setCurrentIndex(2)
        else:
            self.mode_stack.setCurrentIndex(0)
            s = self.profile["lighting"]["modes"][mid]
            self.mode_title.setText(MODE_LABELS[mid])
            self.color_btn.setColor(s["color"])
            self.rainbow.setChecked(s["rainbow"])
            self.bright.setValue(s["brightness"])
            self.speed.setValue(s["speed"])
            b = self.dir_group.button(s["direction"])
            if b:
                b.setChecked(True)
            self.bg_host.setVisible(mid in _REACTIVE_MODES)
            self.bg_check.setChecked(bool(s.get("background")))
            if s.get("background"):
                self.bg_btn.setColor(s["background"])
            self.speed.setEnabled(mid != "static")
            for b in self.dir_group.buttons():
                b.setEnabled(mid != "static")
        self._loading = was

    def _mode_set(self, key, value):
        if self._loading:
            return
        mid = self._cur_mode()
        if mid in self.profile["lighting"]["modes"]:
            self.profile["lighting"]["modes"][mid][key] = value
            self._changed()

    def _bg_changed(self):
        if self._loading:
            return
        self._mode_set("background", self.bg_btn.color() if self.bg_check.isChecked() else None)

    def _mode_color(self, c):
        self._mode_set("color", c)
        if self.rainbow.isChecked() and not self._loading:
            self.rainbow.setChecked(False)

    def _custom_brightness(self, v):
        if self._loading:
            return
        self.profile["lighting"]["custom_brightness"] = v
        self._changed()

    # -- custom colours tab ----------------------------------------------
    def _build_custom_tab(self):
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(24)

        left = QVBoxLayout()
        left.addWidget(section("Štětec"))
        brow = QHBoxLayout()
        self.brush_btn = ColorButton(self.state.get("brush", "#ff6a3d"))
        self.brush_btn.colorChanged.connect(self._brush_changed)
        brow.addWidget(self.brush_btn)
        sw = Swatches()
        sw.picked.connect(lambda c: (self.brush_btn.setColor(c), self._brush_changed(c)))
        brow.addWidget(sw, 1)
        left.addLayout(brow)
        hint = QLabel("Klikni nebo táhni přes klávesy – obarví se aktuální barvou štětce.\n"
                      "Ctrl + klik převezme barvu klávesy do štětce.")
        hint.setObjectName("hint")
        left.addWidget(hint)
        left.addSpacing(8)
        left.addWidget(section("Zbytek kláves"))
        drow = QHBoxLayout()
        self.default_btn = ColorButton("#ffffff")
        self.default_btn.colorChanged.connect(self._custom_default)
        drow.addWidget(self.default_btn)
        dl = QLabel("barva kláves, které jsi neobarvil")
        dl.setObjectName("hint")
        drow.addWidget(dl, 1)
        left.addLayout(drow)
        left.addStretch(1)
        lay.addLayout(left, 1)

        right = QVBoxLayout()
        right.addWidget(section("Rychlé akce"))
        grid = QGridLayout()
        actions = [
            ("Obarvit vše štětcem", self._fill_all),
            ("Vymazat (vše = zbytek)", self._clear_custom),
            ("WASD + šipky", self._preset_gaming),
            ("Duha zleva doprava", self._preset_rainbow),
            ("Přechod dvou barev", self._preset_gradient),
            ("Řady podle barev", self._preset_rows),
        ]
        for i, (label, fn) in enumerate(actions):
            b = QPushButton(label)
            b.clicked.connect(fn)
            grid.addWidget(b, i // 2, i % 2)
        right.addLayout(grid)
        right.addStretch(1)
        lay.addLayout(right, 1)
        return w

    def _brush_changed(self, c):
        self.state["brush"] = c
        prof.save_state(self.state)

    def _ensure_custom_mode(self):
        if self._cur_mode() != "custom":
            self.profile["lighting"]["mode"] = "custom"
            self._select_mode_item("custom")

    def _paint(self, kid):
        self._ensure_custom_mode()
        self.profile["lighting"]["custom_colors"][kid] = self.brush_btn.color()
        self._changed()

    def _custom_default(self, c):
        self.profile["lighting"]["custom_default"] = c
        self._ensure_custom_mode()
        self._changed()

    def _fill_all(self):
        self._ensure_custom_mode()
        c = self.brush_btn.color()
        self.profile["lighting"]["custom_colors"] = {k.id: c for k in KEYS}
        self._changed()

    def _clear_custom(self):
        self._ensure_custom_mode()
        self.profile["lighting"]["custom_colors"] = {}
        self._changed()

    def _preset_gaming(self):
        self._ensure_custom_mode()
        cc = self.profile["lighting"]["custom_colors"]
        for k in ("w", "a", "s", "d"):
            cc[k] = "#ff2a00"
        for k in ("up", "down", "left", "right"):
            cc[k] = "#00ff60"
        for k in ("esc", "space", "lshift", "lctrl"):
            cc[k] = "#ffb000"
        self._changed()

    def _preset_rainbow(self):
        self._ensure_custom_mode()
        self.profile["lighting"]["custom_colors"] = {
            k.id: QColor.fromHsvF(((k.x + k.w / 2) / WIDTH_UNITS) * 0.85, 1, 1).name()
            for k in KEYS
        }
        self._changed()

    def _preset_gradient(self):
        a = QColorDialog.getColor(QColor(self.brush_btn.color()), self, "První barva (vlevo)")
        if not a.isValid():
            return
        b = QColorDialog.getColor(QColor("#0090ff"), self, "Druhá barva (vpravo)")
        if not b.isValid():
            return
        self._ensure_custom_mode()
        out = {}
        for k in KEYS:
            t = (k.x + k.w / 2) / WIDTH_UNITS
            out[k.id] = QColor.fromRgbF(a.redF() + (b.redF() - a.redF()) * t,
                                        a.greenF() + (b.greenF() - a.greenF()) * t,
                                        a.blueF() + (b.blueF() - a.blueF()) * t).name()
        self.profile["lighting"]["custom_colors"] = out
        self._changed()

    def _preset_rows(self):
        self._ensure_custom_mode()
        palette = ["#ff0040", "#ff8000", "#ffe000", "#00ff60", "#00a0ff", "#a040ff"]
        rows = sorted({k.y for k in KEYS})
        self.profile["lighting"]["custom_colors"] = {
            k.id: palette[rows.index(k.y) % len(palette)] for k in KEYS}
        self._changed()

    # -- keymap tab ------------------------------------------------------
    def _build_keymap_tab(self):
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(24)

        left = QVBoxLayout()
        self.km_title = QLabel("Vyber klávesu na klávesnici nahoře")
        self.km_title.setObjectName("modeTitle")
        left.addWidget(self.km_title)
        self.km_current = QLabel("")
        self.km_current.setObjectName("hint")
        left.addWidget(self.km_current)
        left.addSpacing(6)

        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.addWidget(QLabel("Funkce"), 0, 0)
        self.km_type = QComboBox()
        for t, label in (("default", "Výchozí (původní funkce)"), ("key", "Klávesa / zkratka"),
                         ("media", "Multimédia a aplikace"), ("mouse", "Tlačítko myši"),
                         ("disabled", "Vypnout klávesu")):
            self.km_type.addItem(label, t)
        self.km_type.currentIndexChanged.connect(self._km_type_changed)
        form.addWidget(self.km_type, 0, 1)
        self.km_value_label = QLabel("Hodnota")
        form.addWidget(self.km_value_label, 1, 0)
        self.km_value = QComboBox()
        self.km_value.setMaxVisibleItems(18)
        form.addWidget(self.km_value, 1, 1)
        self.km_mods_label = QLabel("Modifikátory")
        form.addWidget(self.km_mods_label, 2, 0)
        mods = QHBoxLayout()
        self.km_mods: dict[str, QCheckBox] = {}
        for m in ("lctrl", "lshift", "lalt", "lwin"):
            cb = QCheckBox(MOD_LABELS[m])
            self.km_mods[m] = cb
            mods.addWidget(cb)
        mods.addStretch(1)
        form.addLayout(mods, 2, 1)
        left.addLayout(form)

        brow = QHBoxLayout()
        self.km_assign = QPushButton("Přiřadit")
        self.km_assign.setObjectName("primary")
        self.km_assign.clicked.connect(self._km_assign)
        brow.addWidget(self.km_assign)
        self.km_reset = QPushButton("Vrátit výchozí")
        self.km_reset.clicked.connect(self._km_reset)
        brow.addWidget(self.km_reset)
        brow.addStretch(1)
        left.addLayout(brow)
        warn = QLabel("Mapování se do klávesnice nahraje tlačítkem „Nahrát do klávesnice“ "
                      "a vždy přepíše celé mapování uložené v klávesnici.")
        warn.setObjectName("hint")
        warn.setWordWrap(True)
        left.addWidget(warn)
        left.addStretch(1)
        lay.addLayout(left, 3)

        right = QVBoxLayout()
        right.addWidget(section("Přemapované klávesy"))
        self.km_list = QListWidget()
        self.km_list.itemClicked.connect(lambda it: self._km_select(it.data(Qt.UserRole)))
        right.addWidget(self.km_list, 1)
        clear = QPushButton("Vše na výchozí")
        clear.clicked.connect(self._km_clear_all)
        right.addWidget(clear)
        lay.addLayout(right, 2)

        self._km_key: str | None = None
        self._km_type_changed()
        self._km_enable(False)
        return w

    def _km_enable(self, on):
        for wdg in (self.km_type, self.km_value, self.km_assign, self.km_reset,
                    *self.km_mods.values()):
            wdg.setEnabled(on)

    def _km_type_changed(self):
        t = self.km_type.currentData()
        self.km_value.clear()
        if t == "key":
            for usage, label in KEY_USAGES:
                self.km_value.addItem(label, usage)
        elif t == "media":
            for usage, label in MEDIA_USAGES:
                self.km_value.addItem(label, usage)
        elif t == "mouse":
            for mid, label, _ in MOUSE_ACTIONS:
                self.km_value.addItem(label, mid)
        has_value = t in ("key", "media", "mouse")
        self.km_value.setVisible(has_value)
        self.km_value_label.setVisible(has_value)
        self.km_mods_label.setVisible(t == "key")
        for cb in self.km_mods.values():
            cb.setVisible(t == "key")

    def _km_select(self, kid: str):
        self._km_key = kid
        k = KEYS_BY_ID[kid]
        self.kb.selected = {kid}
        self.kb.update()
        name = (k.cz if self.kb.legend == "cz" else k.us) or "Mezerník"
        self.km_title.setText(f"Klávesa: {name}")
        if kid in NON_REMAPPABLE:
            self.km_current.setText("Klávesu Fn nelze přemapovat.")
            self._km_enable(False)
            return
        self._km_enable(True)
        action = self.profile["keymap"].get(kid)
        self.km_current.setText(f"Aktuálně: {describe_action(action)}")
        t = (action or {}).get("type", "default")
        self.km_type.setCurrentIndex(self.km_type.findData(t))
        self._km_type_changed()
        if action:
            if t in ("key", "media"):
                self.km_value.setCurrentIndex(self.km_value.findData(int(action["usage"])))
            elif t == "mouse":
                self.km_value.setCurrentIndex(self.km_value.findData(action["button"]))
            for m, cb in self.km_mods.items():
                cb.setChecked(m in action.get("mods", []))
        else:
            for cb in self.km_mods.values():
                cb.setChecked(False)

    def _km_assign(self):
        if not self._km_key:
            return
        t = self.km_type.currentData()
        if t == "default":
            self.profile["keymap"].pop(self._km_key, None)
        elif t == "disabled":
            self.profile["keymap"][self._km_key] = {"type": "disabled"}
        elif t in ("key", "media"):
            a = {"type": t, "usage": int(self.km_value.currentData())}
            if t == "key":
                mods = [m for m, cb in self.km_mods.items() if cb.isChecked()]
                if mods:
                    a["mods"] = mods
            self.profile["keymap"][self._km_key] = a
        elif t == "mouse":
            self.profile["keymap"][self._km_key] = {"type": "mouse",
                                                    "button": self.km_value.currentData()}
        self._changed(lighting=False)
        self._km_select(self._km_key)
        self._update_apply_button()

    def _km_reset(self):
        if self._km_key:
            self.profile["keymap"].pop(self._km_key, None)
            self._changed(lighting=False)
            self._km_select(self._km_key)
            self._update_apply_button()

    def _km_clear_all(self):
        if not self.profile["keymap"]:
            return
        if QMessageBox.question(self, "Mapování kláves",
                                "Vrátit všechny klávesy na výchozí funkci?") != QMessageBox.Yes:
            return
        self.profile["keymap"] = {}
        self._changed(lighting=False)
        if self._km_key:
            self._km_select(self._km_key)
        self._update_apply_button()

    def _refresh_keymap_badges(self):
        km = self.profile["keymap"]
        self.kb.badges = {kid: describe_action(a) for kid, a in km.items() if kid in KEYS_BY_ID}
        self.km_list.clear()
        for k in KEYS:
            if k.id in km:
                name = (k.cz if self.kb.legend == "cz" else k.us) or "Mezerník"
                it = QListWidgetItem(f"{name}  →  {describe_action(km[k.id])}")
                it.setData(Qt.UserRole, k.id)
                self.km_list.addItem(it)
        self.kb.update()

    # -- scripts tab -------------------------------------------------------
    def _build_scripts_tab(self):
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(20)

        left = QVBoxLayout()
        self.script_list = QListWidget()
        self.script_list.setFixedWidth(240)
        self.script_list.currentItemChanged.connect(self._script_selected)
        left.addWidget(self.script_list, 1)
        brow = QHBoxLayout()
        b = QPushButton("Nový skript…")
        b.clicked.connect(self._script_new)
        brow.addWidget(b)
        b = QPushButton("Složka")
        b.setToolTip(str(scripting.USER_DIR))
        b.clicked.connect(self._script_folder)
        brow.addWidget(b)
        left.addLayout(brow)
        lay.addLayout(left)

        right = QVBoxLayout()
        right.setSpacing(8)
        self.sc_title = QLabel()
        self.sc_title.setObjectName("modeTitle")
        right.addWidget(self.sc_title)
        self.sc_desc = QLabel()
        self.sc_desc.setObjectName("hint")
        self.sc_desc.setWordWrap(True)
        right.addWidget(self.sc_desc)
        self.sc_form_host = QWidget()
        self.sc_form_host.setObjectName("plain")
        self.sc_form = QGridLayout(self.sc_form_host)
        self.sc_form.setContentsMargins(0, 6, 0, 6)
        self.sc_form.setHorizontalSpacing(16)
        self.sc_form.setVerticalSpacing(8)
        right.addWidget(self.sc_form_host)
        self.sc_error = QLabel()
        self.sc_error.setObjectName("error")
        self.sc_error.setWordWrap(True)
        self.sc_error.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.sc_error.hide()
        right.addWidget(self.sc_error)
        right.addStretch(1)
        arow = QHBoxLayout()
        self.sc_apply = QPushButton("Nahrát do klávesnice")
        self.sc_apply.setObjectName("primary")
        self.sc_apply.clicked.connect(self._script_apply)
        arow.addWidget(self.sc_apply)
        self.sc_reset = QPushButton("Výchozí hodnoty")
        self.sc_reset.clicked.connect(self._script_reset)
        arow.addWidget(self.sc_reset)
        self.sc_edit = QPushButton("Upravit kód")
        self.sc_edit.clicked.connect(self._script_edit)
        arow.addWidget(self.sc_edit)
        arow.addStretch(1)
        right.addLayout(arow)
        lay.addLayout(right, 1)

        self._scripts: list[scripting.Script] = []
        self._script: scripting.Script | None = None
        self._script_light: dict | None = None
        self._script_mtimes: dict = {}
        self._reload_scripts()
        self._script_poll = QTimer(self, interval=1000)
        self._script_poll.timeout.connect(self._poll_scripts)
        self._script_poll.start()
        return w

    def _script_files(self) -> dict:
        out = {}
        for d in (scripting.BUNDLED_DIR, scripting.USER_DIR):
            if d.is_dir():
                for p in d.glob("*.py"):
                    try:
                        out[str(p)] = p.stat().st_mtime
                    except OSError:
                        pass
        return out

    def _poll_scripts(self):
        files = self._script_files()
        if files != self._script_mtimes:
            self._reload_scripts()

    def _reload_scripts(self, select: str | None = None):
        self._script_mtimes = self._script_files()
        current = select or (self._script.id if self._script else self.state.get("script"))
        self._scripts = scripting.list_scripts()
        self.script_list.blockSignals(True)
        self.script_list.clear()
        row = 0
        for i, s in enumerate(self._scripts):
            it = QListWidgetItem(("⚠ " if s.error else "") + s.name +
                                 ("" if s.bundled else "  ✎"))
            it.setData(Qt.UserRole, s.id)
            it.setToolTip(str(s.path))
            self.script_list.addItem(it)
            if s.id == current:
                row = i
        self.script_list.blockSignals(False)
        if self._scripts:
            self.script_list.setCurrentRow(row)
            self._script_selected(self.script_list.currentItem())
        else:
            self._script = None
            self._script_light = None
            self.sc_title.setText("Zatím žádné skripty")
            self.sc_desc.setText("Skript je krátký soubor v Pythonu, který navrhne podsvícení. "
                                 "Začni tlačítkem „Nový skript…“ – šablona popisuje, co skript umí.")
            while self.sc_form.count():
                wdg = self.sc_form.takeAt(0).widget()
                if wdg:
                    wdg.deleteLater()
            self.sc_error.hide()
            for b in (self.sc_apply, self.sc_reset, self.sc_edit):
                b.setEnabled(False)

    def _script_values(self) -> dict:
        s = self._script
        saved = self.state.get("script_params", {}).get(s.id, {})
        vals = s.defaults()
        vals.update({k: v for k, v in saved.items() if k in s.params})
        return vals

    def _script_store(self, key, value):
        if self._loading or not self._script:
            return
        self.state.setdefault("script_params", {}).setdefault(self._script.id, {})[key] = value
        prof.save_state(self.state)
        self._script_run()

    def _script_selected(self, item, _prev=None):
        if item is None:
            return
        sid = item.data(Qt.UserRole)
        self._script = next((s for s in self._scripts if s.id == sid), None)
        if not self._script:
            return
        s = self._script
        self.sc_reset.setEnabled(True)
        self.sc_edit.setEnabled(True)
        self.state["script"] = s.id
        prof.save_state(self.state)
        self.sc_title.setText(s.name)
        self.sc_desc.setText(s.description + ("" if s.bundled else f"\n{s.path}"))
        self.sc_edit.setText("Upravit kód" if not s.bundled else "Upravit kopii kódu")
        # rebuild parameter form
        while self.sc_form.count():
            wdg = self.sc_form.takeAt(0).widget()
            if wdg:
                wdg.deleteLater()
        vals = self._script_values()
        self._loading = True
        for row, (key, spec) in enumerate(s.params.items()):
            self.sc_form.addWidget(QLabel(spec.get("label", key)), row, 0)
            self.sc_form.addWidget(self._param_widget(key, spec, vals.get(key)), row, 1)
        self.sc_form.setColumnStretch(1, 1)
        self._loading = False
        self._script_run()

    def _param_widget(self, key, spec, value):
        t = spec.get("type", "int")
        if t == "color":
            host = QWidget()
            host.setObjectName("plain")
            hl = QHBoxLayout(host)
            hl.setContentsMargins(0, 0, 0, 0)
            btn = ColorButton(value or "#ffffff")
            btn.colorChanged.connect(lambda c: self._script_store(key, c))
            hl.addWidget(btn)
            sw = Swatches()
            sw.picked.connect(lambda c, b=btn: (b.setColor(c), self._script_store(key, c)))
            hl.addWidget(sw, 1)
            return host
        if t == "bool":
            cb = QCheckBox()
            cb.setChecked(bool(value))
            cb.toggled.connect(lambda v: self._script_store(key, v))
            return cb
        if t == "choice":
            combo = QComboBox()
            combo.addItems([str(o) for o in spec.get("options", [])])
            combo.setCurrentText(str(value))
            combo.currentTextChanged.connect(lambda v: self._script_store(key, v))
            return combo
        if t == "float":
            sp = QDoubleSpinBox()
            sp.setRange(spec.get("min", 0.0), spec.get("max", 1.0))
            sp.setSingleStep(spec.get("step", 0.05))
            sp.setValue(float(value or 0))
            sp.valueChanged.connect(lambda v: self._script_store(key, v))
            return sp
        host = QWidget()
        host.setObjectName("plain")
        s, row = labeled_slider(int(spec.get("min", 0)), int(spec.get("max", 100)))
        rng_ = spec.get("max", 100) - spec.get("min", 0)
        s.setTickPosition(QSlider.TicksBelow if rng_ <= 20 else QSlider.NoTicks)
        s.setValue(int(value if value is not None else spec.get("min", 0)))
        s.valueChanged.emit(s.value())
        s.valueChanged.connect(lambda v: self._script_store(key, v))
        row.setContentsMargins(0, 0, 0, 0)
        host.setLayout(row)
        return host

    def _script_run(self):
        s = self._script
        self._script_light = None
        try:
            if s is None:
                return
            if s.error:
                raise scripting.ScriptError(s.error)
            kb = s.run(self._script_values())
            self._script_light = kb.to_lighting(self.profile["lighting"])
            self.sc_error.hide()
            self.sc_apply.setEnabled(getattr(self, "_connected", False))
            mode = self._script_light["mode"]
            if mode != "custom" and hasattr(self, "status"):
                self.status.showMessage(
                    f"Skript používá efekt „{MODE_LABELS[mode]}“ – animace běží až v klávesnici.", 5000)
        except scripting.ScriptError as exc:
            self.sc_error.setText(f"Chyba ve skriptu:\n{exc}")
            self.sc_error.show()
            self.sc_apply.setEnabled(False)

    def _script_apply(self):
        if not self._script_light:
            return
        self.profile["lighting"] = copy.deepcopy(self._script_light)
        self.profile["script"] = {"id": self._script.id, "params": self._script_values()}
        self._autosave()
        self._load_into_ui()
        self.apply(include_keymap=False)

    def _script_reset(self):
        if self._script:
            self.state.get("script_params", {}).pop(self._script.id, None)
            prof.save_state(self.state)
            self._script_selected(self.script_list.currentItem())

    def _script_edit(self):
        s = self._script
        if not s:
            return
        path = s.path if not s.bundled else scripting.user_copy(s)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        if s.bundled:
            self._reload_scripts(select=s.id)

    def _script_new(self):
        name, ok = QInputDialog.getText(self, "Nový skript", "Název skriptu:")
        if not ok or not name.strip():
            return
        path = scripting.new_script(name.strip())
        self._reload_scripts(select=path.stem)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _script_folder(self):
        scripting.USER_DIR.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(scripting.USER_DIR)))

    # -- keyboard interaction --------------------------------------------
    def _tab_changed(self, i):
        self.kb.selected = {self._km_key} if (i == 2 and self._km_key) else set()
        self.kb.setCursor(Qt.CrossCursor if i == 1 else Qt.PointingHandCursor)
        if i == 1:
            self._ensure_custom_mode()
            self._changed()
        self.kb.update()

    def _key_clicked(self, kid, mods):
        tab = self.tabs.currentIndex()
        if tab == 1:
            if mods & Qt.ControlModifier:
                c = self.profile["lighting"]["custom_colors"].get(
                    kid, self.profile["lighting"]["custom_default"])
                self.brush_btn.setColor(c)
                self._brush_changed(c)
            else:
                self._paint(kid)
        elif tab == 2:
            self._km_select(kid)
        elif tab == 3:
            pass
        else:
            self.tabs.setCurrentIndex(1)

    def _key_dragged(self, kid):
        if self.tabs.currentIndex() == 1:
            if self.profile["lighting"]["custom_colors"].get(kid) != self.brush_btn.color():
                self._paint(kid)

    # -- preview -----------------------------------------------------------
    def _update_preview(self):
        light = self.profile["lighting"]
        if self.tabs.currentIndex() == 3 and self._script_light:
            light = self._script_light
        mode = light["mode"]
        t = time.monotonic() - self._t0
        colors: dict[str, QColor] = {}
        if self.tabs.currentIndex() == 2:
            # key remapping: neutral keys so badges and selection stand out
            self.kb.colors = {k.id: QColor("#5a6070") for k in KEYS}
            self.kb.update()
            return
        if mode == "off":
            colors = {k.id: QColor(0, 0, 0) for k in KEYS}
        elif mode == "custom":
            scale = 0.3 + 0.7 * light["custom_brightness"] / BRIGHTNESS_MAX
            cc, default = light["custom_colors"], light["custom_default"]
            for k in KEYS:
                c = QColor(cc.get(k.id, default))
                colors[k.id] = QColor.fromRgbF(c.redF() * scale, c.greenF() * scale, c.blueF() * scale)
        else:
            s = light["modes"][mode]
            scale = 0.3 + 0.7 * s["brightness"] / BRIGHTNESS_MAX
            rate = 0.05 + s["speed"] * 0.05
            base = QColor(s["color"])
            if mode in _REACTIVE_MODES:
                self.kb.colors = self._reactive_preview(mode, s, t, scale)
                self.kb.update()
                return
            for k in KEYS:
                cx = (k.x + k.w / 2) / WIDTH_UNITS
                cy = (k.y + k.h / 2) / HEIGHT_UNITS
                level = 1.0
                if mode == "spectrum":
                    c = QColor.fromHsvF((t * rate) % 1.0, 1, 1)
                elif mode in ("breath", "pulsating"):
                    level = 0.15 + 0.85 * (0.5 + 0.5 * math.sin(t * rate * 2 * math.pi))
                    c = QColor.fromHsvF((t * rate * 0.25) % 1.0, 1, 1) if s["rainbow"] else base
                elif mode in _WAVE_MODES or s["rainbow"]:
                    pos = cx if s["direction"] in (0, 1) else cy
                    sign = -1 if s["direction"] in (1, 3) else 1
                    if s["rainbow"] or mode in ("colourful",):
                        c = QColor.fromHsvF((pos * 0.9 + sign * t * rate) % 1.0, 1, 1)
                    else:
                        c = base
                        level = 0.25 + 0.75 * (0.5 + 0.5 * math.sin((pos - sign * t * rate) * 2 * math.pi))
                elif mode == "glittering":
                    h = (hash((k.id, int(t * rate * 6))) % 100) / 100
                    level = 1.0 if h > 0.8 else 0.25
                    c = base
                else:
                    c = base
                f = scale * level
                colors[k.id] = QColor.fromRgbF(c.redF() * f, c.greenF() * f, c.blueF() * f)
        self.kb.colors = colors
        self.kb.dim_keys = set()
        self.kb.update()

    def _reactive_preview(self, mode, s, t, scale):
        """Simulated key presses for effects that react to typing."""
        import random
        presses = getattr(self, "_sim_presses", [])
        if not presses or t - presses[-1][1] > 0.45:
            presses.append((random.choice(KEYS), t))
        presses = [(k, t0) for k, t0 in presses if t - t0 < 4]
        self._sim_presses = presses
        fade = 0.4 + s["speed"] * 0.18
        out = {}
        for k in KEYS:
            level = 0.0
            hue_shift = 0.0
            for pk, t0 in presses:
                age = t - t0
                if mode in ("single_on", "single_off"):
                    if pk.id == k.id:
                        level = max(level, math.exp(-age * fade))
                else:
                    d = math.hypot(k.x - pk.x, (k.y - pk.y) * 1.2)
                    front = age * (3 + s["speed"] * 0.8)
                    ring = math.exp(-((d - front) ** 2) / 1.2) * math.exp(-age * 0.9)
                    if mode == "explode":
                        ring = max(ring, math.exp(-d) * math.exp(-age * fade))
                    if ring > level:
                        level, hue_shift = ring, (pk.x / WIDTH_UNITS)
            if mode == "single_off":
                level = 1 - level
            if s["rainbow"]:
                c = QColor.fromHsvF((k.x / WIDTH_UNITS * 0.8 + hue_shift + t * 0.1) % 1.0, 1, 1)
            else:
                c = QColor(s["color"])
            bg = QColor(s.get("background") or "#000000")
            lv = min(1.0, level)
            out[k.id] = QColor.fromRgbF(
                scale * (bg.redF() * (1 - lv) + c.redF() * lv),
                scale * (bg.greenF() * (1 - lv) + c.greenF() * lv),
                scale * (bg.blueF() * (1 - lv) + c.blueF() * lv))
        return out

    # -- load/apply --------------------------------------------------------
    def _select_mode_item(self, mid):
        for i in range(self.mode_list.count()):
            if self.mode_list.item(i).data(Qt.UserRole) == mid:
                was = self._loading
                self._loading = True
                self.mode_list.setCurrentRow(i)
                self._loading = was
                self._show_mode_settings(mid)
                return

    def _load_into_ui(self):
        self._loading = True
        self._select_mode_item(self._cur_mode())
        self.default_btn.setColor(self.profile["lighting"]["custom_default"])
        self.kb.legend = self.state.get("legend", "cz")
        self._loading = False
        self._refresh_keymap_badges()
        if self._km_key:
            self._km_select(self._km_key)
        self._update_apply_button()

    def _keymap_dirty(self) -> bool:
        return _keymap_hash(self.profile["keymap"]) != self.state.get("keymap_hash")

    def _update_apply_button(self):
        if self._keymap_dirty():
            self.apply_btn.setText("Nahrát do klávesnice •")
            self.apply_btn.setToolTip("Mapování kláves se změnilo a ještě není v klávesnici (Ctrl+S)")
        else:
            self.apply_btn.setText("Nahrát do klávesnice")
            self.apply_btn.setToolTip("Ctrl+S")

    def apply(self, include_keymap: bool = True):
        if not self._connected:
            self.status.showMessage("Klávesnice není připojená.", 4000)
            return
        keymap = None
        if include_keymap and self._keymap_dirty():
            keymap = self.profile["keymap"]
            self._pending_keymap_hash = _keymap_hash(keymap)
        self.writer.submit(self.profile["lighting"], keymap)

    def _write_done(self, ok: bool, msg: str):
        if ok:
            if "mapování" in msg and getattr(self, "_pending_keymap_hash", None):
                self.state["keymap_hash"] = self._pending_keymap_hash
                prof.save_state(self.state)
                self._update_apply_button()
            self.status.showMessage(msg, 3000)
        else:
            self.status.showMessage(f"Chyba: {msg}", 8000)

    def _check_device(self):
        devs = find_devices()
        self._connected = bool(devs)
        if devs:
            self.device_label.setText(f"<span style='color:#3ddc84'>●</span> Připojeno ({devs[0].path})")
        else:
            self.device_label.setText("<span style='color:#ff5252'>●</span> Klávesnice nepřipojena")
        self.apply_btn.setEnabled(self._connected)
        self.sc_apply.setEnabled(self._connected and self._script_light is not None)

    def closeEvent(self, e):
        self._autosave()
        super().closeEvent(e)


STYLE = """
QWidget { background: #16181d; color: #d7dbe3; font-size: 13px; }
QLabel, QCheckBox, QSlider, QWidget#plain { background: transparent; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #3a3f4a; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #4a5160; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QToolButton::menu-indicator { image: none; width: 0; }
QLabel#title { font-size: 20px; font-weight: 800; letter-spacing: 3px; color: #ffffff; }
QLabel#subtitle { color: #ff6a3d; font-weight: 600; letter-spacing: 1px; padding-top: 4px; }
QLabel#section { color: #7d8594; font-size: 11px; font-weight: 700; letter-spacing: 1.5px; }
QLabel#modeTitle { font-size: 17px; font-weight: 700; color: #ffffff; }
QLabel#hint { color: #7d8594; }
QLabel#error { color: #ff7a7a; font-family: monospace; background: #2a1517;
               border: 1px solid #5a2a2e; border-radius: 6px; padding: 8px; }
QTabWidget::pane { border: 1px solid #262a33; border-radius: 10px; background: #1b1e24; top: -1px; }
QTabWidget::pane > QWidget, QStackedWidget, QStackedWidget > QWidget { background: #1b1e24; }
QTabBar::tab { background: transparent; color: #8a92a1; padding: 8px 18px; margin-right: 4px;
               border-bottom: 2px solid transparent; font-weight: 600; }
QTabBar::tab:selected { color: #ffffff; border-bottom: 2px solid #ff6a3d; }
QTabBar::tab:hover { color: #d7dbe3; }
QPushButton { background: #2a2e37; border: 1px solid #353a45; border-radius: 7px; padding: 7px 14px; }
QPushButton:hover { background: #333845; border-color: #4a5160; }
QPushButton:pressed { background: #252931; }
QPushButton:disabled { color: #5c6370; background: #20232a; }
QPushButton#primary { background: #ff6a3d; color: #160a05; border: none; font-weight: 700; }
QPushButton#primary:hover { background: #ff8259; }
QPushButton#primary:disabled { background: #4a3a35; color: #8c7d78; }
QPushButton#seg:checked { background: #ff6a3d; color: #160a05; border-color: #ff6a3d; font-weight: 700; }
QToolButton { background: #2a2e37; border: 1px solid #353a45; border-radius: 7px; padding: 4px 10px; }
QComboBox { background: #23262e; border: 1px solid #353a45; border-radius: 7px; padding: 5px 10px; }
QComboBox:hover { border-color: #4a5160; }
QComboBox QAbstractItemView { background: #23262e; border: 1px solid #353a45; selection-background-color: #ff6a3d; selection-color: #160a05; }
QListWidget { background: #1f2229; border: 1px solid #2b2f38; border-radius: 8px; padding: 4px; outline: none; }
QListWidget::item { padding: 6px 10px; border-radius: 6px; }
QListWidget::item:hover { background: #2a2e37; }
QListWidget::item:selected { background: #ff6a3d; color: #160a05; font-weight: 600; }
QSlider::groove:horizontal { height: 4px; background: #2f343e; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #ff6a3d; border-radius: 2px; }
QSlider::handle:horizontal { background: #ffffff; width: 14px; height: 14px; margin: -6px 0; border-radius: 7px; }
QSlider::handle:horizontal:disabled { background: #555b66; }
QSlider::sub-page:horizontal:disabled { background: #3a3f4a; }
QCheckBox::indicator { width: 16px; height: 16px; border-radius: 4px; border: 1px solid #4a5160; background: #23262e; }
QCheckBox::indicator:checked { background: #ff6a3d; border-color: #ff6a3d; }
QStatusBar { background: #121418; color: #8a92a1; }
QMenu { background: #23262e; border: 1px solid #353a45; padding: 4px; }
QMenu::item { padding: 6px 18px; border-radius: 5px; }
QMenu::item:selected { background: #ff6a3d; color: #160a05; }
QToolTip { background: #23262e; color: #e8eaf0; border: 1px solid #4a5160; padding: 4px; }
"""


def _app_icon() -> QIcon:
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    for i in range(6):
        a = math.pi / 3 * i - math.pi / 2
        pt = QPointF(32 + 28 * math.cos(a), 32 + 28 * math.sin(a))
        path.moveTo(pt) if i == 0 else path.lineTo(pt)
    path.closeSubpath()
    p.setPen(QPen(ACCENT, 5))
    p.setBrush(QColor("#16181d"))
    p.drawPath(path)
    p.setPen(QPen(QColor("#ffffff"), 5, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(24, 20, 24, 44)
    p.drawLine(40, 20, 40, 44)
    p.drawLine(24, 32, 40, 32)
    p.end()
    return QIcon(pm)


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Hexblade")
    app.setDesktopFileName("hexblade")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    app.setWindowIcon(_app_icon())
    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
