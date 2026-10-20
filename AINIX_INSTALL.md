# AINIX Installation

See INSTALLATION.md and FLAKE_INSTALLATION.md for current instructions.

Quick try (once packaged as a flake):

```bash
nix run github:jdnitrap/AINIX -- "How do I install Rust?"
```

System enable:

```nix
services.ainix.enable = true;
```
