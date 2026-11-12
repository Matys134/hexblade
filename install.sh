#!/bin/sh
# Instalace Hexblade pro aktuálního uživatele.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"

# 1) udev pravidlo (přístup ke klávesnici bez roota)
if ! cmp -s "$DIR/udev/70-hexblade.rules" /etc/udev/rules.d/70-hexblade.rules 2>/dev/null; then
    echo "Instaluji udev pravidlo (vyžaduje sudo)…"
    sudo install -m 644 "$DIR/udev/70-hexblade.rules" /etc/udev/rules.d/70-hexblade.rules
    sudo udevadm control --reload-rules
    sudo udevadm trigger --subsystem-match=hidraw
fi

# 2) spouštěč v ~/.local/bin
mkdir -p "$HOME/.local/bin"
cat > "$HOME/.local/bin/hexblade" <<EOF
#!/bin/sh
PYTHONPATH="$DIR\${PYTHONPATH:+:\$PYTHONPATH}" exec python3 -m hexblade "\$@"
EOF
chmod +x "$HOME/.local/bin/hexblade"

# 3) ikona a položka v menu aplikací
install -Dm644 "$DIR/assets/hexblade.svg" "$HOME/.local/share/icons/hicolor/scalable/apps/hexblade.svg"
mkdir -p "$HOME/.local/share/applications"
cat > "$HOME/.local/share/applications/hexblade.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Hexblade
GenericName=Nastavení klávesnice
Comment=Podsvícení a mapování kláves pro CZC.Gaming Hexblade
Exec=$HOME/.local/bin/hexblade gui
Icon=hexblade
Terminal=false
Categories=Settings;HardwareSettings;
Keywords=keyboard;rgb;klávesnice;podsvícení;
EOF
command -v update-desktop-database >/dev/null && update-desktop-database "$HOME/.local/share/applications" || true

echo "Hotovo. Spusť „Hexblade“ z menu, nebo v terminálu: hexblade"
