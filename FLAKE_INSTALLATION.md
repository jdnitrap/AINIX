# AINIX Flake Installation

AINIX follows NixOS 26.05. `flake.lock` pins the Nixpkgs revision, and the package brings its own Python 3.13. You do not install Python first.

Works on `x86_64-linux` and `aarch64-linux`.

## Install from the repo

```bash
nix profile add github:jdnitrap/AINIX
```

That installs the window. AINIX appears in the application menu. The terminal helper is the `ainix` command, for anyone who wants it.

## Run the window without installing

```bash
nix run github:jdnitrap/AINIX
```

The terminal helper:

```bash
nix run github:jdnitrap/AINIX#cli -- "How do I enable ssh?"
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
