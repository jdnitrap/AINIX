"""Browse the stable or unstable package list inside the AINIX window."""

import shutil
import subprocess
import threading

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk, Pango

from ainix_catalog.catalog import (
    CatalogError,
    cache_root,
    catalog_path,
    load_cached,
    refresh,
    suggest_branch,
)
from ainix_catalog.groups import CATEGORY_ORDER


EMPTY = (
    "Choose Stable or Unstable, then Refresh. "
    "That pulls the package list for the branch you picked."
)
SHOW_LIMIT = 300


def read_nixos_version():
    if shutil.which("nixos-version") is None:
        return ""
    try:
        return subprocess.check_output(
            ["nixos-version"],
            text=True,
            timeout=5,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError):
        return ""


class PackagesPanel(Gtk.Box):
    def __init__(self, on_ask, on_select=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.on_ask = on_ask
        self.on_select = on_select
        self.catalog = None
        self.busy = False
        self.ready = False
        self.generation = 0
        self._search_token = 0
        self.selected = None
        self.set_margin_top(16)
        self.set_margin_bottom(16)
        self.set_margin_start(16)
        self.set_margin_end(16)

        strings = Gtk.StringList.new(["Stable", "Unstable"])
        self.branch = Gtk.DropDown(model=strings, selected=0)
        self.branch.connect("notify::selected", self._branch_changed)
        self.refresh_button = Gtk.Button(label="Refresh")
        self.refresh_button.add_css_class("suggested-action")
        self.refresh_button.connect("clicked", self.on_refresh)
        self.revision = Gtk.Label(label="", xalign=0)
        self.revision.set_hexpand(True)
        self.revision.set_ellipsize(Pango.EllipsizeMode.END)
        self.revision.add_css_class("dim-label")
        top = Gtk.Box(spacing=8)
        top.append(self.branch)
        top.append(self.refresh_button)
        top.append(self.revision)

        note = Gtk.Label(
            label=(
                "Stable and Unstable are the current NixOS channels. "
                "Refresh reads that channel's package list from nixpkgs. "
                "Languages, TeX, Typst, and fonts have their own groups. "
                "A package that is still unclassified is a Program when it installs a command, and a Library when it does not. "
                "Apply adds the selected package to this machine's package list after you confirm. "
                "The system channel is left as it is."
            ),
            xalign=0,
        )
        note.set_wrap(True)
        note.add_css_class("dim-label")

        self.search = Gtk.SearchEntry()
        self.search.set_placeholder_text("Filter by name or description")
        self.search.connect("search-changed", self._search_changed)

        self.categories = Gtk.ListBox()
        self.categories.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.categories.add_css_class("navigation-sidebar")
        self.categories.connect("row-selected", self._category_selected)
        category_scroll = Gtk.ScrolledWindow()
        category_scroll.set_child(self.categories)
        category_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        category_scroll.set_size_request(220, -1)

        self.results = Gtk.ListBox()
        self.results.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.results.connect("row-selected", self._result_selected)
        result_scroll = Gtk.ScrolledWindow()
        result_scroll.set_child(self.results)
        result_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        result_scroll.set_vexpand(True)
        result_scroll.add_css_class("card")

        self.detail = Gtk.Label(label="Pick a package.", xalign=0, yalign=0)
        self.detail.set_wrap(True)
        self.detail.set_selectable(True)
        self.detail.set_margin_top(8)
        self.detail.set_margin_bottom(8)
        self.detail.set_margin_start(8)
        self.detail.set_margin_end(8)
        detail_scroll = Gtk.ScrolledWindow()
        detail_scroll.set_child(self.detail)
        detail_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        detail_scroll.set_size_request(-1, 120)
        detail_scroll.add_css_class("card")

        self.copy_button = Gtk.Button(label="Copy name")
        self.copy_button.set_sensitive(False)
        self.copy_button.connect("clicked", self.on_copy)
        self.ask_button = Gtk.Button(label="Ask how to install")
        self.ask_button.set_sensitive(False)
        self.ask_button.connect("clicked", self.on_ask_install)
        buttons = Gtk.Box(spacing=8)
        buttons.append(self.copy_button)
        buttons.append(self.ask_button)

        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        right.set_hexpand(True)
        right.append(result_scroll)
        right.append(detail_scroll)
        right.append(buttons)

        panes = Gtk.Box(spacing=12)
        panes.set_vexpand(True)
        panes.append(category_scroll)
        panes.append(right)

        self.spinner = Gtk.Spinner()
        self.status = Gtk.Label(label=EMPTY, xalign=0)
        self.status.set_wrap(True)
        self.status.add_css_class("dim-label")
        status_row = Gtk.Box(spacing=8)
        status_row.append(self.spinner)
        status_row.append(self.status)

        self.append(top)
        self.append(note)
        self.append(self.search)
        self.append(panes)
        self.append(status_row)

        selected = 1 if suggest_branch(read_nixos_version()) == "unstable" else 0
        self.branch.set_selected(selected)
        self.ready = True
        self._load_cached()

    def _branch(self):
        return "unstable" if self.branch.get_selected() == 1 else "stable"

    def _branch_changed(self, *_ignored):
        if not self.ready or self.busy:
            return
        self._load_cached()

    def _search_changed(self, *_ignored):
        if self._search_token:
            GLib.source_remove(self._search_token)
        self._search_token = GLib.timeout_add(150, self._apply_filter)

    def _category_selected(self, *_ignored):
        self._apply_filter()

    def _category_name(self):
        row = self.categories.get_selected_row()
        if row is None:
            return ""
        return getattr(row, "category_name", "")

    def _load_cached(self):
        branch = self._branch()
        path = catalog_path(cache_root(), branch)
        self.catalog = None
        self._clear(self.categories)
        self._clear(self.results)
        self._show_detail(None)
        self.revision.set_text("")
        if not path.is_file():
            self.status.set_text(EMPTY)
            return
        self.generation += 1
        token = self.generation
        root = cache_root()

        def work():
            catalog = load_cached(root, branch)
            GLib.idle_add(self._loaded, token, catalog)

        threading.Thread(target=work, daemon=True).start()
        self.status.set_text("Opening the saved package list…")

    def _loaded(self, token, catalog):
        if token != self.generation:
            return False
        if catalog is None:
            self.status.set_text(EMPTY)
            return False
        self._apply_catalog(catalog)
        short = catalog.revision[:12]
        self.status.set_text(
            f"{catalog.channel} at {short}. {len(catalog.packages)} packages."
        )
        return False

    def on_refresh(self, *_ignored):
        if self.busy:
            return
        self.busy = True
        self.refresh_button.set_sensitive(False)
        self.branch.set_sensitive(False)
        self.spinner.start()
        self.generation += 1
        token = self.generation
        branch = self._branch()
        root = cache_root()

        def tell(message):
            GLib.idle_add(self._progress, token, message)

        def work():
            try:
                catalog = refresh(branch, root, progress=tell)
                error = ""
            except CatalogError as exc:
                catalog = None
                error = str(exc)
            except Exception as exc:
                catalog = None
                error = f"{exc.__class__.__name__}: {exc}"
            GLib.idle_add(self._refreshed, token, catalog, error)

        threading.Thread(target=work, daemon=True).start()

    def _progress(self, token, message):
        if token == self.generation:
            self.status.set_text(message)
        return False

    def _refreshed(self, token, catalog, error):
        if token != self.generation:
            return False
        self.busy = False
        self.refresh_button.set_sensitive(True)
        self.branch.set_sensitive(True)
        self.spinner.stop()
        if error or catalog is None:
            self.status.set_text(error or "The package list was not saved.")
            return False
        self._apply_catalog(catalog)
        short = catalog.revision[:12]
        self.status.set_text(
            f"Saved {len(catalog.packages)} packages from {catalog.channel} at {short}."
        )
        return False

    def _apply_catalog(self, catalog):
        self.catalog = catalog
        short = catalog.revision[:12]
        self.revision.set_text(f"{catalog.channel}  {short}  {catalog.fetched_at}")
        self._fill_categories()
        self._apply_filter()

    def _fill_categories(self):
        self._clear(self.categories)
        self._add_category("", f"All  {len(self.catalog.packages)}")
        for name in CATEGORY_ORDER:
            count = self.catalog.counts.get(name, 0)
            if count:
                self._add_category(name, f"{name}  {count}")
        first = self.categories.get_row_at_index(0)
        if first is not None:
            self.categories.select_row(first)

    def _add_category(self, name, label):
        row = Gtk.ListBoxRow()
        row.category_name = name
        text = Gtk.Label(label=label, xalign=0)
        text.set_margin_top(6)
        text.set_margin_bottom(6)
        text.set_margin_start(10)
        text.set_margin_end(10)
        row.set_child(text)
        self.categories.append(row)

    def _apply_filter(self):
        self._search_token = 0
        self._clear(self.results)
        self._show_detail(None)
        catalog = self.catalog
        if catalog is None:
            return False
        category = self._category_name()
        query = self.search.get_text().strip()
        if not category and not query:
            self.status.set_text(
                f"{len(catalog.packages)} packages. Pick a group, or type a name."
            )
            return False
        try:
            rows, total = catalog.select(category, query, SHOW_LIMIT)
        except CatalogError as exc:
            self.status.set_text(str(exc))
            return False
        for package in rows:
            self.results.append(self._result_row(package))
        shown = f"Showing {len(rows)} of {total}."
        if category:
            shown = category + ". " + shown
        self.status.set_text(shown)
        return False

    def _result_row(self, package):
        row = Gtk.ListBoxRow()
        row.package = package
        title = Gtk.Label(label=package.attr, xalign=0)
        title.add_css_class("heading")
        meta = package.version or "no version"
        if package.unfree:
            meta += "  unfree"
        if package.broken:
            meta += "  broken"
        version = Gtk.Label(label=meta, xalign=0)
        version.add_css_class("dim-label")
        description = Gtk.Label(label=package.description or package.category, xalign=0)
        description.set_ellipsize(Pango.EllipsizeMode.END)
        description.add_css_class("dim-label")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_margin_top(6)
        box.set_margin_bottom(6)
        box.set_margin_start(10)
        box.set_margin_end(10)
        box.append(title)
        box.append(version)
        box.append(description)
        row.set_child(box)
        return row

    def _result_selected(self, _box, row):
        self._show_detail(None if row is None else getattr(row, "package", None))

    def _show_detail(self, package):
        self.selected = package
        self.copy_button.set_sensitive(package is not None)
        self.ask_button.set_sensitive(package is not None)
        if package is None:
            self.detail.set_text("Pick a package.")
            if self.on_select is not None:
                self.on_select(None)
            return
        lines = [
            package.attr,
            package.version or "no version",
            package.category,
        ]
        if package.description:
            lines.append(package.description)
        if package.homepage:
            lines.append(package.homepage)
        marks = []
        if package.unfree:
            marks.append("unfree")
        if package.broken:
            marks.append("broken")
        if marks:
            lines.append(", ".join(marks))
        lines.append("")
        lines.append("pkgs." + package.attr)
        self.detail.set_text("\n".join(lines))
        if self.on_select is not None:
            self.on_select(package)

    def on_copy(self, *_ignored):
        package = self.selected
        if package is None:
            return
        text = "pkgs." + package.attr
        self.get_clipboard().set(text)
        self.status.set_text("Copied " + text)

    def on_ask_install(self, *_ignored):
        package = self.selected
        if package is None or self.on_ask is None:
            return
        self.on_ask(package)

    def _clear(self, box):
        while True:
            row = box.get_row_at_index(0)
            if row is None:
                return
            box.remove(row)
