#!/usr/bin/env bash
# Install AINIX to ~/.local/bin without nix profile.
set -euo pipefail

DEST="${HOME}/.local/bin"
LIB="${HOME}/.local/share/ainix/lib"

mkdir -p "$DEST" "$LIB"

# Copy supporting modules
cp -r core control help config "$LIB/"

# Install launcher
cat > "$DEST/ainix" << EOF
#!/usr/bin/env bash
export PYTHONPATH="${LIB}:\${PYTHONPATH:-}"
exec python3 "${LIB}/ainix.py" "\$@"
EOF

cp ainix.py "$LIB/ainix.py"
chmod +x "$DEST/ainix" "$LIB/ainix.py"

# Man page if possible
if command -v install >/dev/null 2>&1; then
  mkdir -p "${HOME}/.local/share/man/man1"
  cp ainix.1 "${HOME}/.local/share/man/man1/ainix.1" 2>/dev/null || true
fi

echo "Installed to ${DEST}/ainix"
echo "Make sure ${DEST} is on your PATH."
echo "Then: ainix help"
