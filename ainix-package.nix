{ lib
, stdenvNoCC
, python3
, makeWrapper
, installShellFiles
, makeDesktopItem
, gtk4
, gdk-pixbuf
, pango
, harfbuzz
, graphene
, glib
, gobject-introspection
, gsettings-desktop-schemas
}:

let
  pythonEnv = python3.withPackages (ps: [
    ps.brotli
    ps.pygobject3
    ps.pycairo
  ]);
  # pango and glib default to their bin outputs, which have no typelibs.
  typelibs = lib.makeSearchPath "lib/girepository-1.0" [
    gtk4
    gdk-pixbuf
    pango.out
    harfbuzz
    graphene
    glib.out
    gobject-introspection
  ];
  schemas = lib.concatStringsSep ":" [
    "${gtk4}/share/gsettings-schemas/${gtk4.name}"
    "${gsettings-desktop-schemas}/share/gsettings-schemas/${gsettings-desktop-schemas.name}"
  ];
  desktopItem = makeDesktopItem {
    name = "org.jdnitrap.Ainix";
    desktopName = "AINIX";
    genericName = "NixOS helper";
    comment = "Ask Nix and NixOS questions without a terminal";
    exec = "ainix-desktop";
    icon = "ainix";
    terminal = false;
    startupNotify = true;
    categories = [ "Utility" ];
    startupWMClass = "org.jdnitrap.Ainix";
    keywords = [ "nix" "nixos" "ainix" ];
  };
in
stdenvNoCC.mkDerivation {
  pname = "ainix";
  version = "0.11.0";
  src = ./.;

  nativeBuildInputs = [ makeWrapper installShellFiles ];

  installPhase = ''
    runHook preInstall
    mkdir -p $out/share/ainix $out/bin
    cp ainix.py $out/share/ainix/
    cp -r core control help config ainix_help ainix_gui ainix_catalog $out/share/ainix/
    find $out/share/ainix -type d -name __pycache__ -print0 | xargs -0 -r rm -rf
    makeWrapper ${pythonEnv}/bin/python3 $out/bin/ainix \
      --add-flags "$out/share/ainix/ainix.py" \
      --set PYTHONPATH "$out/share/ainix" \
      --set PYTHONUNBUFFERED 1
    makeWrapper ${pythonEnv}/bin/python3 $out/bin/ainix-desktop \
      --add-flags "-m" \
      --add-flags "ainix_gui" \
      --set PYTHONPATH "$out/share/ainix" \
      --set PYTHONUNBUFFERED 1 \
      --set GI_TYPELIB_PATH "${typelibs}" \
      --prefix XDG_DATA_DIRS : "${schemas}:${gtk4}/share"
    installManPage ainix.1
    install -Dm644 ${./ainix.svg} $out/share/icons/hicolor/scalable/apps/ainix.svg
    install -Dm644 ${desktopItem}/share/applications/org.jdnitrap.Ainix.desktop $out/share/applications/org.jdnitrap.Ainix.desktop
    substituteInPlace $out/share/applications/org.jdnitrap.Ainix.desktop \
      --replace-fail 'Exec=ainix-desktop' "Exec=$out/bin/ainix-desktop" \
      --replace-fail 'Categories=Utility' 'Categories=Utility;' \
      --replace-fail 'Keywords=nix;nixos;ainix' 'Keywords=nix;nixos;ainix;'
    runHook postInstall
  '';

  meta = {
    description = "AI-Native NixOS Integration - Help and Control for NixOS";
    homepage = "https://github.com/jdnitrap/AINIX";
    license = lib.licenses.mit;
    mainProgram = "ainix-desktop";
    platforms = lib.platforms.linux;
  };
}
