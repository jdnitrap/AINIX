# AINIX

A local assistant for NixOS. It answers questions, shows safe command previews, and can generate small Nix snippets. Nothing changes your system unless you explicitly ask.

## What it does

- **Help** — answers NixOS questions from a small knowledge base, real Nix docs, optional web search, and an optional local model
- **Preview** — shows the command or config line it would run, without running it
- **Start** — a short first-steps guide for new NixOS users

It does not edit your config files. A model is optional. It works without one.

## Install

One command. On NixOS it uses `nix profile` (Python included). Elsewhere it uses a local install if Python is present.

```bash
curl -fsSL https://raw.githubusercontent.com/jdnitrap/AINIX/main/install.sh | bash
```

Then:

```bash
ainix start
```

## Try it

```bash
ainix start
ainix "How do I install a package?"
ainix install firefox
ainix firefox
ainix --history
```

`ainix start` walks through install, rebuild, and rollback.

## Help order

Default is **docs-first**:
1. Local knowledge
2. Nix docs
3. Web (if online)
4. Local model only if the above miss

**Model-first** is optional. Set it once:

```bash
mkdir -p ~/.config/ainix
echo '{"model": "gemma2:9b", "model_first": true}' > ~/.config/ainix/config.json
```

Or for one run:

```bash
ainix --model-first "How do I enable ssh?"
ainix --docs-first "How do I enable ssh?"
```

## Optional local model

AINIX does not require a model. If you want one, use Ollama (works with NVIDIA, AMD, or CPU):

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull gemma2:9b
ainix --model gemma2:9b "How do I enable ssh?"
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

## More

- `ainix start` — first steps
- `ainix help` — usage
- `man ainix` — man page
- `ainix --version` — version
