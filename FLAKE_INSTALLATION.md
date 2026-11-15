# AINIX Flake Installation

AINIX follows NixOS 26.05. `flake.lock` pins the Nixpkgs revision, and the package brings its own Python 3.13. You do not install Python first.

Works on `x86_64-linux` and `aarch64-linux`.

## Install from the repo

```bash
nix profile add github:jdnitrap/AINIX
```

`ainix` is the terminal helper. `ainix-desktop` opens the window.

## Run without installing

```bash
nix run github:jdnitrap/AINIX -- "How do I enable ssh?"
```

The window:

```bash
nix run github:jdnitrap/AINIX#desktop
```

## Add the module to a NixOS flake

```nix
inputs.ainix.url = "github:jdnitrap/AINIX";
```

```nix
imports = [ inputs.ainix.nixosModules.default ];

services.ainix.enable = true;
```

That adds `ainix` and `ainix-desktop` to the system packages.
