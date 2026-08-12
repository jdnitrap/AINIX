# AINIX Flake Installation Guide

AINIX is now easily installable on any NixOS machine via Nix flakes!

## Quick Start (No Setup Required)

### Run AINIX Directly
```bash
# Run without installing (downloads on first use)
nix run github:jdnitrap/gobook#ainix -- "How do I install a package?"
nix run github:jdnitrap/gobook#ainix install firefox
nix run github:jdnitrap/gobook#ainix --explain nixos-rebuild
```

### Temporary Environment
```bash
# Get a temporary shell with AINIX available
nix shell github:jdnitrap/gobook#ainix

# Now use AINIX
ainix "How do I...?"
```

## System-Wide Installation

### Option 1: Using Flakes (Recommended)

Edit your `configuration.nix`:

```nix
{
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    gobook.url = "github:jdnitrap/gobook";
  };

  outputs = { self, nixpkgs, gobook }: {
    nixosConfigurations.default = nixpkgs.lib.nixosSystem {
      system = "x86_64-linux";
      modules = [
        ./configuration.nix
        gobook.nixosModules.ainix
      ];
    };
  };
}
```

In your `configuration.nix`:

```nix
{
  services.ainix = {
    enable = true;
    enableNixQubesIntegration = true;
  };
}
```

Then rebuild:
```bash
sudo nixos-rebuild switch
```

### Option 2: Manual System Installation

```bash
# Clone the repository
git clone https://github.com/jdnitrap/gobook.git
cd gobook

# Build the package
nix build

# Install globally
nix profile install ./

# Or add to current shell
nix shell ./
```

### Option 3: Home Manager Integration

In your Home Manager configuration:

```nix
{
  inputs.gobook.url = "github:jdnitrap/gobook";

  programs.ainix = {
    enable = true;
  };
}
```

Then rebuild home-manager:
```bash
home-manager switch
```

## Using AINIX

### After Installation

```bash
# Basic help query
ainix "How do I install Rust?"

# Execute a command (preview)
ainix install firefox

# Get explanation
ainix --explain nixos-rebuild

# Use containers
ainix --container dev "cargo build"

# Execute for real
ainix --execute install firefox
```

### Shell Aliases

Add to your shell config if not using Home Manager:

```bash
# ~/.bashrc or ~/.zshrc
alias ai=ainix
alias ai-help='ainix --explain'
alias ai-test='ainix --dry-run'
alias ai-safe='ainix --container untrusted'
```

## Flake Commands

### Available Commands

```bash
# Run AINIX
nix run github:jdnitrap/gobook#ainix -- "query"

# Enter development shell
nix flake show github:jdnitrap/gobook  # See available packages/apps
nix develop github:jdnitrap/gobook      # Dev environment

# Build the package
nix build github:jdnitrap/gobook#ainix

# Show package info
nix flake info github:jdnitrap/gobook
```

## Configuration

### Global Configuration

After installation, edit the config:

```bash
# System-wide
sudo nano /etc/ainix/ainix.json

# Or user-specific
mkdir -p ~/.config/ainix
cp /etc/ainix/ainix.json ~/.config/ainix/
nano ~/.config/ainix/ainix.json
```

### Via NixOS Module

```nix
services.ainix = {
  enable = true;
  
  settings = {
    execution.default_mode = "preview";
    execution.use_containers = true;
    containers.preferred_container = "untrusted";
    safety.enable_rollback = true;
    safety.log_commands = true;
  };
  
  enableNixQubesIntegration = true;
  enableLocalLearning = true;
  logLevel = "info";
};
```

## Local Development

### Work with Local Copy

```bash
# Clone and enter dev shell
git clone https://github.com/jdnitrap/gobook.git
cd gobook
nix flake update              # Update flake inputs
nix develop                   # Enter dev environment
```

### Run Tests

```bash
cd ainix
python3 tests/test_router.py
python3 tests/test_executor.py
python3 tests/test_help.py
```

### Build Locally

```bash
# Build the package locally
nix build .#ainix

# Run without installing
./result/bin/ainix "test query"
```

## Troubleshooting

### "Command not found" after installation

Try one of these:

```bash
# Add to PATH explicitly
export PATH="${PATH}:$(nix build --no-link --print-out-paths github:jdnitrap/gobook#ainix)/bin"

# Or use nix run
nix run github:jdnitrap/gobook#ainix

# Or reinstall
home-manager switch  # or
sudo nixos-rebuild switch
```

### Module not found

Ensure flake inputs are correct in your flake.nix:

```nix
inputs.gobook = {
  url = "github:jdnitrap/gobook";
  inputs.nixpkgs.follows = "nixpkgs";
};
```

### Permission denied

The AINIX module needs access to containers:

```bash
sudo usermod -aG container $USER
newgrp container
```

## Uninstallation

### Flake-based System

Remove from `configuration.nix`:

```nix
# Remove or comment out:
# gobook.nixosModules.ainix
# services.ainix.enable = true;
```

Then rebuild:

```bash
sudo nixos-rebuild switch
```

### Home Manager

Remove from home configuration:

```nix
# Remove:
# programs.ainix.enable = true;
```

Then:

```bash
home-manager switch
```

### Profile

```bash
nix profile remove github:jdnitrap/gobook#ainix
```

## Advanced: Using with NixQubes

If you have NixQubes containers set up, AINIX automatically integrates:

```bash
# Execute safely in dev container
ainix --container dev "cargo build" --execute

# Execute in work container
ainix --container work install firefox --execute

# Execute in untrusted for testing
ainix --container untrusted "test-app" --execute
```

## Publishing to NixPkgs

To get AINIX into nixpkgs:

1. Create PR to nixpkgs with pkgs/tools/nixos/ainix/default.nix
2. Reference this repository
3. Once merged, install with:

```bash
nix-env -iA nixpkgs.ainix
# or
environment.systemPackages = [ pkgs.ainix ];
```

## Support

### Get Help

```bash
# Show AINIX help
ainix --help

# Ask AINIX for help
ainix "How do I...?"

# Check documentation
nix flake show github:jdnitrap/gobook
```

### Report Issues

Issues with AINIX itself: https://github.com/jdnitrap/gobook/issues

## Summary

AINIX is now installable via:

| Method | Command | Notes |
|--------|---------|-------|
| Quick Try | `nix run github:jdnitrap/gobook#ainix -- "query"` | No install needed |
| Dev Shell | `nix shell github:jdnitrap/gobook#ainix` | Temporary |
| System-wide | Add to NixOS config | Persistent |
| Home Manager | `programs.ainix.enable = true` | Per-user |
| Local Build | `nix build .#ainix` | Development |

---

**Version**: 0.1.0  
**Flake Support**: ✅ Complete  
**Date**: July 23, 2026
