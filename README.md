# AINIX

Local NixOS assistant. Preview by default.

## Install (no clone, no Nix)

```bash
curl -fsSL https://raw.githubusercontent.com/jdnitrap/AINIX/main/install.sh | bash
```

That downloads the files and puts `ainix` in `~/.local/bin`.
No git clone, no `nix profile`, no `nix run`.

Make sure `~/.local/bin` is on your PATH, then:

```bash
ainix help
```

## Remove

```bash
rm ~/.local/bin/ainix
rm -rf ~/.local/share/ainix
```

## Usage

```bash
ainix help
ainix "How do I install a package?"
ainix install firefox
ainix code "enable openssh"
man ainix
```
