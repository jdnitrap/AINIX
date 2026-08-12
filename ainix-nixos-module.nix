{ config, pkgs, lib, ... }:

with lib;

let
  cfg = config.services.ainix;
  configFile = pkgs.writeText "ainix-config.json" (builtins.toJSON cfg.settings);

in {

  options.services.ainix = {
    enable = mkEnableOption "AINIX - AI-Native NixOS Integration";

    package = mkOption {
      type = types.package;
      default = pkgs.callPackage ./ainix-package.nix { };
      description = "AINIX package to use";
    };

    settings = mkOption {
      type = types.attrs;
      default = {
        execution.default_mode = "preview";
        execution.require_approval = true;
        execution.use_containers = true;
        containers.enabled = true;
        safety.enable_rollback = true;
        safety.log_commands = true;
      };
      description = "AINIX configuration settings";
    };

    enableNixQubesIntegration = mkOption {
      type = types.bool;
      default = true;
      description = "Enable integration with NixQubes containers";
    };

    enableLocalLearning = mkOption {
      type = types.bool;
      default = true;
      description = "Enable local learning from commands";
    };

    logLevel = mkOption {
      type = types.enum [ "debug" "info" "warn" "error" ];
      default = "info";
      description = "Log level for AINIX";
    };
  };

  config = mkIf cfg.enable {
    environment.systemPackages = [ cfg.package ] ++ (if cfg.enableNixQubesIntegration then [ ] else [ ]);

    # Create AINIX directories
    systemd.tmpfiles.rules = mkIf cfg.enableLocalLearning [
      "d /var/lib/ainix 0755 root root -"
      "d /var/lib/ainix/learning 0755 root root -"
      "d /var/log/ainix 0755 root root -"
    ];

    # Optional: Create a service for AINIX daemon
    # This could provide additional features like background learning
    systemd.services.ainix = mkIf cfg.enableLocalLearning {
      description = "AINIX Background Service";
      after = [ "network-online.target" ];
      wants = [ "network-online.target" ];
      wantedBy = [ "multi-user.target" ];

      script = ''
        ${cfg.package}/bin/ainix-daemon --config ${configFile}
      '';

      serviceConfig = {
        Type = "simple";
        Restart = "on-failure";
        RestartSec = 10;
        StandardOutput = "journal";
        StandardError = "journal";
      };
    };

    # Shell alias for easier access
    environment.shellAliases = {
      ainix = "${cfg.package}/bin/ainix";
    };

    # Integration with NixQubes if available
    nixqubes.containerIntegration = mkIf cfg.enableNixQubesIntegration {
      ainixContainer = {
        enable = true;
        defaultContainer = "untrusted";
        allowedContainers = [ "work" "dev" "untrusted" ];
      };
    };
  };

  meta.maintainers = [ "AINIX Team" ];
}
