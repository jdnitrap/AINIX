# AINIX Usage Examples

## Help Queries

### Example 1: Ask for Information
```bash
$ ainix "How do I install a package in NixOS?"

🤖 AINIX - Query Type: help
========================================
📚 Help System
----------------------------------------

📖 NIX-PACKAGE-MANAGEMENT
--------
NixOS provides multiple ways to manage packages:

1. System packages (in configuration.nix):
   environment.systemPackages = [ pkgs.firefox pkgs.git ];

2. Per-user packages (imperative, temporary):
   nix-env -i firefox

3. Nix shell (temporary environment):
   nix shell nixpkgs#firefox

4. Flake packages:
   nix run github:user/repo#package

Best practice: Define packages in configuration.nix for consistency.

💡 Examples:
  environment.systemPackages = with pkgs; [ firefox ];
  nix-env -i firefox
  nix shell nixpkgs#firefox
```

### Example 2: Explain a Command
```bash
$ ainix --explain nixos-rebuild switch

🤖 AINIX - Query Type: explain
========================================
🔍 EXPLANATION MODE
----------------------------------------
Command: nixos-rebuild
NixOS uses nixos-rebuild to activate configuration changes.

Main operations:
- build: Build the new configuration without activating
- switch: Build and activate the configuration
- boot: Build but only activate on next boot
- test: Build and activate, but not permanently (reverts on reboot)

Common usage:
  sudo nixos-rebuild switch        # Apply changes
  sudo nixos-rebuild boot          # Apply on next boot
  sudo nixos-rebuild test          # Test changes (revert on reboot)
  nixos-rebuild build              # Just build, don't activate
```

## Control Queries

### Example 3: Install a Package (Preview Mode)
```bash
$ ainix install firefox

🤖 AINIX - Query Type: control
========================================
⚙️  Control System
----------------------------------------
📋 Executing: install firefox

✅ PREVIEW
Would execute:
  install firefox

Breakdown:
  - Command: install
  - Arguments: firefox

----------------------------------------
To execute, use: --execute or -x
```

### Example 4: Execute with Confirmation
```bash
$ ainix install firefox --execute

🤖 AINIX - Query Type: control
========================================
⚙️  Control System
----------------------------------------
📋 Executing: install firefox

Executing in container 'untrusted':
install firefox

✅ SAFE
Command executed successfully.
```

### Example 5: Use Specific Container
```bash
$ ainix --container dev "cargo build"

🤖 AINIX - Query Type: control
========================================
⚙️  Control System
----------------------------------------
📋 Executing: cargo build
🔒 Container: dev

✅ PREVIEW
Would execute in container 'dev':
cargo build

Dev container includes: Git, Vim, build-essential, Rust, Node.js, Python3

----------------------------------------
To execute, use: --execute or -x
```

### Example 6: Dry Run (Show Side Effects)
```bash
$ ainix --dry-run update

🤖 AINIX - Query Type: control
========================================
⚙️  Control System
----------------------------------------
📋 Executing: update

✅ DRY-RUN
Would execute Nix operation: update

Changes that would be made:
  - Fetch latest nixpkgs
  - Evaluate new packages
  - Update flake.lock (if using flakes)

To apply these changes, use: --execute or -x
```

## Workflow Examples

### Safe Development Workflow
```bash
# 1. Get help on how to use dev container
ainix "How do I use the dev container?"

# 2. Preview what we'll build
ainix --container dev "cargo build"

# 3. Actually build it in isolation
ainix --container dev "cargo build" --execute

# 4. If something fails, get explanation
ainix --explain "cargo build error"
```

### Package Management Workflow
```bash
# 1. Learn about package management
ainix "What's the best way to install packages?"

# 2. Search for a package
ainix "search firefox"

# 3. Preview installation
ainix install firefox

# 4. Execute installation
ainix install firefox --execute

# 5. Check if it worked
ainix "Is firefox installed?"
```

### System Maintenance Workflow
```bash
# 1. Learn about nixos-rebuild
ainix --explain nixos-rebuild

# 2. Preview the rebuild
ainix --dry-run "nixos-rebuild switch"

# 3. Execute with testing first
ainix --container dev "nixos-rebuild switch"

# 4. If test passes, apply to system
ainix "nixos-rebuild switch" --execute
```

## Safety Features in Action

### Dangerous Operation Rejected
```bash
$ ainix "rm -rf /"

🤖 AINIX - Query Type: control
========================================
⚙️  Control System
----------------------------------------
❌ FAILED
Dangerous operation detected: rm

This operation cannot be executed for safety reasons.
Consider:
  1. Using 'nix-collect-garbage' for safe cleanup
  2. Using containers for testing deletions
  3. Checking what files are safe to remove

If you understand the risks, use: --unsafe-override
```

### Container Isolation
```bash
$ ainix --container untrusted "curl https://untrusted-source.com"

🤖 AINIX - Query Type: control
========================================
⚙️  Control System
----------------------------------------
📋 Executing: curl https://untrusted-source.com
🔒 Container: untrusted

✅ SAFE
Executed in isolated container.
- Container is ephemeral (auto-destroyed)
- Cannot access your main system
- Cannot see other containers
- Has limited network access
```

## Integration with Shell

Add to your shell configuration (`.bashrc`, `.zshrc`):

```bash
# AINIX shortcuts
alias ai=ainix
alias ai-help='ainix --explain'
alias ai-test='ainix --dry-run'
alias ai-safe='ainix --container untrusted'
```

Then use shortcuts:
```bash
ai "How do I...?"
ai-help nixos-rebuild
ai-test update
ai-safe "run untrusted command"
```
