# AINIX

A local assistant for NixOS. It helps a newcomer find the one file and the next edit, and it gives an advanced user the option name, the current line, and one official page.

Version 0.11.0.

It does not edit your config. A model is optional. It works without one.

## How it answers

AINIX sorts a line into a question or a command.

A command such as `ainix install firefox` or `ainix rebuild` does not search the web. It reads this machine's NixOS config and prints a preview.

A question takes the help path. The default is docs-first:

1. Built-in notes in `help/knowledge_base.py` for packages, rebuilds, flakes, generations, and Home Manager.
2. Nix on this computer. A dotted option goes to `nixos-option`. Anything else goes to `nix search nixpkgs`. Results are cached in `~/.local/share/ainix/`.
3. DuckDuckGo HTML search, with `nixos` added to the query, only if Nix found nothing and the machine is online.
4. Ollama, only if the three steps above miss. The prompt includes the layout, a short package-file excerpt when the question is about packages, the file hits, and any text already found. The model is told not to invent options or paths.

After that, AINIX reads the NixOS files on this machine.

- A how-to leads with plain words, the file to edit, and the rebuild command. The exact line and one [search.nixos.org](https://search.nixos.org/options) link follow.
- A question that names an option, or asks for a default or a type, leads with the file, the line, and that same link.

`search.nixos.org` is printed. That page is not downloaded.

## What it reads on this machine

The config directory is `/etc/nixos`, or `AINIX_NIXOS_CONFIG` if that is set. A `flake.nix` in the current directory is ignored.

| Layout | Install names | Rebuild prints |
|---|---|---|
| One `configuration.nix` | that file | `sudo nixos-rebuild switch` |
| Several modules | the file that assigns `environment.systemPackages` | `sudo nixos-rebuild switch` |
| A flake | the package file inside it | `sudo nixos-rebuild switch --flake <dir>#<name>` |

If several files assign `environment.systemPackages`, the main list is first. If a flake has several hosts and none matches `networking.hostName`, AINIX lists the names instead of inventing one.

Words in the question are matched to option names in those files. `ssh` matches `services.openssh`. `printer` matches `services.printing`. The module filenames can be anything. Each machine gets its own paths.

## Try it

```bash
ainix start
ainix "How do I enable ssh?"
ainix "services.openssh.enable default"
ainix "How do I install a package?"
ainix install firefox
ainix rebuild
ainix home
ainix --history
```

## Install

### Quick (curl)

On NixOS this uses `nix profile`. Elsewhere it uses a local install if Python is present.

```bash
curl -fsSL https://raw.githubusercontent.com/jdnitrap/AINIX/main/install.sh | bash
```

### Standalone flake

```bash
nix run github:jdnitrap/AINIX -- help
nix profile add github:jdnitrap/AINIX
```

### As an input in your system flake

```nix
{
  inputs.ainix.url = "github:jdnitrap/AINIX";

  outputs = { self, nixpkgs, ainix, ... }: {
    nixosConfigurations.yourhost = nixpkgs.lib.nixosSystem {
      modules = [
        ainix.nixosModules.default
        { services.ainix.enable = true; }
      ];
    };
  };
}
```

Then:

```bash
ainix start
```

## Optional local model

Model-first is off unless you turn it on. Docs stay first either way.

```bash
mkdir -p ~/.config/ainix
echo '{"model": "gemma2:9b", "model_first": true}' > ~/.config/ainix/config.json
```

One run:

```bash
ainix --model-first "How do I enable ssh?"
ainix --docs-first "How do I enable ssh?"
ainix --model gemma2:9b "How do I enable ssh?"
```

Ollama is the local model, for NVIDIA, AMD, or CPU:

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull gemma2:9b
```

## Uninstall

Nix profile:

```bash
nix profile remove AINIX
```

Curl install:

```bash
ainix uninstall
```

## More

- `ainix help` shows usage
- `man ainix` is the man page
- `ainix --version` prints the version
