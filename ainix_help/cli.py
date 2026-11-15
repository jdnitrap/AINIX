"""Command line for the isolated AINIX search helper."""

import argparse
import sys

from ainix_help.assemble import assemble
from ainix_help.context import Context
from ainix_help.search import Hit, enable_definitions, search, wiki_block, word_hit


def self_test():
    ctx = Context("how do I enable ssh", config="/etc/nixos")
    ctx.terms = ["enable", "ssh"]
    ctx.wants_enable = True
    ctx.release = "26.05"
    ctx.version = "26.05.test"
    hits = [
        Hit("your files", "configuration.nix:39", "/etc/nixos/configuration.nix", 'programs.ssh.askPassword = lib.mkForce "${pkgs.seahorse}/libexec/seahorse/ssh-askpass";'),
        Hit("your files", "networking.nix:20", "/etc/nixos/modules/networking.nix", "services.openssh.enable = false;"),
        Hit("wiki", "SSH", "https://wiki.nixos.org/wiki/SSH", "services.openssh.enable = true;"),
        Hit("discourse", "old name", "https://discourse.nixos.org/t/old/1", "services.openssh.enable = true;"),
        Hit("github nixpkgs", "unrelated", "https://github.com/NixOS/nixpkgs/issues/1", "services.nginx.enable = true;"),
        Hit("github nixpkgs", "gcr-ssh-agent", "https://github.com/NixOS/nixpkgs/issues/9", "services.gnome.gcr-ssh-agent = true;"),
    ]
    text = assemble(ctx, hits, ["wiki: 1 pages", "discourse: 1 posts"], ["services.openssh.enable"])
    checks = [
        "services.openssh.enable to false" in text,
        "Suggested change" in text,
        "services.openssh.enable = true;" in text,
        "Nothing was edited" in text,
        "nginx" not in text,
        "gcr-ssh-agent" not in text,
        "wiki: SSH" in text,
    ]
    sample = [
        "services.openssh = {",
        "  enable = lib.mkOption {",
        "    type = lib.types.bool;",
        "    default = false;",
        "  };",
        "};",
        "services.endlessh-go = {",
        "  enable = lib.mkOption { default = false; };",
        "};",
    ]
    defined = enable_definitions(sample, ["ssh", "openssh", "sshd"])
    checks.append(len(defined) == 1 and "services.openssh.enable" in defined[0][1] and "default = false" in defined[0][1])
    checks.append(word_hit("services.openssh.enable = false;", ["ssh", "openssh", "sshd"]))
    checks.append(not word_hit("services.endlessh-go.enable = true;", ["ssh", "openssh", "sshd"]))
    page = [
        "services.openssh = {",
        "  enable = true;",
        "  openFirewall = true;",
        "  settings = {",
        "    PasswordAuthentication = false;",
        "    AllowUsers = [ \"myUser\" ];",
        "  };",
        "};",
        "services.endlessh-go.enable = true;",
    ]
    detail = wiki_block(page, ctx)
    checks.append(detail.startswith("services.openssh.enable = true;"))
    checks.append("AllowUsers" in detail and "endlessh" not in detail)
    weak = Context("zzzz-not-a-real-topic", config="")
    weak.terms = ["zzzz-not-a-real-topic"]
    weak_text = assemble(weak, [Hit("wiki", "nothing", "https://example.com", "unrelated words")], ["wiki: 1 pages"], [])
    checks.append("No solid match." in weak_text)
    failed = [index for index, ok in enumerate(checks, 1) if not ok]
    if failed:
        print(text)
        print("self-test failed:", failed)
        return 1
    print("self-test passed")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="ainix_help",
        description="Search Nix and NixOS sources together and join the pieces that fit.",
    )
    parser.add_argument("question", nargs="*", help="What you are trying to learn or fix")
    parser.add_argument("--config", default="", help="NixOS configuration directory")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test()
    question = " ".join(args.question).strip()
    if not question:
        parser.print_help()
        return 2
    ctx = Context(question, config=args.config)
    hits, notes, names = search(ctx)
    sys.stdout.write(assemble(ctx, hits, notes, names))
    sys.stdout.write("\n")
    return 0
