# AINIX

AINIX is a local helper for NixOS. Ask a question in ordinary language, and it looks through your configuration and the NixOS sources, then shows the line that fits. You can try it without installing anything else.

It is for a first NixOS setup and for someone who already knows the option names. A newcomer gets plain words and the next edit. Someone who names an option gets the file, the current line, and a source.

Version 0.11.0. It runs on `x86_64-linux` and `aarch64-linux`. The package follows NixOS 26.05 and brings Python 3.13 with it.

## What it does

A question such as "How do I enable ssh?" searches your files, the manuals, nixpkgs at your NixOS revision, the NixOS wiki, Discourse, GitHub, and DuckDuckGo. A learning question can include YouTube. The answer cites the pieces that match and prints a preview of the change.

A command does not search the web. It reads the NixOS configuration on this machine and prints what it would do.

```bash
ainix install firefox
ainix rebuild
ainix home
ainix start
ainix packages
```

The terminal does not edit a file and does not build. Add `--execute` only when you want a previewed command to run.

The window, `ainix-desktop`, asks the same questions. Apply writes the shown line only after you confirm. Build can then dry-build, switch the running system, or set the next boot. The window is GTK 4. It does not require GNOME.

## Try it

One question, without adding AINIX to your profile:

```bash
nix run github:jdnitrap/AINIX -- "How do I enable ssh?"
```

The window:

```bash
nix run github:jdnitrap/AINIX#desktop
```

## Install

```bash
nix profile add github:jdnitrap/AINIX
```

Then:

```bash
ainix "How do I enable ssh?"
ainix "services.openssh.enable default"
ainix "How do I install a package?"
ainix-desktop
```

To add AINIX to a NixOS flake, see [FLAKE_INSTALLATION.md](FLAKE_INSTALLATION.md).

```nix
inputs.ainix.url = "github:jdnitrap/AINIX";
```

```nix
imports = [ inputs.ainix.nixosModules.default ];

services.ainix.enable = true;
```

## How it works

AINIX sorts each line into a question or a command.

A question gathers the sources above and keeps the pieces that share the same option. `ssh` matches `services.openssh`. `printer` matches `services.printing`. The answer leads with your file when that file already sets the option, then the suggested line and the pages that agree. `search.nixos.org` is named in the answer. That page is not downloaded.

A command reads the configuration and stops at a preview.

| Layout | Where packages are named | What `ainix rebuild` prints |
|---|---|---|
| One `configuration.nix` | that file | `sudo nixos-rebuild switch` |
| Several modules | the file that assigns `environment.systemPackages` | `sudo nixos-rebuild switch` |
| A flake | the package file inside it | `sudo nixos-rebuild switch --flake <dir>#<name>` |

The configuration directory is `/etc/nixos`, or `AINIX_NIXOS_CONFIG` if that is set. A `flake.nix` in the current directory is ignored. If several files assign `environment.systemPackages`, the main list is first. If a flake has several hosts and none matches `networking.hostName`, AINIX lists the names instead of inventing one.

Search results are cached in `~/.local/share/ainix/`.

A local model is optional. Docs stay first unless you turn model-first on.

```bash
mkdir -p ~/.config/ainix
printf '%s\n' '{"model": "gemma2:9b", "model_first": true}' > ~/.config/ainix/config.json
```

Ollama is the local model. AINIX does not install it.

```bash
ainix --model-first "How do I enable ssh?"
ainix --docs-first "How do I enable ssh?"
```

## Problems

If something fails, or the answer is wrong, open an issue:

https://github.com/jdnitrap/AINIX/issues

Include the command you ran, the NixOS version (`nixos-version`), and the output AINIX printed. A configuration snippet helps when the question is about your files. Leave passwords and secrets out.

## Uninstall

```bash
nix profile remove AINIX
```

`ainix help` lists the commands. `man ainix` is the manual page.
