#!/usr/bin/env bash
# Install AINIX by downloading files. No clone, no Nix.
set -euo pipefail

BASE="https://raw.githubusercontent.com/jdnitrap/AINIX/main"
DEST="${HOME}/.local/bin"
LIB="${HOME}/.local/share/ainix/lib"

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

# Launcher finds python3, python, or common Nix paths
cat > "$DEST/ainix" << 'EOF'
#!/usr/bin/env bash
LIB="${HOME}/.local/share/ainix/lib"
export PYTHONPATH="${LIB}:${PYTHONPATH:-}"

for cmd in python3 python /run/current-system/sw/bin/python3 /run/current-system/sw/bin/python; do
  if command -v "$cmd" >/dev/null 2>&1 || [[ -x "$cmd" ]]; then
    exec "$cmd" "${LIB}/ainix.py" "$@"
  fi
done

echo "ainix: python3 not found. Install Python or add it to PATH." >&2
exit 1
EOF

chmod +x "$DEST/ainix" "$LIB/ainix.py"

PATH_LINE='export PATH="$HOME/.local/bin:$PATH"'
for rc in "$HOME/.bashrc" "$HOME/.profile" "$HOME/.zshrc"; do
  if [[ -f "$rc" ]] && ! grep -q '.local/bin' "$rc" 2>/dev/null; then
    echo "$PATH_LINE" >> "$rc"
    echo "Added PATH to $rc"
  fi
done

export PATH="$HOME/.local/bin:$PATH"

echo ""
echo "Installed to ${DEST}/ainix"
echo "Open a new terminal, or run: source ~/.bashrc"
echo "Then: ainix help"
