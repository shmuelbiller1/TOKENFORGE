#!/bin/sh
# Install a per-user Linux launcher without root access.
set -eu
APPDIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
DATA=${XDG_DATA_HOME:-"$HOME/.local/share"}
DEST="$DATA/tokenforge"
APPS="$DATA/applications"
mkdir -p "$DEST" "$APPS"
if [ "$APPDIR" != "$DEST" ]; then
  cp -R "$APPDIR"/. "$DEST"/
fi
chmod +x "$DEST/TokenForge"
# Desktop entry field codes, quotes and backslashes need escaping.
escaped=$(printf "%s" "$DEST/TokenForge" | sed 's/\\/\\\\/g; s/"/\\"/g; s/%/%%/g')
{
  printf "[Desktop Entry]\nType=Application\nVersion=1.0\nName=TokenForge\n"
  printf "Comment=Offline document optimization\nExec=\"%s\" %%F\n" "$escaped"
  printf "Terminal=false\nCategories=Office;Utility;\n"
  printf "MimeType=text/plain;text/csv;application/json;application/zip;application/pdf;\n"
} > "$APPS/tokenforge.desktop"
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$APPS" >/dev/null 2>&1 || true
fi
printf "TokenForge installed in %s. Search for TokenForge in your app launcher.\n" "$DEST"
