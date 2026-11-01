# AINIX summary

Local NixOS assistant. Version 0.9.0.

- Help: local knowledge, Nix docs, optional web, optional local model
- Control: preview by default (never runs commands); execute only with confirmation
- Rebuild: `ainix rebuild` uses this machine's config (`/etc/nixos` or `AINIX_NIXOS_CONFIG`), including the flake attribute when there is one
- Home Manager: `ainix home` detects config and shows switch command
- Model: optional, via Ollama. When it runs, it receives this machine's layout, a short package-file excerpt, and docs already found
- Modes: docs-first (default) or model-first
- Install: curl script to ~/.local/bin, or optional nix profile
- Uninstall: `ainix uninstall`

Does not edit your configuration. Does not require a GPU or a model.
