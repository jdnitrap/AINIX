# Install AINIX

## Recommended (no Nix, no clone)

```bash
curl -fsSL https://raw.githubusercontent.com/jdnitrap/AINIX/main/install.sh | bash
```

Then `ainix help`.

## Uninstall

```bash
ainix uninstall
```

## Optional: Nix profile

```bash
nix profile add github:jdnitrap/AINIX --no-write-lock-file
```

Remove with `nix profile remove AINIX`.
