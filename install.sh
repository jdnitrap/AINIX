#!/usr/bin/env bash
# Install AINIX. Works on NixOS and elsewhere.
set -euo pipefail

if command -v nix >/dev/null 2>&1 && [[ -f /etc/NIXOS ]]; then
  echo "NixOS detected. Installing with nix profile (includes Python)..."
  nix profile add github:jdnitrap/AINIX --no-write-lock-file
  echo ""
  echo "Installed. Try: ainix help"
  echo "Uninstall later: nix profile remove AINIX"
  exit 0
fi

# Non-NixOS: download and use system Python
BASE="https://raw.githubusercontent.com/jdnitrap/AINIX/main"
DEST="${HOME}/.local/bin"
LIB="${HOME}/.local/share/ainix/lib"

if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
  echo "Python not found."
  echo "Install Python 3, then re-run this script."
  echo "Or on NixOS, use: nix profile add github:jdnitrap/AINIX --no-write-lock-file"
  exit 1
fi

fetch() {
  local path="$1"
  local out="$2"
  mkdir -p "$(dirname "$out")"
  curl -fsSL "${BASE}/${path}" -o "$out"
}

mkdir -p "$DEST" "$LIB"
echo "Downloading AINIX..."
fetch ainix.py "$LIB/ainix.py"
fetch ainix.1 "${HOME}/.local/share/man/man1/ainix.1"

for f in \
  core/__init__.py core/router.py \
  control/__init__.py control/executor.py \
  help/__init__.py help/knowledge_base.py \
  config/ainix.json
do
  fetch "$f" "$LIB/$f"
done

cat > "$DEST/ainix" << 'EOF'
#!/usr/bin/env bash
LIB="${HOME}/.local/share/ainix/lib"
export PYTHONPATH="${LIB}:${PYTHONPATH:-}"
for cmd in python3 python; do
  if command -v "$cmd" >/dev/null 2>&1; then
    exec "$cmd" "${LIB}/ainix.py" "$@"
  fi
done
echo "ainix: python not found" >&2
exit 1
EOF

chmod +x "$DEST/ainix" "$LIB/ainix.py"

PATH_LINE='export PATH="$HOME/.local/bin:$PATH"'
for rc in "$HOME/.bashrc" "$HOME/.profile" "$HOME/.zshrc"; do
  if [[ -f "$rc" ]] && ! grep -q '.local/bin' "$rc" 2>/dev/null; then
    echo "$PATH_LINE" >> "$rc"
  fi
done

echo ""
echo "Installed to ${DEST}/ainix"
echo "Open a new terminal, then: ainix help"
echo "Uninstall later: ainix uninstall"
