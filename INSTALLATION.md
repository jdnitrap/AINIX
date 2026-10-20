# AINIX Installation

## On any NixOS machine (flake)

Add the input and enable the module:

```nix
# flake.nix
{
  inputs.ainix.url = "github:jdnitrap/AINIX";

  outputs = { self, nixpkgs, ainix, ... }:
  {
    nixosConfigurations.yourhost = nixpkgs.lib.nixosSystem {
      modules = [
        ainix.nixosModules.default
        ./configuration.nix
      ];
    };
  };
}
```

```nix
# configuration.nix
{
  services.ainix.enable = true;
}
```

Then rebuild.

## Run without installing

```bash
nix run github:jdnitrap/AINIX -- "How do I install a package?"
```

## Usage

```bash
ainix "How do I install a package?"
ainix install firefox          # preview by default
ainix --explain nixos-rebuild
ainix install firefox --execute
```
