{ lib, python3, makeWrapper, fetchurl }:

python3.pkgs.buildPythonApplication {
  pname = "ainix";
  version = "0.1.0";
  pyproject = true;

  src = ./.;

  nativeBuildInputs = [
    python3.pkgs.flit-core
    makeWrapper
  ];

  propagatedBuildInputs = with python3.pkgs; [
    # AINIX has no external Python dependencies beyond stdlib
  ];

  postInstall = ''
    # Create bin directory
    mkdir -p $out/bin

    # Install main script
    cp ainix.py $out/bin/ainix
    chmod +x $out/bin/ainix

    # Wrap with Python and PYTHONPATH
    wrapProgram $out/bin/ainix \
      --prefix PYTHONPATH : "$out/lib/python${python3.version}/site-packages" \
      --set PYTHONUNBUFFERED 1
  '';

  # Configuration files
  postInstall_config = ''
    mkdir -p $out/etc/ainix
    cp config/ainix.json $out/etc/ainix/ainix.json
  '';

  # Help files
  postInstall_docs = ''
    mkdir -p $out/share/doc/ainix
    cp README.md $out/share/doc/ainix/
    cp ARCHITECTURE.md $out/share/doc/ainix/
    cp INSTALLATION.md $out/share/doc/ainix/
    cp examples/basic-usage.md $out/share/doc/ainix/
  '';

  doCheck = false;

  meta = with lib; {
    description = "AI-Native NixOS Integration - Help and Control for NixOS";
    longDescription = ''
      AINIX combines an intelligent help system with safe command execution
      to provide a unified interface for NixOS management. It automatically
      classifies queries as advice-seeking or command-execution requests
      and routes them appropriately.

      Features:
      - Automatic query classification (help vs control)
      - Safe command execution with guardrails
      - NixQubes container integration
      - Comprehensive knowledge base
      - Dangerous operation detection
    '';
    homepage = "https://github.com/jdnitrap/gobook";
    license = licenses.mit;
    maintainers = [ "AINIX Team" ];
    platforms = platforms.linux;
    mainProgram = "ainix";
  };
}
