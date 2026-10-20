# AINIX Summary

AINIX is a local Help + Control assistant for NixOS.

- **Help**: answers questions and explains NixOS concepts
- **Control**: previews and (optionally) executes commands with safety checks
- **Learning**: can remember what worked or failed (optional)

## Status

- Help layer: foundation
- Control layer: basic executor with preview/dry-run/execute
- Routing: present
- Learning: planned / partial

## Key files

- `ainix.py` — CLI
- `core/router.py` — query classification
- `help/knowledge_base.py` — advisory knowledge
- `control/executor.py` — safe execution
- `ainix-nixos-module.nix` — NixOS module

No external container system is required. Preview mode is the default.
