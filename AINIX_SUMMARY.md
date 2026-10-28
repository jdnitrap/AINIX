# AINIX summary

Local NixOS assistant. Version 0.7.0.

- Help: local knowledge, Nix docs, optional web, optional local model
- Control: preview by default (never runs commands); execute only with confirmation
- Rebuild: `ainix rebuild` shows flake-aware command + dry-build line
- Home Manager: `ainix home` detects config and shows switch command
- Model: optional, via Ollama, hardware-agnostic
- Modes: docs-first (default) or model-first
- Install: curl script to ~/.local/bin, or optional nix profile
- Uninstall: `ainix uninstall`

Does not edit your configuration. Does not require a GPU or a model.
