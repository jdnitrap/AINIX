{
  description = "AINIX - AI-Native NixOS Integration (Help + Control assistant)";

  inputs = {
    # NixOS 26.05. flake.lock pins the revision so every install gets the same
    # Python 3.13.
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachSystem [ "x86_64-linux" "aarch64-linux" ] (system:
      let
        pkgs = import nixpkgs { inherit system; };
      in {
        packages.default = pkgs.callPackage ./ainix-package.nix { };
        packages.ainix = self.packages.${system}.default;

        apps.default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/ainix-desktop";
        };
        apps.cli = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/ainix";
        };

        devShells.default = import ./shell.nix { inherit pkgs; };
        devShells.gui = import ./gui-shell.nix { inherit pkgs; };
      }
    ) // {
      nixosModules.default = import ./ainix-nixos-module.nix;
      nixosModules.ainix = self.nixosModules.default;
    };
}
