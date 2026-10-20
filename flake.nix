{
  description = "AINIX - AI-Native NixOS Integration (Help + Control assistant)";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
      in {
        packages.default = pkgs.callPackage ./ainix-package.nix { };
        packages.ainix = self.packages.${system}.default;

        apps.default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/ainix";
        };
      }
    ) // {
      nixosModules.default = import ./ainix-nixos-module.nix;
      nixosModules.ainix = self.nixosModules.default;
    };
}
