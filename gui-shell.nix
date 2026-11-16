# Isolated shell for the AINIX window. It is not installed on the system.
{ pkgs ? import <nixpkgs> { } }:
let
  pythonEnv = pkgs.python3.withPackages (ps: [
    ps.pygobject3
    ps.pycairo
    ps.brotli
  ]);
  typelibs = pkgs.lib.makeSearchPath "lib/girepository-1.0" [
    pkgs.gtk4
    pkgs.gdk-pixbuf
    pkgs.pango
    pkgs.harfbuzz
    pkgs.graphene
    pkgs.glib
    pkgs.gobject-introspection
  ];
  schemas = pkgs.lib.concatStringsSep ":" [
    "${pkgs.gtk4}/share/gsettings-schemas/${pkgs.gtk4.name}"
    "${pkgs.gsettings-desktop-schemas}/share/gsettings-schemas/${pkgs.gsettings-desktop-schemas.name}"
  ];
in
pkgs.mkShell {
  packages = [
    pythonEnv
    pkgs.gtk4
    pkgs.gobject-introspection
    pkgs.cacert
  ];
  shellHook = ''
    export SSL_CERT_FILE="${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt"
    export GI_TYPELIB_PATH="${typelibs}''${GI_TYPELIB_PATH:+:$GI_TYPELIB_PATH}"
    export XDG_DATA_DIRS="${schemas}:${pkgs.gtk4}/share''${XDG_DATA_DIRS:+:$XDG_DATA_DIRS}"
    if [ -f "$PWD/ainix.py" ] && [ -d "$PWD/ainix_help" ]; then
      export AINIX_ROOT="$PWD"
    else
      echo "ainix: start the window from the AINIX checkout." >&2
    fi
    export PYTHONPATH="$AINIX_ROOT''${PYTHONPATH:+:$PYTHONPATH}"
    export PATH="$AINIX_ROOT/bin''${PATH:+:$PATH}"
  '';
}
