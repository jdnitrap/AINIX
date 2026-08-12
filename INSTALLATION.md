# AINIX Installation Guide

AINIX (AI-Native NixOS Integration) combines help and control layers into a unified system for NixOS management.

## Requirements

- NixOS 26.05 or compatible
- Python 3.8+
- Bash shell

## Installation Methods

### Method 1: Manual Installation (Development)

```bash
# Clone or navigate to gobook/ainix directory
cd ~/gobook/ainix

# Make scripts executable
chmod +x ainix.py
chmod +x tests/test_*.py

# Test the installation
python3 tests/test_router.py
python3 tests/test_executor.py
python3 tests/test_help.py
```

### Method 2: NixOS Module Installation

Add to your `configuration.nix`:

```nix
{
  services.ainix = {
    enable = true;
    enableNixQubesIntegration = true;
    enableLocalLearning = true;
    logLevel = "info";
  };
}
```

Then rebuild:
```bash
sudo nixos-rebuild switch
```

### Method 3: Flake Integration

Add to your `flake.nix`:

```nix
{
  description = "NixOS with AINIX";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }: {
    nixosConfigurations.default = nixpkgs.lib.nixosSystem {
      system = "x86_64-linux";
      modules = [
        ./configuration.nix
        ./ainix/ainix-nixos-module.nix
      ];
    };
  };
}
```

## Quick Start

### Basic Usage

```bash
# Ask for help
python3 ainix.py "How do I install a package?"

# Execute a command (preview mode)
python3 ainix.py install firefox

# Explain a command
python3 ainix.py --explain nixos-rebuild

# Use a specific container
python3 ainix.py --container dev "cargo build"
```

### Create an Alias

```bash
# Add to ~/.bashrc or ~/.zshrc
alias ainix='python3 ~/gobook/ainix/ainix.py'

# Then use directly
ainix "How do I...?"
ainix install firefox
```

## Configuration

### Edit Configuration

Edit `config/ainix.json` to customize:

- Execution modes (preview, dry-run, safe, execute)
- Container preferences
- Safety policies
- Learning preferences
- Logging levels

Example:
```json
{
  "execution": {
    "default_mode": "preview",
    "use_containers": true
  },
  "containers": {
    "preferred_container": "untrusted"
  }
}
```

### Load Custom Configuration

```bash
ainix --config /path/to/custom-config.json "your query"
```

## NixQubes Integration

AINIX automatically integrates with NixQubes containers:

```bash
# Execute in work container
ainix --container work install firefox

# Execute in dev container for development
ainix --container dev "cargo build"

# Execute in untrusted container for testing
ainix --container untrusted "test dangerous app"

# Execute in net container for networking
ainix --container net "curl https://example.com"
```

## Learning System

AINIX can learn from your usage patterns:

```bash
# Commands are logged to /var/lib/ainix/learning/
# Successful patterns are remembered
# Failed operations teach what to avoid
```

Enable learning in configuration:
```json
{
  "learning": {
    "enabled": true,
    "store_successful_commands": true,
    "learn_from_failures": true
  }
}
```

## Testing

Run the test suite:

```bash
cd ainix

# Test query routing
python3 tests/test_router.py

# Test command execution
python3 tests/test_executor.py

# Test knowledge base
python3 tests/test_help.py
```

## Troubleshooting

### Python Import Errors

```bash
# Make sure paths are correct
export PYTHONPATH="/home/user/gobook/ainix:$PYTHONPATH"
python3 ainix.py "test query"
```

### Container Not Found

```bash
# List available containers
qubesctl list

# Only these containers are available:
# - net (networking)
# - work (work environment)
# - dev (development)
# - untrusted (testing)
```

### Permission Denied

```bash
# Make scripts executable
chmod +x ainix.py

# Or run with python explicitly
python3 ainix.py "query"
```

## Integration with NixQubes

If using NixQubes for container isolation:

```bash
# AINIX automatically uses containers for dangerous operations
# Preview what would happen
ainix install firefox

# Execute in untrusted container
ainix --execute install firefox

# Build in dev container
ainix --container dev "cargo build" --execute
```

## Performance Tips

1. **First run** takes longer (initializes knowledge base)
2. **Preview mode** is instant (no actual execution)
3. **Container execution** has startup overhead (~2-5 seconds)
4. **Learning** improves over time as patterns are discovered

## Next Steps

1. ✅ Run the tests: `python3 tests/test_router.py`
2. ✅ Try basic queries: `ainix "How do I install Rust?"`
3. ✅ Integrate with NixOS: Add to `configuration.nix`
4. ✅ Customize configuration: Edit `config/ainix.json`
5. ✅ Enable learning: Set up `/var/lib/ainix/` directories

## Uninstallation

### Manual Installation

```bash
# Remove directory
rm -rf ~/gobook/ainix

# Remove alias from shell config
# Edit ~/.bashrc and remove 'alias ainix=...'
```

### NixOS Module

Remove from `configuration.nix`:
```nix
services.ainix.enable = false;
```

Then rebuild:
```bash
sudo nixos-rebuild switch
```

## Support & Feedback

For issues or suggestions:
1. Check knowledge base: `ainix "How do I...?"`
2. Read examples: `ainix --help`
3. Review logs: `tail -f /var/log/ainix/commands.log`

## Version

- **AINIX**: 0.1.0 (Development)
- **Compatible with**: NixOS 26.05+
- **Python**: 3.8+

## License

AINIX is part of the gobook project.
