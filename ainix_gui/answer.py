"""Turn a question or a command into the text the window shows.

Apply writes a line only after a separate confirmation. Switch and boot run
only after their own confirmation.
"""

import os
from contextlib import contextmanager


HELP_TEXT = """\
AINIX

A question asks your files, the manuals, nixpkgs at your revision, the wiki, Discourse, GitHub, and DuckDuckGo together. The answer cites the pieces that fit.

Examples:
  How do I enable ssh?
  How do I allow password authentication for openssh?

install, rebuild, home, and start only show a preview.
Nothing is edited. Nothing is built.
"""


@contextmanager
def config_env(config):
    previous = os.environ.get("AINIX_NIXOS_CONFIG")
    if config:
        os.environ["AINIX_NIXOS_CONFIG"] = config
    elif "AINIX_NIXOS_CONFIG" in os.environ:
        del os.environ["AINIX_NIXOS_CONFIG"]
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("AINIX_NIXOS_CONFIG", None)
        else:
            os.environ["AINIX_NIXOS_CONFIG"] = previous


def help_answer(question, config):
    from ainix_help.assemble import assemble
    from ainix_help.context import Context
    from ainix_help.search import search

    ctx = Context(question, config=config or "")
    hits, notes, names = search(ctx)
    return assemble(ctx, hits, notes, names)


def rebuild_preview(config):
    from core.nixos_layout import detect

    from ainix_help.plan import Answer, Plan, commands_from

    with config_env(config):
        layout = detect()
    plan = Plan()
    dry, switch, boot, names, needs_host = commands_from(layout)
    plan.dry_build = dry
    plan.switch = switch
    plan.boot = boot
    plan.flake_names = names
    plan.needs_host = needs_host
    lines = [
        f"Rebuild preview ({layout.style_label()})",
    ]
    if layout.root:
        lines.append(f"Config: {layout.root}")
    if layout.note:
        lines.extend(["", layout.note])
    lines.extend([
        "",
        "Dry-build, read-only:",
        f"  {dry}",
        "Switch, replaces the running system:",
        f"  {switch}",
        "Boot, next restart, leaves this session as it is:",
        f"  {boot}",
        "",
        "The Build button asks before it runs one of these. Nothing is edited.",
    ])
    return Answer("\n".join(lines), plan)


def command_preview(question, config):
    from core.nixos_layout import detect, valid_package_name

    parts = question.split()
    if parts and parts[0].lower() in ("install", "add") and len(parts) >= 2:
        package = parts[1]
        if not valid_package_name(package):
            return f"Not a package name: {package}"
        with config_env(config):
            return "\n".join(detect().install_preview(package))
    if parts and parts[0].lower() in ("rebuild", "rebuilds") and len(parts) == 1:
        return rebuild_preview(config)
    from control.executor import SafeExecutor

    text = "\n".join(SafeExecutor().preview_command(question))
    return (
        text
        + "\n\nThis was read as a command, so the sources were not searched."
        + " Phrase it as a question if you want a search."
    )


def answer_question(question, config=""):
    from core.router import QueryRouter, QueryType

    question = (question or "").strip()
    config = (config or "").strip()
    if not question:
        return ""
    if config and not os.path.isdir(config):
        return f"That configuration directory does not exist: {config}"
    from ainix_help.install_edit import install_question

    planned = install_question(question, config)
    if planned is not None:
        return planned
    lowered = question.lower()
    if lowered in ("help", "--help", "-h"):
        return HELP_TEXT
    if lowered == "start":
        from ainix import AINIX
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with config_env(config):
            with redirect_stdout(buf):
                AINIX(quiet=True).show_start()
        return buf.getvalue().strip()
    if lowered in ("home", "home-manager", "homemanager"):
        from ainix import AINIX
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with config_env(config):
            with redirect_stdout(buf):
                AINIX(quiet=True).show_home()
        return buf.getvalue().strip()
    if lowered in ("rebuild", "rebuilds"):
        return rebuild_preview(config)
    kind, _subject = QueryRouter.classify(question)
    if kind == QueryType.CONTROL:
        return command_preview(question, config)
    return help_answer(question, config)
