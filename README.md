# AINIX (test branch)

This branch makes a **local model the default answer path**.

- Help questions go to Ollama first
- Nix docs are passed in as context when available
- Control stays preview-first; the model does not change the system
- `--docs-first` skips the model

Main branch is unchanged.

## Try

```bash
ollama pull gemma2:9b
nix profile add github:jdnitrap/AINIX/test --no-write-lock-file
ainix "How do I install a package?"
```
