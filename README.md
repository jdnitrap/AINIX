# AINIX

Local NixOS assistant. Preview by default. Model is optional.

## Install (no clone, no Nix)

```bash
curl -fsSL https://raw.githubusercontent.com/jdnitrap/AINIX/main/install.sh | bash
```

Puts `ainix` in `~/.local/bin`. Ensure that is on your PATH.

```bash
ainix help
ainix --version
```

## Uninstall

```bash
ainix uninstall
```

Or manually:

```bash
rm ~/.local/bin/ainix
rm -rf ~/.local/share/ainix
```

## Usage

```bash
ainix "How do I install a package?"
ainix install firefox
ainix firefox
ainix --history
ainix --cache-clear
man ainix
```

## Help order

Default is **docs-first**:
1. Local knowledge
2. Nix docs (`nixos-option`, `nix search`)
3. Web (if online)
4. Local model (if available and the above miss)

**Model-first** (optional): ask the local model immediately.

Set once:

```bash
mkdir -p ~/.config/ainix
echo '{"model": "gemma2:9b", "model_first": true}' > ~/.config/ainix/config.json
```

Or per run:

```bash
ainix --model-first "question"
ainix --docs-first "question"
ainix --model gemma2:9b "question"
```

No model is required. Works on any hardware. Ollama handles NVIDIA, AMD, or CPU if you want a model.

## Local model (optional)

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull gemma2:9b
```

Then point AINIX at it with `--model` or the config file above.
