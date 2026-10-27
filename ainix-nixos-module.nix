{ config, pkgs, lib, ... }:

with lib;

let
  cfg = config.services.ainix;

in {

  options.services.ainix = {
    enable = mkEnableOption "AINIX - local NixOS assistant";

    package = mkOption {
      type = types.package;
      default = pkgs.callPackage ./ainix-package.nix { };
      description = "AINIX package to use";
    };
  };

  config = mkIf cfg.enable {
    environment.systemPackages = [ cfg.package ];

    environment.shellAliases = {
      ainix = "${cfg.package}/bin/ainix";
    };
  };

  meta.maintainers = [ "AINIX Team" ];
}
