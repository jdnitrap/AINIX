# AINIX Installation Guide

## Requirements

- NixOS (recent)
- Python 3.8+

## NixOS Module

Add the module to your flake and enable it:

```nix
services.ainix = {
  enable = true;
  enableLocalLearning = true;
  logLevel = "info";
};
```

Then rebuild.

## Direct / Development

```bash
git clone https://github.com/jdnitrap/AINIX.git
cd AINIX
python3 ainix.py "How do I install a package?"
```

## Usage

```bash
ainix "How do I install a package?"
ainix install firefox          # preview by default
ainix --explain nixos-rebuild
ainix install firefox --execute
```

## Configuration

Edit `config/ainix.json` or `~/.config/ainix/ainix.json` for execution mode, safety, and learning preferences.

## Testing

```bash
python3 tests/test_router.py
python3 tests/test_executor.py
python3 tests/test_help.py
```
