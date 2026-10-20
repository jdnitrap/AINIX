{ lib, python3, makeWrapper }:

python3.pkgs.buildPythonApplication {
  pname = "ainix";
  version = "0.1.0";
  pyproject = false;

  src = ./.;

  nativeBuildInputs = [ makeWrapper ];

  installPhase = ''
    mkdir -p $out/bin
    cp ainix.py $out/bin/ainix
    chmod +x $out/bin/ainix

    # Ship the supporting modules so the script can import them
    mkdir -p $out/lib/ainix
    cp -r core control help config $out/lib/ainix/

    wrapProgram $out/bin/ainix \
      --prefix PYTHONPATH : "$out/lib/ainix" \
      --set PYTHONUNBUFFERED 1
  '';

  doCheck = false;

  meta = with lib; {
    description = "AI-Native NixOS Integration - Help and Control for NixOS";
    homepage = "https://github.com/jdnitrap/AINIX";
    license = licenses.mit;
    maintainers = [ "AINIX Team" ];
    platforms = platforms.linux;
    mainProgram = "ainix";
  };
}
