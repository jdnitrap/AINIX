# AINIX Flake Installation

## Run directly

```bash
nix run github:jdnitrap/AINIX -- "How do I install a package?"
```

## Add to your flake

```nix
inputs.ainix.url = "github:jdnitrap/AINIX";

# then in modules:
ainix.nixosModules.default   # or the path to ainix-nixos-module.nix
```

```nix
services.ainix = {
  enable = true;
  enableLocalLearning = true;
};
```

## Local development

```bash
git clone https://github.com/jdnitrap/AINIX.git
cd AINIX
python3 ainix.py "query"
python3 tests/test_router.py
```
