# AINIX

Local NixOS assistant: Help (explain) + Control (preview, then optional execute).

Preview is the default. Nothing runs unless you pass `--execute`.

## Install (any NixOS machine)

```bash
nix profile add github:jdnitrap/AINIX --no-write-lock-file
```

Then:

```bash
ainix --help
ainix "How do I install a package?"
ainix install firefox          # preview only
```

Remove later:

```bash
nix profile remove ainix
```

### Why the flag

The repo has no committed `flake.lock` yet. Nix tries to write one on install and fails on a remote flake. `--no-write-lock-file` skips that.

A committed lock file would make the plain command work. If you can, generate one and open a PR (see below).

## One-shot (no install)

```bash
nix run github:jdnitrap/AINIX --no-write-lock-file -- "How do I install a package?"
```

## System-wide (optional)

```nix
inputs.ainix.url = "github:jdnitrap/AINIX";
# modules = [ ainix.nixosModules.default ];
# services.ainix.enable = true;
```

## What it does

- **Help**: answers from a small local base, then falls back to `nixos-option` / `nix search` when available
- **Control**: shows a preview (and a dry-run for nix commands when possible). Logs real executions to `~/.local/share/ainix/commands.log`
- Blocks obviously dangerous commands unless you force them

## Contribute

1. Fork and clone
2. `nix develop` or just edit and test with `python3 ainix.py "..."`
3. Open a PR

Helpful first contributions:
- Generate and commit a `flake.lock` so install works without the flag:
  ```bash
  nix flake lock
  git add flake.lock
  ```
- Expand the knowledge base in `help/knowledge_base.py`
- Improve preview / dry-run behavior in `control/executor.py`
- Add tests

## Status

Early. Usable for help and preview. Do not rely on `--execute` for important system changes yet.
