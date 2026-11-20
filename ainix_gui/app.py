"""AINIX window. Ask a question, then apply the shown line if you confirm."""

import sys
import threading

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from ainix_gui.answer import answer_question
from ainix_gui.changes import ApplyError, apply_edits, run_rebuild, sudo_needs_password
from ainix_gui.packages import PackagesPanel
from ainix_gui.toggle import OPTION, documentation_plan, find_documentation_enable
from ainix_help.context import config_root
from ainix_help.plan import button_state
from ainix_help.search import plain_bool


INTRO = """\
Ask a question in ordinary language.

  How do I enable ssh?
  How do I allow password authentication for openssh?

Apply writes only the line in the answer, and only after you confirm. A dry-build runs next. Switch replaces the running system. Boot builds the next startup and leaves this session as it is.
"""


def open_choice(parent, heading, body, responses, on_choice, extra=None, default="cancel"):
    """Modal GTK dialog. responses are (name, label, style). style is suggested, destructive, or None."""
    dialog = Gtk.Window(transient_for=parent, modal=True, destroy_with_parent=True)
    dialog.set_title(heading)
    dialog.set_resizable(False)
    root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    root.set_margin_top(16)
    root.set_margin_bottom(16)
    root.set_margin_start(16)
    root.set_margin_end(16)
    text = Gtk.Label(label=body, wrap=True, xalign=0, selectable=True)
    text.set_max_width_chars(56)
    root.append(text)
    if extra is not None:
        root.append(extra)
    row = Gtk.Box(spacing=8)
    row.set_halign(Gtk.Align.END)
    closed = {"done": False}

    def finish(name):
        if closed["done"]:
            return
        closed["done"] = True
        on_choice(name)
        dialog.destroy()

    dialog.connect("close-request", lambda *_args: finish(default) or True)
    for name, label, style in responses:
        button = Gtk.Button(label=label)
        if style == "suggested":
            button.add_css_class("suggested-action")
        elif style == "destructive":
            button.add_css_class("destructive-action")
        button.connect("clicked", lambda *_button, chosen=name: finish(chosen))
        row.append(button)
    root.append(row)
    dialog.set_child(root)
    dialog.present()


