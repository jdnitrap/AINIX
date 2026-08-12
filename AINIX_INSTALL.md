# AINIX Installation: 4 Ways to "Poof" It Into NixOS

AINIX can now be installed on **any NixOS machine** with zero configuration. Here are all the ways:

## 1️⃣ Try It Instantly (No Install)

```bash
# Run AINIX directly from GitHub (downloads automatically)
nix run github:jdnitrap/gobook#ainix -- "How do I install Rust?"
nix run github:jdnitrap/gobook#ainix install firefox
nix run github:jdnitrap/gobook#ainix --explain nixos-rebuild
```

**Perfect for:** Testing before installing, one-off queries

---

## 2️⃣ Temporary Shell (Just This Session)

```bash
# Open a shell with AINIX available
nix shell github:jdnitrap/gobook#ainix

# Now use it like normal
ainix "How do I...?"
ainix install firefox
```

**Perfect for:** Quick work, doesn't touch system

---

## 3️⃣ System-Wide Installation (Permanent)

### Edit `/etc/nixos/flake.nix`:

```nix
{
  description = "My NixOS system with AINIX";

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

### Then in `/etc/nixos/configuration.nix`:

```nix
{
  services.ainix = {
    enable = true;
    enableNixQubesIntegration = true;
    enableLocalLearning = true;
  };
}
```

### Rebuild:

```bash
sudo nixos-rebuild switch
```

**Perfect for:** Permanent, system-wide availability, NixQubes integration

---

## 4️⃣ Home Manager Installation (Per-User)

### In your `home.nix`:

```nix
{
  programs.ainix = {
    enable = true;
  };
}
```

### Rebuild:

```bash
home-manager switch
```

**Perfect for:** Per-user setup, without system privileges

---

## 🚀 Quick Reference Table

| Use Case | Command | Pros | Cons |
|----------|---------|------|------|
| **Try it now** | `nix run github:jdnitrap/gobook#ainix -- "query"` | Instant, no install | Slower (downloads each time) |
| **This session** | `nix shell github:jdnitrap/gobook#ainix` | Fast, safe | Only this shell |
| **System-wide** | Flake + config rebuild | Permanent, integrated | Needs config changes |
| **Per-user** | Home Manager | Clean, per-user | Requires Home Manager |

---

## 📋 Usage After Installation

Once installed (any method):

```bash
# Help queries (advisory)
ainix "How do I install Rust?"
ainix "What's the difference between nix-env and configuration.nix?"

# Control queries (execution - preview first)
ainix install firefox
ainix update
ainix rebuild system

# Explanations
ainix --explain nixos-rebuild
ainix --explain "nix search"

# Container execution (if NixQubes available)
ainix --container dev "cargo build"
ainix --container work "firefox"
ainix --container untrusted "test-app"

# Execution
ainix install firefox --execute
ainix --container dev "cargo build" --execute

# Dry run (simulate without executing)
ainix --dry-run update
```

---

## 🔧 Advanced: Local Development

```bash
# Clone gobook
git clone https://github.com/jdnitrap/gobook.git
cd gobook

# Enter development environment
nix develop

# Run AINIX directly
python3 ainix/ainix.py "query"

# Run tests
cd ainix
python3 tests/test_router.py
python3 tests/test_executor.py
python3 tests/test_help.py
```

---

## ⚡ Shell Aliases (Optional)

Add to `~/.bashrc` or `~/.zshrc`:

```bash
# Quick access aliases
alias ai=ainix
alias ai-help='ainix --explain'
alias ai-test='ainix --dry-run'
alias ai-safe='ainix --container untrusted'

# Usage:
# ai "How do I...?"
# ai-help nixos-rebuild
# ai-test update
# ai-safe "run untrusted app"
```

---

## 🎯 Real-World Examples

### Example 1: Learn then Do
```bash
# First, understand what nixos-rebuild does
ainix --explain nixos-rebuild

# Preview the changes
ainix "nixos-rebuild switch"

# Actually do it
ainix "nixos-rebuild switch" --execute
```

### Example 2: Safe Development
```bash
# Use dev container for building
ainix --container dev "cargo build"

# Execute in isolation
ainix --container dev "cargo build" --execute
```

### Example 3: Test Untrusted App
```bash
# Run in ephemeral untrusted container
ainix --container untrusted "unknown-app"
```

---

## ✅ Verification

After installation, verify it works:

```bash
# Try basic queries
ainix "What is NixOS?"

# Try control queries
ainix install sl

# Try explanations
ainix --explain nixos-rebuild

# Show help
ainix --help
```

All should work without errors!

---

## 🔄 Uninstallation

### System-wide (NixOS)
Remove from `configuration.nix` and rebuild:
```bash
sudo nixos-rebuild switch
```

### Home Manager
Remove from `home.nix` and rebuild:
```bash
home-manager switch
```

### Flake Profile
```bash
nix profile remove github:jdnitrap/gobook#ainix
```

---

## 📚 Documentation

- **FLAKE_INSTALLATION.md**: Detailed flake setup guide
- **README.md**: Project overview
- **ARCHITECTURE.md**: Technical architecture
- **INSTALLATION.md**: Original installation guide
- **examples/basic-usage.md**: Usage examples

---

## 🎉 Summary

AINIX is now **truly installable** on any NixOS system:

✅ Try instantly without installing  
✅ Install temporarily for a session  
✅ Install system-wide via flakes  
✅ Install per-user via Home Manager  
✅ Work offline after first install  
✅ No complex setup required  

**Pick your favorite method and run `nix run github:jdnitrap/gobook#ainix`!**

---

**Version**: 0.1.0  
**Status**: ✅ Production Ready  
**Date**: July 23, 2026
