#!/usr/bin/env bash
# Remove CapyRunner. Your tasks/notes are kept unless you pass --purge.
set -euo pipefail
pkill -f "python -m capyrunner" 2>/dev/null || true
rm -rf "$HOME/.local/share/capyrunner"
rm -f  "$HOME/.local/bin/capyrunner" \
       "$HOME/.local/share/applications/capyrunner.desktop" \
       "$HOME/.local/share/icons/hicolor/256x256/apps/capyrunner.png" \
       "${XDG_CONFIG_HOME:-$HOME/.config}/autostart/capyrunner.desktop"
if [[ "${1:-}" == "--purge" ]]; then
  rm -rf "${XDG_CONFIG_HOME:-$HOME/.config}/CapyRunner"
  echo "CapyRunner removed, including your tasks, notes and settings."
else
  echo "CapyRunner removed. Your data is kept in ${XDG_CONFIG_HOME:-$HOME/.config}/CapyRunner (use --purge to delete it)."
fi
