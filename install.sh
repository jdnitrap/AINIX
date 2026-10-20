#!/usr/bin/env bash
# Install AINIX from anywhere. No Nix required.
set -euo pipefail

REPO="https://github.com/jdnitrap/AINIX.git"
DEST="${HOME}/.local/bin"
LIB="${HOME}/.local/share/ainix/lib"
TMP="$(mktemp -d)"

cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

# Use local checkout if present, otherwise clone.
if [[ -f ainix.py && -d core && -d help ]]; then
  SRC="."
else
  echo "Fetching AINIX..."
  git clone --depth 1 "$REPO" "$TMP/ainix"
  SRC="$TMP/ainix"
fi

mkdir -p "$DEST" "$LIB"
cp -r "$SRC/core" "$SRC/control" "$SRC/help" "$SRC/config" "$LIB/"
cp "$SRC/ainix.py" "$LIB/ainix.py"

cat > "$DEST/ainix" << EOF
#!/usr/bin/env bash
export PYTHONPATH="${LIB}:\${PYTHONPATH:-}"
exec python3 "${LIB}/ainix.py" "\$@"
EOF

chmod +x "$DEST/ainix" "$LIB/ainix.py"

if [[ -f "$SRC/ainix.1" ]]; then
  mkdir -p "${HOME}/.local/share/man/man1"
  cp "$SRC/ainix.1" "${HOME}/.local/share/man/man1/ainix.1"
fi

echo "Installed to ${DEST}/ainix"
echo "Ensure ${DEST} is on your PATH, then: ainix help"
