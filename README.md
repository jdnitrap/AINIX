# AINIX

Local NixOS assistant. Preview by default.

## Install without nix profile

```bash
git clone https://github.com/jdnitrap/AINIX.git
cd AINIX
./install.sh
```

Then:

```bash
ainix help
ainix --version
```

Remove by deleting `~/.local/bin/ainix` and `~/.local/share/ainix`.

## Or run once (no install)

```bash
nix run github:jdnitrap/AINIX --no-write-lock-file -- help
```

## Or with nix profile (optional)

```bash
nix profile add github:jdnitrap/AINIX --no-write-lock-file
```

## Usage

```bash
ainix help
ainix "How do I install a package?"
ainix install firefox
ainix code "enable openssh"
man ainix
```
