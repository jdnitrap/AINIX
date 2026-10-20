# AINIX

Local NixOS assistant. Preview by default. Model is optional.

## Install

One command. On NixOS it uses `nix profile` (Python included). Elsewhere it uses a local install if Python is present.

```bash
curl -fsSL https://raw.githubusercontent.com/jdnitrap/AINIX/main/install.sh | bash
```

Then:

```bash
ainix help
```

## Uninstall

NixOS / nix profile:

```bash
nix profile remove AINIX
```

Curl install:

```bash
ainix uninstall
```

## Usage

```bash
ainix "How do I install a package?"
ainix install firefox
ainix --history
ainix --cache-clear
```

## Help order

Default is **docs-first**: local knowledge, Nix docs, web if online, then local model if needed.

**Model-first** (optional):

```bash
mkdir -p ~/.config/ainix
echo '{"model": "gemma2:9b", "model_first": true}' > ~/.config/ainix/config.json
```

No model is required. Ollama handles NVIDIA, AMD, or CPU if you want one.

## Local model (optional)

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull gemma2:9b
```