class AinixWindow(Gtk.ApplicationWindow):
    def __init__(self, app, answer_fn):
        super().__init__(application=app, title="AINIX")
        self.answer_fn = answer_fn
        self.generation = 0
        self.busy = False
        self.plan = None
        self.package_plan = None
        self.package_text = ""
        self.page_name = "ask"
        self._resolved = ("", "", "")
        self._toggle_guard = False
        self.set_default_size(880, 720)

        header = Gtk.HeaderBar()
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
        title = Gtk.Label(label="AINIX")
        subtitle = Gtk.Label(label="Nix and NixOS helper")
        subtitle.add_css_class("dim-label")
        title_box.append(title)
        title_box.append(subtitle)
        header.set_title_widget(title_box)
        self.apply_button = Gtk.Button(label="Apply")
        self.apply_button.set_sensitive(False)
        self.apply_button.connect("clicked", self.on_apply)
        self.build_button = Gtk.Button(label="Build")
        self.build_button.set_sensitive(False)
        self.build_button.connect("clicked", self.on_build)
        self.copy_button = Gtk.Button(label="Copy")
        self.copy_button.connect("clicked", self.on_copy)
        self.ask_view_button = Gtk.Button(label="Ask")
        self.packages_view_button = Gtk.Button(label="Packages")
        self.ask_view_button.connect("clicked", lambda *_ignored: self._show_page("ask"))
        self.packages_view_button.connect("clicked", lambda *_ignored: self._show_page("packages"))
        header.pack_start(self.ask_view_button)
        header.pack_start(self.packages_view_button)
        header.pack_end(self.copy_button)
        header.pack_end(self.build_button)
        header.pack_end(self.apply_button)

        banner = Gtk.Label(
            label="Apply writes the configuration after you confirm. Build installs the system, and can write a waiting change first.",
            wrap=True,
            xalign=0,
        )

        self.question = Gtk.Entry()
        self.question.set_placeholder_text("How do I enable ssh?")
        self.question.set_hexpand(True)
        self.question.connect("activate", self.on_ask)

        self.ask_button = Gtk.Button(label="Ask")
        self.ask_button.add_css_class("suggested-action")
        self.ask_button.connect("clicked", self.on_ask)

        question_row = Gtk.Box(spacing=8)
        question_row.append(self.question)
        question_row.append(self.ask_button)

        self.config_entry = Gtk.Entry()
        self.config_entry.set_hexpand(True)
        self.config_entry.set_text(config_root())
        self.config_entry.set_placeholder_text("/etc/nixos")
        browse = Gtk.Button(label="Browse")
        browse.connect("clicked", self.on_browse)
        config_row = Gtk.Box(spacing=8)
        config_row.append(self.config_entry)
        config_row.append(browse)

        config_label = Gtk.Label(label="Configuration directory", xalign=0)
        config_label.add_css_class("heading")

        self.doc_switch = Gtk.Switch()
        self.doc_switch.set_valign(Gtk.Align.CENTER)
        self.doc_switch.connect("state-set", self.on_doc_toggle)
        doc_label = Gtk.Label(label=OPTION, xalign=0)
        doc_label.set_hexpand(True)
        self.doc_where = Gtk.Label(label="", xalign=0)
        self.doc_where.add_css_class("dim-label")
        doc_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        doc_text.set_hexpand(True)
        doc_text.append(doc_label)
        doc_text.append(self.doc_where)
        doc_row = Gtk.Box(spacing=12)
        doc_row.append(doc_text)
        doc_row.append(self.doc_switch)
        doc_row.add_css_class("card")
        doc_row.set_margin_top(4)
        doc_row.set_margin_bottom(4)
        doc_row.set_margin_start(12)
        doc_row.set_margin_end(12)

        self.answer = Gtk.TextView()
        self.answer.set_editable(False)
        self.answer.set_cursor_visible(False)
        self.answer.set_monospace(True)
        self.answer.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.answer.set_left_margin(12)
        self.answer.set_right_margin(12)
        self.answer.set_top_margin(12)
        self.answer.set_bottom_margin(12)
        self.answer.get_buffer().set_text(INTRO)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_child(self.answer)
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.add_css_class("card")

        self.spinner = Gtk.Spinner()
        self.status = Gtk.Label(label="", xalign=0)
        self.status.set_wrap(True)
        self.status.add_css_class("dim-label")
        status_row = Gtk.Box(spacing=8)
        status_row.append(self.spinner)
        status_row.append(self.status)

        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        page.set_margin_top(16)
        page.set_margin_bottom(16)
        page.set_margin_start(16)
        page.set_margin_end(16)
        page.append(banner)
        page.append(question_row)
        page.append(config_label)
        page.append(config_row)
        page.append(doc_row)
        page.append(scroll)
        self._load_doc_toggle()
        page.append(status_row)

        self.packages_panel = PackagesPanel(on_ask=self.on_package_ask, on_select=self.on_package_selected)
        self.config_entry.connect("changed", self._config_changed)
        self.stack = Gtk.Stack()
        self.stack.add_named(page, "ask")
        self.stack.add_named(self.packages_panel, "packages")
        self._show_page("ask")

        self.set_titlebar(header)
        self.set_child(self.stack)

    def _show_page(self, name):
        self.page_name = name
        self.stack.set_visible_child_name(name)
        self.ask_view_button.remove_css_class("suggested-action")
        self.packages_view_button.remove_css_class("suggested-action")
        button = self.ask_view_button if name == "ask" else self.packages_view_button
        button.add_css_class("suggested-action")
        self._refresh_actions()

    def _plan(self):
        if self.page_name == "packages":
            return self.package_plan
        return self.plan

    def _config_changed(self, *_ignored):
        selected = self.packages_panel.selected
        if selected is not None and not self.busy:
            self.on_package_selected(selected)
        self._load_doc_toggle()

    def _load_doc_toggle(self):
        edit = find_documentation_enable(self.config_entry.get_text().strip())
        self._toggle_guard = True
        if edit is None:
            self.doc_switch.set_active(False)
            self.doc_switch.set_sensitive(False)
            self.doc_where.set_text("Not set in this configuration directory.")
        else:
            self.doc_switch.set_sensitive(True)
            self.doc_switch.set_active(plain_bool(edit.old_value) == "true")
            self.doc_where.set_text(f"{edit.where} is {plain_bool(edit.old_value)}")
        self._toggle_guard = False

    def on_doc_toggle(self, _switch, state):
        if self._toggle_guard or self.busy:
            return True
        new_value = "true" if state else "false"
        plan = documentation_plan(self.config_entry.get_text().strip(), new_value)
        if plan is None:
            return False
        if plan.needs_host:
            self.status.set_text("This flake has more than one host. The toggle does not pick one.")
            return True
        self._confirm_doc_switch(plan)
        return True

    def _confirm_doc_switch(self, plan):
        edit = plan.edits[0]

        def finish(response):
            if response != "switch":
                self._load_doc_toggle()
                return
            try:
                self._resolved = plan.with_host("")
                written = apply_edits(plan.edits, self.config_entry.get_text().strip())
            except (ApplyError, ValueError, OSError) as exc:
                self._load_doc_toggle()
                self.status.set_text(str(exc))
                return
            self._show_page("ask")
            self._append("\nWrote " + ", ".join(written) + "\n")
            self._load_doc_toggle()
            self._begin_rebuild(self._resolved[0], afterwards="switch")

        open_choice(
            self,
            "Write this and switch?",
            (
                f"{edit.where}\n"
                f"- {edit.option} = {edit.old_value};\n"
                f"+ {edit.option} = {edit.new_value};\n\n"
                "A dry-build runs first. When it succeeds, this runs:\n"
                f"{plan.switch}\n\n"
                "Switch activates that generation in this session. You stay logged in."
            ),
            [("cancel", "Cancel", None), ("switch", "Write and switch", "destructive")],
            finish,
        )

    def on_package_selected(self, package):
        if package is None:
            self.package_plan = None
            self.package_text = ""
            self._refresh_actions()
            return
        text = self._package_answer(package)
        self.package_plan = text.plan
        self.package_text = str(text)
        if text.plan.edits:
            where = text.plan.edits[0].where or "a Nix file you choose"
            self.packages_panel.status.set_text(
                f"Apply writes {package.attr} into {where}. "
                "Build can install that change, or install the system as it is. "
                "Nothing is written until you confirm."
            )
        else:
            self.packages_panel.status.set_text(str(text).splitlines()[0])
        self._refresh_actions()

    def _package_answer(self, package):
        from ainix_help.install_edit import install_answer

        return install_answer(
            package.attr,
            self.config_entry.get_text().strip(),
            unfree=bool(getattr(package, "unfree", False)),
            broken=bool(getattr(package, "broken", False)),
        )

    def on_package_ask(self, package):
        text = self._package_answer(package)
        self.plan = text.plan
        self.package_plan = text.plan
        self.package_text = str(text)
        self.question.set_text(f"How do I install {package.attr}?")
        self.answer.get_buffer().set_text(str(text).strip() + "\n")
        self._show_page("ask")
        if text.plan.edits:
            self.status.set_text("Preview ready. Apply adds the package after you confirm.")
        else:
            self.status.set_text(str(text).splitlines()[0])

    def answer_text(self):
        buf = self.answer.get_buffer()
        return buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)

    def on_browse(self, _button):
        dialog = Gtk.FileDialog()
        dialog.set_title("Configuration directory")
        current = self.config_entry.get_text().strip()
        if current:
            folder = existing_file(current)
            if folder is not None:
                dialog.set_initial_folder(folder)
        dialog.select_folder(self, None, self.on_folder)

    def on_folder(self, dialog, result):
        try:
            chosen = dialog.select_folder_finish(result)
        except GLib.Error:
            return
        if chosen is not None:
            self.config_entry.set_text(chosen.get_path() or "")

    def on_copy(self, _button):
        text = self.answer_text().strip()
        if not text:
            return
        self.get_clipboard().set(text)
        self.status.set_text("Answer copied")

    def on_ask(self, *_ignored):
        if self.busy:
            return
        question = self.question.get_text().strip()
        config = self.config_entry.get_text().strip()
        if not question:
            self.status.set_text("Type a question first.")
            return
        self.generation += 1
        token = self.generation
        self._set_busy(True)
        self.status.set_text("Asking your files and the Nix sources…")

        def work():
            try:
                text = self.answer_fn(question, config)
                error = ""
            except Exception as exc:
                text = ""
                error = f"{exc.__class__.__name__}: {exc}"
            GLib.idle_add(self.finish, token, text, error)

        threading.Thread(target=work, daemon=True).start()

    def finish(self, token, text, error):
        if token != self.generation:
            return False
        self._set_busy(False)
        if error:
            self.plan = None
            self._refresh_actions()
            self.answer.get_buffer().set_text(error)
            self.status.set_text("The question failed before an answer was ready.")
            return False
        self.plan = getattr(text, "plan", None)
        self.answer.get_buffer().set_text(str(text).strip() + "\n")
        self._refresh_actions()
        if self.plan is not None and self.plan.edits and self.plan.dry_build:
            self.status.set_text(
                "Preview ready. Apply writes the configuration. Build can install that change, or install the system as it is."
            )
        elif self.plan is not None and self.plan.edits:
            self.status.set_text("Preview ready. Apply writes the shown line after you confirm.")
        elif self.plan is not None and self.plan.dry_build:
            self.status.set_text("Preview ready. Build can dry-build, switch, or boot.")
        else:
            self.status.set_text("Preview ready. Nothing was edited and nothing was built.")
        return False

    def _refresh_actions(self):
        apply, build = button_state(self._plan())
        self.apply_button.set_sensitive(apply and not self.busy)
        self.build_button.set_sensitive(build and not self.busy)

    def _set_busy(self, busy):
        self.busy = busy
        self.ask_button.set_sensitive(not busy)
        self.question.set_sensitive(not busy)
        if busy:
            self.spinner.start()
            self.apply_button.set_sensitive(False)
            self.build_button.set_sensitive(False)
        else:
            self.spinner.stop()
            self._refresh_actions()

    def _append(self, text):
        buf = self.answer.get_buffer()
        buf.insert(buf.get_end_iter(), text)
        return False

    def on_apply(self, *_ignored):
        self._start_write()

    def _start_write(self):
        plan = self._plan()
        if self.busy or plan is None or not plan.edits:
            return
        if any(not edit.path for edit in plan.edits):
            self._choose_insert_file()
            return
        self._confirm_write()

    def _choose_insert_file(self):
        dialog = Gtk.FileDialog()
        dialog.set_title("File that should gain this option")
        nix = Gtk.FileFilter()
        nix.set_name("Nix files")
        nix.add_suffix("nix")
        dialog.set_default_filter(nix)
        current = self.config_entry.get_text().strip()
        folder = existing_file(current)
        if folder is not None:
            dialog.set_initial_folder(folder)
        dialog.open(self, None, self._insert_file_chosen)

    def _insert_file_chosen(self, dialog, result):
        try:
            chosen = dialog.open_finish(result)
        except GLib.Error:
            return
        path = chosen.get_path() if chosen is not None else ""
        if not path:
            return
        plan = self._plan()
        if plan is None:
            return
        for edit in plan.edits:
            if not edit.path:
                edit.path = path
                edit.where = path
        self._confirm_write()

    def _edit_body(self):
        rows = []
        for edit in self._plan().edits:
            rows.append(edit.where or edit.path or "The file you chose")
            if getattr(edit, "kind", "assign") == "package" and edit.line:
                rows.append(f"+ {edit.new_value}")
                rows.append("This name is added to the environment.systemPackages list in that file.")
            else:
                if edit.old_value:
                    rows.append(f"- {edit.option} = {edit.old_value};")
                else:
                    rows.append("- (not set in that file)")
                rows.append(f"+ {edit.option} = {edit.new_value};")
            rows.append("")
        rows.append("This writes those lines. The dry-build runs next. Switch and boot wait until it succeeds.")
        return "\n".join(rows)

    def _host_dropdown(self):
        names = [""] + list(self._plan().flake_names)
        model = Gtk.StringList.new(names)
        return Gtk.DropDown(model=model, selected=0)

    def _dropdown_text(self, dropdown):
        if dropdown is None:
            return ""
        item = dropdown.get_selected_item()
        return item.get_string() if item is not None else ""

    def _confirm_write(self):
        plan = self._plan()
        if plan is None or not plan.edits:
            return
        host_box = self._host_dropdown() if plan.needs_host else None

        def finish(response):
            if response != "write":
                return
            try:
                host = self._dropdown_text(host_box)
                self._resolved = plan.with_host(host)
                written = apply_edits(plan.edits, self.config_entry.get_text().strip())
            except (ApplyError, ValueError, OSError) as exc:
                self.status.set_text(str(exc))
                return
            from_packages = self.page_name == "packages"
            if from_packages and self.package_text:
                self.answer.get_buffer().set_text(self.package_text.strip() + "\n")
            self.plan = plan
            plan.edits = []
            self._show_page("ask")
            self._append("\nWrote " + ", ".join(written) + "\n")
            self._begin_rebuild(self._resolved[0], afterwards="choose")

        open_choice(
            self,
            "Write this change?",
            self._edit_body(),
            [("cancel", "Cancel", None), ("write", "Write the file", "destructive")],
            finish,
            extra=host_box,
        )

    def on_build(self, *_ignored):
        plan = self._plan()
        if self.busy or plan is None or not plan.dry_build:
            return
        if plan.edits:
            self._build_with_edit(plan)
            return
        self._choose_build(plan)

    def _build_with_edit(self, plan):
        def finish(response):
            if response == "write":
                self._start_write()
            elif response == "current":
                self._choose_build(plan)

        open_choice(
            self,
            "Write the change before installing?",
            "A configuration change is waiting. Write it, then install. "
            "Or install the files as they are and leave that change for later.",
            [
                ("cancel", "Cancel", None),
                ("current", "Install as it is", None),
                ("write", "Write, then install", "suggested"),
            ],
            finish,
        )

    def _choose_build(self, plan):
        host_box = self._host_dropdown() if plan.needs_host else None

        def finish(response):
            if response not in {"dry", "boot", "switch"}:
                return
            try:
                dry, switch, boot = plan.with_host(self._dropdown_text(host_box))
            except ValueError as exc:
                self.status.set_text(str(exc))
                return
            self._resolved = (dry, switch, boot)
            command = {"dry": dry, "boot": boot, "switch": switch}[response]
            afterwards = "choose" if response == "dry" else "stop"
            self._begin_rebuild(command, afterwards)

        open_choice(
            self,
            "Build this system?",
            "Dry-build only checks. Switch replaces the running system. "
            "Boot builds the next startup and leaves this session as it is. "
            "No file is edited.",
            [
                ("cancel", "Cancel", None),
                ("dry", "Dry-build", None),
                ("boot", "Boot", "suggested"),
                ("switch", "Switch", "destructive"),
            ],
            finish,
            extra=host_box,
        )

    def _begin_rebuild(self, command, afterwards):
        self._set_busy(True)
        self.status.set_text("Checking sudo…")

        def work():
            try:
                needs = sudo_needs_password()
                error = ""
            except OSError as exc:
                needs = False
                error = str(exc)
            GLib.idle_add(self._have_sudo, needs, error, command, afterwards)

        threading.Thread(target=work, daemon=True).start()

    def _have_sudo(self, needs, error, command, afterwards):
        if error:
            self._set_busy(False)
            self.status.set_text(error)
            return False
        if not needs:
            self._launch(command, None, afterwards)
            return False
        self._ask_password(command, afterwards)
        return False

    def _ask_password(self, command, afterwards):
        entry = Gtk.PasswordEntry()

        def finish(response):
            if response != "ok":
                self._set_busy(False)
                self.status.set_text("Cancelled before the rebuild.")
                return
            self._launch(command, entry.get_text(), afterwards)

        open_choice(
            self,
            "Sudo password",
            "This rebuild needs sudo. The password is used for this command and is not saved.",
            [("cancel", "Cancel", None), ("ok", "Continue", "suggested")],
            finish,
            extra=entry,
        )

    def _launch(self, command, password, afterwards):
        self._set_busy(True)
        self._append(f"\n$ {command}\n")
        self.status.set_text("Running the rebuild…")

        def on_line(line):
            GLib.idle_add(self._append, line + "\n")

        def work():
            try:
                code, _output = run_rebuild(command, password, on_line)
                error = ""
            except (ValueError, OSError) as exc:
                code, error = 1, str(exc)
            GLib.idle_add(self._rebuild_finished, code, error, afterwards)

        threading.Thread(target=work, daemon=True).start()

    def _rebuild_finished(self, code, error, afterwards):
        self._set_busy(False)
        if error:
            self.status.set_text(error)
            return False
        if code != 0:
            self.status.set_text("The build failed. The running system was not switched.")
            return False
        if afterwards == "switch":
            self.status.set_text("Dry-build succeeded. Switching. You stay logged in.")
            self._begin_rebuild(self._resolved[1], afterwards="stop")
            return False
        if afterwards != "choose":
            self.status.set_text("Build finished. Nothing further was started.")
            return False
        self._choose_activation()
        return False

    def _choose_activation(self):
        def finish(response):
            if response == "boot":
                self._begin_rebuild(self._resolved[2], afterwards="stop")
            elif response == "switch":
                self._begin_rebuild(self._resolved[1], afterwards="stop")
            else:
                self.status.set_text("Dry-build succeeded. Nothing was switched or set to boot.")

        open_choice(
            self,
            "Dry-build succeeded",
            "Switch replaces the running system now. Boot builds the next startup and leaves this session as it is.",
            [
                ("later", "Not now", None),
                ("boot", "Boot", "suggested"),
                ("switch", "Switch", "destructive"),
            ],
            finish,
            default="later",
        )


