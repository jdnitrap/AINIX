{ pkgs ? import <nixpkgs> { } }:
pkgs.mkShell {
  packages = [
    (pkgs.python3.withPackages (ps: [ ps.brotli ]))
    pkgs.cacert
  ];
  shellHook = ''
    export SSL_CERT_FILE="${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt"
    if [ -f "$PWD/ainix.py" ] && [ -d "$PWD/ainix_help" ]; then
      export AINIX_ROOT="$PWD"
    else
      echo "ainix: start nix-shell from the AINIX checkout." >&2
    fi
    export PYTHONPATH="$AINIX_ROOT''${PYTHONPATH:+:$PYTHONPATH}"
    export PATH="$AINIX_ROOT/bin''${PATH:+:$PATH}"
  '';
}
