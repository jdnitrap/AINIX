# AINIX Installation

## Per-user (no config changes)

```bash
nix profile add github:jdnitrap/AINIX --no-write-lock-file
```

(`install` is a deprecated alias for `add`.)

Remove later with:
```bash
nix profile remove ainix
```

## One-shot

```bash
nix run github:jdnitrap/AINIX --no-write-lock-file -- "How do I install a package?"
```

## System-wide (flake)

```nix
inputs.ainix.url = "github:jdnitrap/AINIX";
# then
ainix.nixosModules.default
services.ainix.enable = true;
```

## Why --no-write-lock-file

The repo has no committed flake.lock yet. Nix tries to write one on install and fails on a remote flake. The flag skips that.
