#!/usr/bin/env python3
"""A question goes to the search joiner. An install command stays a preview."""

import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import ainix
import ainix_help.search as search_mod
from ainix_help.search import Hit


class Args:
    execute = False
    yes = False


def test_question_uses_joiner():
    seen = {}
    original = search_mod.search

    def fake_search(ctx):
        seen["question"] = ctx.question
        return (
            [Hit("wiki", "SSH", "https://wiki.nixos.org/wiki/SSH", "services.openssh.enable = true;")],
            ["wiki: 1 pages"],
            ["services.openssh.enable"],
        )

    search_mod.search = fake_search
    try:
        buf = io.StringIO()
        with redirect_stdout(buf):
            ainix.AINIX().handle_query("How do I enable ssh?", Args())
        text = buf.getvalue()
    finally:
        search_mod.search = original
    assert seen["question"] == "How do I enable ssh?"
    assert "Question: How do I enable ssh?" in text
    assert "wiki: SSH" in text
    assert "Nothing was edited" in text
    assert "[docs-first]" not in text
    print("✓ a question uses the joiner")


def test_install_does_not_search():
    original = search_mod.search

    def fail_search(_ctx):
        raise AssertionError("install searched the web")

    search_mod.search = fail_search
    try:
        buf = io.StringIO()
        with redirect_stdout(buf):
            ainix.AINIX().handle_query("install firefox", Args())
        text = buf.getvalue()
    finally:
        search_mod.search = original
    assert "firefox" in text
    assert "Question:" not in text
    print("✓ install stays a preview")


if __name__ == "__main__":
    test_question_uses_joiner()
    test_install_does_not_search()
    print("question route tests passed")
