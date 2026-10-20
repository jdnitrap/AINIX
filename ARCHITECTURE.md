# Architecture

## Layers

- **Router** (`core/router.py`): classifies help vs control.
- **Help** (`help/knowledge_base.py`): local topics, Nix docs, web search, optional Ollama.
- **Control** (`control/executor.py`): preview-first executor with basic safety checks.
- **CLI** (`ainix.py`): flags, config, history, notes, uninstall.

## Help order

Docs-first (default):
1. Local knowledge
2. Nix docs
3. Web if online
4. Local model if available and earlier steps miss

Model-first:
1. Local model
2. Fall back to docs/web if no model

## Model

Optional. No GPU assumptions. Ollama is the backend if present.
Config: `~/.config/ainix/config.json` with `model` and `model_first`.

## Safety

Preview never changes the system. Execute asks unless `--yes`.
Dangerous patterns are blocked.
