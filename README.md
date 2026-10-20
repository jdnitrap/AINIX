# AINIX

Local NixOS assistant. Preview by default.

## Install (no Nix required)

```bash
git clone https://github.com/jdnitrap/AINIX.git
cd AINIX
./install.sh
```

That puts `ainix` in `~/.local/bin`. No `nix profile`, no `nix run`.

Make sure `~/.local/bin` is on your PATH, then:

```bash
ainix help
ainix --version
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

## Optional: Nix install

Only if you prefer Nix:

```bash
nix profile add github:jdnitrap/AINIX --no-write-lock-file
```