def existing_file(path):
    from gi.repository import Gio

    folder = Gio.File.new_for_path(path)
    if folder.query_exists():
        return folder
    return None


class AinixApp(Gtk.Application):
    def __init__(self, answer_fn=None, after_present=None):
        super().__init__(application_id="org.jdnitrap.Ainix")
        self.answer_fn = answer_fn or answer_question
        self.after_present = after_present
        self.window = None

    def do_activate(self, *_ignored):
        if self.window is None:
            self.window = AinixWindow(self, self.answer_fn)
            if self.after_present is not None:
                GLib.idle_add(self.after_present, self.window)
        self.window.present()


def self_test():
    import os
    import tempfile

    os.environ["AINIX_CATALOG_CACHE"] = tempfile.mkdtemp(prefix="ainix-catalog-")
    seen = {}
    holder = {"code": 1, "tries": 0}

    def fake(question, config):
        seen["question"] = question
        seen["config"] = config
        return (
            "Suggested change\n"
            "+ services.openssh.enable = true;\n"
            "This is a preview. Nothing was edited and nothing was built."
        )

    def after(window):
        window._show_page("packages")
        if "Refresh" not in window.packages_panel.status.get_text():
            print(window.packages_panel.status.get_text())
            window.get_application().quit()
            return False
        window._show_page("ask")
        window.question.set_text("   ")
        window.on_ask()
        if window.status.get_text() != "Type a question first.":
            print("empty question was accepted")
            window.get_application().quit()
            return False
        window.question.set_text("how do I enable ssh")
        window.config_entry.set_text("/etc/nixos")
        window.on_ask()

        def check():
            holder["tries"] += 1
            text = window.answer_text()
            if "Nothing was edited" not in text:
                if holder["tries"] > 50:
                    print(text or window.status.get_text())
                    window.get_application().quit()
                    return False
                return True
            if seen.get("question") != "how do I enable ssh" or seen.get("config") != "/etc/nixos":
                print(seen)
                window.get_application().quit()
                return False
            if not window.ask_button.get_sensitive():
                print("Ask stayed disabled")
                window.get_application().quit()
                return False
            if window.apply_button.get_sensitive() or window.build_button.get_sensitive():
                print("Apply or Build was offered for a preview with no plan")
                window.get_application().quit()
                return False
            holder["code"] = 0
            print("gui self-test passed")
            window.get_application().quit()
            return False

        GLib.timeout_add(20, check)
        return False

    app = AinixApp(answer_fn=fake, after_present=after)
    app.run(["ainix-gui"])
    return holder["code"]


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    if "--self-test" in argv:
        return self_test()
    app = AinixApp()
    return app.run(argv)
