#!/usr/bin/env bash
# CapyRunner installer for Linux (per-user, no root needed except optional system libraries).
# Usage:  ./install.sh            (interactive)
#         ./install.sh --yes      (accept defaults)
set -euo pipefail

YES=0
[[ "${1:-}" == "--yes" || "${1:-}" == "-y" ]] && YES=1

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$HOME/.local/share/capyrunner"
VENV="$APP_DIR/venv"
BIN_DIR="$HOME/.local/bin"
APPS_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
AUTOSTART_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"

say()  { printf '\033[1;33m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m ✓\033[0m %s\n' "$*"; }
warn() { printf '\033[1;31m !\033[0m %s\n' "$*"; }
ask()  { # ask "question" default(Y/N)
  local q="$1" def="${2:-Y}" a
  if [[ $YES == 1 ]]; then [[ $def == Y ]]; return; fi
  read -r -p "$q [$( [[ $def == Y ]] && echo Y/n || echo y/N )] " a || true
  a="${a:-$def}"; [[ "$a" =~ ^[Yy] ]]
}

say "Installing CapyRunner from $SRC"

# ---------------------------------------------------------------- python
if ! command -v python3 >/dev/null; then
  warn "python3 not found. Install it first (Ubuntu/Debian: sudo apt install python3 python3-venv)"; exit 1
fi
PYV=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' || { warn "Python $PYV is too old (need 3.9+)"; exit 1; }
ok "Python $PYV"

# ---------------------------------------------------------------- system libs (Debian/Ubuntu)
if command -v apt-get >/dev/null && command -v dpkg >/dev/null; then
  need=()
  python3 -c 'import venv, ensurepip' 2>/dev/null || need+=("python3-venv")
  for p in libxcb-cursor0 libegl1 libxkbcommon-x11-0 libnotify-bin; do
    dpkg -s "$p" >/dev/null 2>&1 || need+=("$p")
  done
  if (( ${#need[@]} )); then
    say "Missing system packages: ${need[*]}"
    if ask "Install them now with sudo apt?" Y; then
      sudo apt-get update -qq && sudo apt-get install -y "${need[@]}"
    else
      warn "Skipped. If CapyRunner fails to start, run: sudo apt install ${need[*]}"
    fi
  else
    ok "System packages present"
  fi
elif command -v dnf >/dev/null; then
  say "Fedora/RHEL: if needed run  sudo dnf install xcb-util-cursor libnotify"
elif command -v pacman >/dev/null; then
  say "Arch: if needed run  sudo pacman -S xcb-util-cursor libnotify"
fi

# ---------------------------------------------------------------- venv + package
say "Creating virtual environment in $VENV"
mkdir -p "$APP_DIR"
python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install -q --upgrade pip
say "Installing CapyRunner and PySide6-Essentials (first time downloads ~60 MB)…"
"$VENV/bin/python" -m pip install -q --upgrade "$SRC"
ok "Python packages installed"

# ---------------------------------------------------------------- launcher
mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/capyrunner" <<EOF
#!/usr/bin/env bash
# On Wayland, prefer XWayland so the floating pet can stay on top and remember its position.
# Set CAPYRUNNER_WAYLAND=1 to use native Wayland instead.
# A desktop-wide QT_QPA_PLATFORM=wayland (e.g. "wayland;xcb" on Hyprland/Omarchy) is overridden too,
# otherwise the compositor centres the pet and it cannot move.
if [ -n "\${WAYLAND_DISPLAY:-}" ] && [ -n "\${DISPLAY:-}" ] && [ -z "\${CAPYRUNNER_WAYLAND:-}" ]; then
  case "\${QT_QPA_PLATFORM:-}" in
    ""|wayland*)
      if ldconfig -p 2>/dev/null | grep -q 'libxcb-cursor.so.0'; then export QT_QPA_PLATFORM=xcb; fi ;;
  esac
fi
exec "$VENV/bin/python" -m capyrunner "\$@"
EOF
chmod +x "$BIN_DIR/capyrunner"
ok "Launcher: $BIN_DIR/capyrunner"

# ---------------------------------------------------------------- icon + menu entry
mkdir -p "$ICON_DIR" "$APPS_DIR"
cp "$SRC/capyrunner/assets/capyrunner.png" "$ICON_DIR/capyrunner.png"
cat > "$APPS_DIR/capyrunner.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=CapyRunner
GenericName=Task & notification mascot
Comment=Running mascot for your tasks, notes and notifications
Exec=$BIN_DIR/capyrunner
Icon=capyrunner
Categories=Utility;
Keywords=tasks;notes;reminder;notification;runcat;
StartupNotify=false
EOF
command -v update-desktop-database >/dev/null && update-desktop-database -q "$APPS_DIR" 2>/dev/null || true
command -v gtk-update-icon-cache  >/dev/null && gtk-update-icon-cache -q -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
ok "Added to your applications menu"

# ---------------------------------------------------------------- autostart
if ask "Start CapyRunner automatically when you log in?" Y; then
  mkdir -p "$AUTOSTART_DIR"
  cp "$APPS_DIR/capyrunner.desktop" "$AUTOSTART_DIR/capyrunner.desktop"
  echo "X-GNOME-Autostart-Delay=5" >> "$AUTOSTART_DIR/capyrunner.desktop"
  "$VENV/bin/python" - <<'PY' || true
import json, os
p = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "CapyRunner", "settings.json")
os.makedirs(os.path.dirname(p), exist_ok=True)
s = json.load(open(p)) if os.path.exists(p) else {}
s["autostart"] = True
json.dump(s, open(p, "w"), indent=2)
PY
  ok "Autostart enabled"
fi

# ---------------------------------------------------------------- tray tips
case "${XDG_CURRENT_DESKTOP:-}" in
  *GNOME*|*gnome*)
    if command -v gnome-extensions >/dev/null && ! gnome-extensions list --enabled 2>/dev/null | grep -qi appindicator; then
      warn "GNOME hides tray icons by default. For the top-bar runner, install the 'AppIndicator and KStatusNotifierItem Support' extension"
      warn "  (Ubuntu: sudo apt install gnome-shell-extension-appindicator, then log out/in)."
      warn "  Without it CapyRunner still works as a floating pet on your desktop."
    fi ;;
esac

case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) warn "$BIN_DIR is not in your PATH. Add this to ~/.bashrc:  export PATH=\"\$HOME/.local/bin:\$PATH\"" ;;
esac

# ---------------------------------------------------------------- launch
if [[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]] && ask "Launch CapyRunner now?" Y; then
  (setsid "$BIN_DIR/capyrunner" >/dev/null 2>&1 &)
  ok "CapyRunner started — look for the runner in your top bar / tray or on your desktop."
fi

say "Done. Uninstall any time with: $SRC/uninstall.sh"
