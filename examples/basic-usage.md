# Basic usage

```bash
ainix help
ainix "How do I install a package?"
ainix install firefox
ainix --history
ainix --cache-clear
ainix uninstall
```

## Optional model

```bash
ollama pull gemma2:9b
ainix --model gemma2:9b "How do I enable ssh?"
```

## Model-first

```bash
mkdir -p ~/.config/ainix
echo '{"model": "gemma2:9b", "model_first": true}' > ~/.config/ainix/config.json
ainix "How do I enable ssh?"
```

Default remains docs-first if you do not set the config.
