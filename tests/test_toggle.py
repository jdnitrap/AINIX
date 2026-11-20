"""The one documentation toggle finds the line and builds a switch plan."""

import tempfile
from pathlib import Path

from ainix_gui.toggle import documentation_plan, find_documentation_enable


def test_nested_module_line():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        module = root / "modules"
        module.mkdir()
        (module / "system-setup.nix").write_text(
            "{\n  documentation.nixos.enable = false;\n}\n"
        )
        (root / "configuration.nix").write_text("{ imports = [ ./modules/system-setup.nix ]; }\n")
        edit = find_documentation_enable(root)
        assert edit is not None
        assert edit.line == 2
        assert edit.old_value == "false"
        plan = documentation_plan(root, "true")
        assert plan.edits[0].new_value == "true"
        assert plan.switch.startswith("sudo nixos-rebuild switch")
        assert documentation_plan(root, "false") is None


if __name__ == "__main__":
    test_nested_module_line()
    print("ok")
