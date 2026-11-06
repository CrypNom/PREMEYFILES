"""
pages.py - Every screen of PREMEYFILES ADMIN.

Each page is a Frame with a refresh() method that loads fresh data from the
website. Nothing is stored in this program - the website is the only source
of truth.
"""
import os
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, ttk

import theme
from api_client import ApiError


# ====================================================================== base
class Page(tk.Frame):
    title = ""

    def __init__(self, parent, app):
        super().__init__(parent, bg=theme.BG)
        self.app = app

    def refresh(self):
        pass

    def header(self, text, subtitle=""):
        top = tk.Frame(self, bg=theme.BG)
        top.pack(fill="x", pady=(0, 14))
        theme.label(top, text, theme.FONT_H1).pack(anchor="w")
        if subtitle:
            theme.label(top, subtitle, theme.FONT_SMALL, theme.MUTED).pack(anchor="w")
        return top


class FormDialog(tk.Toplevel):
    """A small popup with a few text fields (used to add / edit categories and tags)."""

    def __init__(self, app, title, fields, on_submit):
        super().__init__(app.root, bg=theme.PANEL)
        self.title(title)
        self.resizable(False, False)
        self.transient(app.root)
        self.on_submit = on_submit
        self.vars = {}
        body = tk.Frame(self, bg=theme.PANEL, padx=24, pady=20)
        body.pack()
        theme.label(body, title, theme.FONT_H2).pack(anchor="w", pady=(0, 10))
        first = None
        for key, text, initial in fields:
            theme.label(body, text, theme.FONT_SMALL, theme.MUTED).pack(anchor="w", pady=(6, 2))
            var = tk.StringVar(value=initial)
            e = theme.entry(body, var, width=40)
            e.pack(fill="x", ipady=5)
            e.bind("<Return>", lambda _e: self.submit())
            self.vars[key] = var
            first = first or e
        row = tk.Frame(body, bg=theme.PANEL)
        row.pack(fill="x", pady=(16, 0))
        theme.button(row, "Save", self.submit).pack(side="right")
        theme.button(row, "Cancel", self.destroy, "ghost").pack(side="right", padx=8)
        first.focus_set()
        self.grab_set()
        app.center(self)

    def submit(self):
        self.on_submit({k: v.get().strip() for k, v in self.vars.items()})
        self.destroy()


# ====================================================================== dashboard
class DashboardPage(Page):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.header("Dashboard", "A live overview of your website")
        self.cards_row = tk.Frame(self, bg=theme.BG)
        self.cards_row.pack(fill="x")
        self.card_labels = {}
        for key, text in (("total_projects", "Projects"), ("total_downloads", "Total downloads"),
                          ("downloads_today", "Downloads today"), ("storage", "Storage used"),
                          ("unread_messages", "Unread messages")):
            c = theme.card(self.cards_row, padx=18, pady=14)
            c.pack(side="left", expand=True, fill="x", padx=(0, 10))
            value = theme.label(c, "-", theme.FONT_BIG, theme.PURPLE_SOFT, bg=theme.CARD)
            value.pack(anchor="w")
            theme.label(c, text, theme.FONT_SMALL, theme.MUTED, bg=theme.CARD).pack(anchor="w")
            self.card_labels[key] = value

        lower = tk.Frame(self, bg=theme.BG)
        lower.pack(fill="both", expand=True, pady=(14, 0))
        left = tk.Frame(lower, bg=theme.BG)
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        right = tk.Frame(lower, bg=theme.BG)
        right.pack(side="left", fill="both", expand=True)

        theme.label(left, "Top downloaded projects", theme.FONT_H2).pack(anchor="w", pady=(0, 6))
        frame, self.top_table = theme.make_table(left, [("title", "Project"), ("n", "Downloads")], [260, 90], 6)
        frame.pack(fill="x")
        theme.label(left, "Recently uploaded", theme.FONT_H2).pack(anchor="w", pady=(14, 6))
        frame, self.recent_table = theme.make_table(left, [("title", "Project"), ("date", "Date")], [260, 110], 6)
        frame.pack(fill="x")

        theme.label(right, "Downloads - last 7 days", theme.FONT_H2).pack(anchor="w", pady=(0, 6))
        self.chart = tk.Canvas(right, height=260, bg=theme.CARD, highlightthickness=1,
                               highlightbackground=theme.BORDER)
        self.chart.pack(fill="both", expand=True)
        self.chart.bind("<Configure>", lambda _e: self._draw_chart())
        self._days = []

    def refresh(self):
        self.app.run_async(self.app.api.dashboard, self._show)

    def _show(self, d):
        self.card_labels["total_projects"].configure(text=str(d["total_projects"]))
        self.card_labels["total_downloads"].configure(text=str(d["total_downloads"]))
        self.card_labels["downloads_today"].configure(text=str(d["downloads_today"]))
        self.card_labels["storage"].configure(text=theme.human_size(d["total_storage_bytes"]))
        self.card_labels["unread_messages"].configure(text=str(d["unread_messages"]))
        self.app.set_unread(d["unread_messages"])
        for tree, rows, fn in ((self.top_table, d["top_projects"], lambda r: (r["title"], r["download_count"])),
                               (self.recent_table, d["recent_projects"], lambda r: (r["title"], r["created_at"][:10]))):
            tree.delete(*tree.get_children())
            for r in rows:
                tree.insert("", "end", values=fn(r))
        self._days = d["downloads_per_day"]
        self._draw_chart()

    def _draw_chart(self):
        c = self.chart
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 50 or h < 50:
            return
        if not self._days:
            c.create_text(w / 2, h / 2, text="No downloads in the last 7 days", fill=theme.MUTED, font=theme.FONT)
            return
        biggest = max(r["n"] for r in self._days) or 1
        n = len(self._days)
        slot = (w - 40) / n
        for i, r in enumerate(self._days):
            bar_h = (h - 70) * r["n"] / biggest
            x0 = 20 + i * slot + slot * 0.2
            x1 = 20 + (i + 1) * slot - slot * 0.2
            c.create_rectangle(x0, h - 36 - bar_h, x1, h - 36, fill=theme.PURPLE, outline="")
            c.create_text((x0 + x1) / 2, h - 44 - bar_h, text=str(r["n"]), fill=theme.TEXT, font=theme.FONT_SMALL)
            c.create_text((x0 + x1) / 2, h - 18, text=r["day"][5:], fill=theme.MUTED, font=theme.FONT_SMALL)


# ====================================================================== project form
class ProjectForm(tk.Frame):
    """Used for publishing a new project and for editing an existing one."""

    def __init__(self, parent, app, project=None, on_saved=None, bg=theme.BG):
        super().__init__(parent, bg=bg)
        self.app = app
        self.project = project
        self.on_saved = on_saved
        self.file_path = None
        self.thumb_path = None
        self.busy = False
        self.progress_state = (0, 1)
        self.categories, self.languages = [], []
        self.allowed = set()

        left = tk.Frame(self, bg=bg)
        left.pack(side="left", fill="both", expand=True, padx=(0, 16))
        right = tk.Frame(self, bg=bg)
        right.pack(side="left", fill="y")

        theme.label(left, "Project title *", theme.FONT_SMALL, theme.MUTED, bg=bg).pack(anchor="w")
        self.title_var = tk.StringVar(value=project["title"] if project else "")
        theme.entry(left, self.title_var, width=50).pack(fill="x", ipady=6, pady=(2, 10))

        theme.label(left, "Description", theme.FONT_SMALL, theme.MUTED, bg=bg).pack(anchor="w")
        self.desc = theme.textbox(left, height=8)
        self.desc.pack(fill="both", expand=True, pady=(2, 10))
        if project:
            self.desc.insert("1.0", project["description"])

        theme.label(left, "Category", theme.FONT_SMALL, theme.MUTED, bg=bg).pack(anchor="w")
        self.cat_var = tk.StringVar()
        self.cat_box = ttk.Combobox(left, textvariable=self.cat_var, state="readonly", width=40)
        self.cat_box.pack(fill="x", pady=(2, 10), ipady=3)

        theme.label(left, "Programming languages (Ctrl+click for several)", theme.FONT_SMALL, theme.MUTED, bg=bg).pack(anchor="w")
        self.lang_list = tk.Listbox(left, selectmode="multiple", height=5, exportselection=False,
                                    bg=theme.FIELD, fg=theme.TEXT, selectbackground=theme.PURPLE_DARK,
                                    selectforeground="#fff", relief="flat", highlightthickness=1,
                                    highlightbackground=theme.BORDER, activestyle="none")
        self.lang_list.pack(fill="x", pady=(2, 0))

        # ---- right column: files
        self.file_title = "Source-code file *" if not project else "Replace source file (optional)"
        theme.label(right, self.file_title, theme.FONT_SMALL, theme.MUTED, bg=bg).pack(anchor="w")
        self.file_label = theme.label(right, self._file_text(), theme.FONT_SMALL, theme.TEXT, bg=bg,
                                      wraplength=260, justify="left")
        self.file_label.pack(anchor="w", pady=(2, 4))
        theme.button(right, "Choose file...", self.pick_file, "ghost").pack(anchor="w")
        self.allowed_label = theme.label(right, "", theme.FONT_SMALL, theme.MUTED, bg=bg, wraplength=260, justify="left")
        self.allowed_label.pack(anchor="w", pady=(4, 14))

        theme.label(right, "Thumbnail / preview image", theme.FONT_SMALL, theme.MUTED, bg=bg).pack(anchor="w")
        self.thumb_label = theme.label(right, "None selected" if not (project and project["thumbnail"]) else
                                       "Current image kept", theme.FONT_SMALL, theme.TEXT, bg=bg,
                                       wraplength=260, justify="left")
        self.thumb_label.pack(anchor="w", pady=(2, 4))
        theme.button(right, "Choose image...", self.pick_thumb, "ghost").pack(anchor="w")
        self.remove_thumb = tk.IntVar(value=0)
        if project and project["thumbnail"]:
            tk.Checkbutton(right, text="Remove current thumbnail", variable=self.remove_thumb, bg=bg,
                           fg=theme.TEXT, selectcolor=theme.FIELD, activebackground=bg,
                           activeforeground=theme.TEXT).pack(anchor="w", pady=(6, 0))

        self.bar = ttk.Progressbar(right, length=260, mode="determinate", maximum=100)
        self.bar.pack(anchor="w", pady=(26, 2))
        self.status = theme.label(right, "", theme.FONT_SMALL, theme.MUTED, bg=bg, wraplength=260, justify="left")
        self.status.pack(anchor="w")
        text = "Publish" if not project else "Save changes"
        self.submit_btn = theme.button(right, text, self.submit, pady=10)
        self.submit_btn.pack(anchor="w", fill="x", pady=(10, 0))

        self.load_choices()

    # ---- loading lists
    def load_choices(self):
        self.app.run_async(lambda: (self.app.api.categories(), self.app.api.languages(), self.app.api.settings()),
                           self._choices_loaded)

    def _choices_loaded(self, result):
        try:
            # Remember what is selected right now (so reloading the lists keeps the choices).
            old_cat = self.cat_var.get()
            old_langs = {self.lang_list.get(i) for i in self.lang_list.curselection()}
            first_load = not self.categories and not self.languages
            self.categories, self.languages, settings = result
            names = ["(No category)"] + [c["name"] for c in self.categories]
            self.cat_box.configure(values=names)
            selected = "(No category)"
            chosen_names = set()
            if first_load and self.project:
                for c in self.categories:
                    if c["id"] == self.project["category_id"]:
                        selected = c["name"]
                chosen_names = {l["name"] for l in self.project["languages"]}
            elif not first_load:
                selected = old_cat if old_cat in names else "(No category)"
                chosen_names = old_langs
            self.cat_var.set(selected)
            self.lang_list.delete(0, "end")
            for i, lang in enumerate(self.languages):
                self.lang_list.insert("end", lang["name"])
                if lang["name"] in chosen_names:
                    self.lang_list.selection_set(i)
            self.allowed = {e for e in settings["settings"]["allowed_extensions"].split(",") if e}
            self.allowed_label.configure(text="Allowed types: " + ", ".join(sorted(self.allowed)) +
                                         "\nMax size: %s MB" % settings["settings"]["max_upload_mb"])
        except tk.TclError:
            pass  # the window was closed

    def _file_text(self):
        if self.file_path:
            return "%s (%s)" % (os.path.basename(self.file_path), theme.human_size(os.path.getsize(self.file_path)))
        if self.project:
            f = self.project["file"]
            return "Current: %s (%s)" % (f["original_name"], theme.human_size(f["size_bytes"]))
        return "No file selected"

    def pick_file(self):
        path = filedialog.askopenfilename(title="Choose the source-code file")
        if path:
            self.file_path = path
            self.file_label.configure(text=self._file_text())
            if not self.title_var.get().strip():
                self.title_var.set(os.path.splitext(os.path.basename(path))[0].replace("_", " ").replace("-", " ").title())

    def pick_thumb(self):
        path = filedialog.askopenfilename(title="Choose a preview image",
                                          filetypes=[("Images", "*.png *.jpg *.jpeg *.gif *.webp")])
        if path:
            self.thumb_path = path
            self.thumb_label.configure(text=os.path.basename(path))
            self.remove_thumb.set(0)

    # ---- saving
    def submit(self):
        if self.busy:
            return
        title = self.title_var.get().strip()
        if len(title) < 2:
            return messagebox.showwarning("Missing title", "Please enter a project title (at least 2 characters).")
        if not self.project and not self.file_path:
            return messagebox.showwarning("Missing file", "Please choose the source-code file to upload.")
        if self.file_path:
            ext = os.path.splitext(self.file_path)[1].lstrip(".").lower()
            if self.allowed and ext not in self.allowed:
                return messagebox.showwarning(
                    "File type not allowed",
                    "'.%s' files are not allowed.\nAllowed: %s\n\n(You can add more types under Website Content > Settings.)"
                    % (ext, ", ".join(sorted(self.allowed))))

        cat_index = self.cat_box.current()
        category_id = self.categories[cat_index - 1]["id"] if cat_index > 0 else ""
        language_ids = ",".join(str(self.languages[i]["id"]) for i in self.lang_list.curselection())
        fields = {"title": title, "description": self.desc.get("1.0", "end").strip(),
                  "category_id": category_id, "language_ids": language_ids}
        if self.project and self.remove_thumb.get():
            fields["remove_thumbnail"] = "1"

        def progress(sent, total):               # runs in the background thread
            self.progress_state = (sent, total)

        if self.project:
            work = lambda: self.app.api.update_project(self.project["id"], fields, self.file_path, self.thumb_path, progress)
        else:
            work = lambda: self.app.api.create_project(fields, self.file_path, self.thumb_path, progress)

        self.busy = True
        self.progress_state = (0, 1)
        self.submit_btn.configure(state="disabled", text="Uploading...")
        self.status.configure(text="Starting upload...", fg=theme.MUTED)
        self._poll()
        self.app.run_async(work, self._saved, self._failed)

    def _poll(self):
        if not self.busy:
            return
        try:
            sent, total = self.progress_state
            pct = int(sent * 100 / total) if total else 0
            self.bar["value"] = pct
            if sent >= total and total > 1:
                self.status.configure(text="Processing on the server...")
            elif sent:
                self.status.configure(text="Uploading... %d%% (%s of %s)" % (pct, theme.human_size(sent), theme.human_size(total)))
            self.after(120, self._poll)
        except tk.TclError:
            pass

    def _saved(self, project):
        self.busy = False
        try:
            self.bar["value"] = 100
            self.submit_btn.configure(state="normal", text="Publish" if not self.project else "Save changes")
            self.status.configure(text="Done! It is live on the website.", fg=theme.GREEN)
        except tk.TclError:
            pass
        if self.on_saved:
            self.on_saved(project)

    def _failed(self, exc):
        self.busy = False
        try:
            self.bar["value"] = 0
            self.submit_btn.configure(state="normal", text="Publish" if not self.project else "Save changes")
            self.status.configure(text="Failed.", fg=theme.RED)
        except tk.TclError:
            pass
        self.app.handle_error(exc)


class UploadPage(Page):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.header("Publish a project", "Upload a file, add its details, click Publish - it appears on the website immediately")
        self.box = theme.card(self, padx=22, pady=20)
        self.box.pack(fill="both", expand=True)
        self.form = None
        self._build()

    def _build(self):
        if self.form:
            self.form.destroy()
        self.form = ProjectForm(self.box, self.app, bg=theme.CARD, on_saved=self._published)
        self.form.pack(fill="both", expand=True)

    def _published(self, project):
        self.app.toast("Published: %s" % project["title"])
        self.app.pages["projects"].dirty = True
        if messagebox.askyesno("Published", "'%s' is now live on the website.\n\nOpen it in your browser?" % project["title"]):
            webbrowser.open("%s/project/%d" % (self.app.api.base_url, project["id"]))
        self._build()               # fresh empty form for the next project

    def refresh(self):
        # Categories / tags may have changed since the form was built.
        if self.form and not self.form.busy:
            self.form.load_choices()


class EditDialog(tk.Toplevel):
    def __init__(self, app, project, on_saved):
        super().__init__(app.root, bg=theme.CARD)
        self.title("Edit project #%d" % project["id"])
        self.transient(app.root)
        self.on_saved = on_saved
        body = tk.Frame(self, bg=theme.CARD, padx=22, pady=20)
        body.pack(fill="both", expand=True)
        theme.label(body, "Edit project", theme.FONT_H2, bg=theme.CARD).pack(anchor="w", pady=(0, 10))
        ProjectForm(body, app, project, self._saved, bg=theme.CARD).pack(fill="both", expand=True)
        self.grab_set()
        app.center(self, 820, 620)

    def _saved(self, project):
        self.on_saved(project)
        self.destroy()


# ====================================================================== projects list
class ProjectsPage(Page):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.dirty = True
        self.rows = []
        self.header("All projects", "Search, edit, delete and see downloads")

        bar = tk.Frame(self, bg=theme.BG)
        bar.pack(fill="x", pady=(0, 10))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._filter())
        theme.label(bar, "Search:", theme.FONT_SMALL, theme.MUTED).pack(side="left")
        theme.entry(bar, self.search_var, width=32).pack(side="left", padx=(6, 14), ipady=5)
        self.cat_var = tk.StringVar(value="All categories")
        self.cat_box = ttk.Combobox(bar, textvariable=self.cat_var, state="readonly", width=22,
                                    values=["All categories"])
        self.cat_box.pack(side="left")
        self.cat_box.bind("<<ComboboxSelected>>", lambda _e: self._filter())
        theme.button(bar, "Refresh", self.refresh, "ghost", pady=5).pack(side="right")

        cols = [("id", "ID"), ("title", "Title"), ("cat", "Category"), ("langs", "Languages"),
                ("type", "Type"), ("size", "Size"), ("dl", "Downloads"), ("date", "Uploaded")]
        frame, self.tree = theme.make_table(self, cols, [45, 240, 130, 150, 55, 80, 80, 95], 14)
        frame.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda _e: self.edit())

        actions = tk.Frame(self, bg=theme.BG)
        actions.pack(fill="x", pady=(10, 0))
        theme.button(actions, "Edit", self.edit).pack(side="left")
        theme.button(actions, "Downloads details", self.details, "ghost").pack(side="left", padx=8)
        theme.button(actions, "Open on website", self.open_site, "ghost").pack(side="left")
        theme.button(actions, "Delete", self.delete, "danger").pack(side="right")
        self.summary = theme.label(actions, "", theme.FONT_SMALL, theme.MUTED)
        self.summary.pack(side="right", padx=14)

    def refresh(self):
        self.dirty = False
        self.app.run_async(lambda: (self.app.api.projects(), self.app.api.categories()), self._loaded)

    def _loaded(self, result):
        self.rows, categories = result
        self.cat_box.configure(values=["All categories"] + [c["name"] for c in categories])
        self._filter()

    def _filter(self):
        q = self.search_var.get().strip().lower()
        cat = self.cat_var.get()
        self.tree.delete(*self.tree.get_children())
        shown = total_dl = 0
        for p in self.rows:
            langs = ", ".join(l["name"] for l in p["languages"])
            if cat != "All categories" and p["category"] != cat:
                continue
            if q and q not in (p["title"] + " " + p["description"] + " " + p["category"] + " " + langs).lower():
                continue
            self.tree.insert("", "end", iid=str(p["id"]), values=(
                p["id"], p["title"], p["category"], langs, "." + p["file"]["extension"],
                theme.human_size(p["file"]["size_bytes"]), p["downloads"], p["created_at"][:10]))
            shown += 1
            total_dl += p["downloads"]
        self.summary.configure(text="%d project(s) shown - %d download(s)" % (shown, total_dl))

    def _selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select a project", "Please click a project in the table first.")
            return None
        return next(p for p in self.rows if str(p["id"]) == sel[0])

    def edit(self):
        p = self._selected()
        if p:
            EditDialog(self.app, p, lambda _p: (self.app.toast("Project updated"), self.refresh()))

    def delete(self):
        p = self._selected()
        if not p:
            return
        if not messagebox.askyesno(
                "Delete project",
                "Delete '%s'?\n\nIt will disappear from the website and its stored file will be "
                "permanently deleted.\nThis cannot be undone." % p["title"], icon="warning"):
            return
        self.app.run_async(lambda: self.app.api.delete_project(p["id"]),
                           lambda _r: (self.app.toast("Deleted: %s" % p["title"]), self.refresh()))

    def open_site(self):
        p = self._selected()
        if p:
            webbrowser.open("%s/project/%d" % (self.app.api.base_url, p["id"]))

    def details(self):
        p = self._selected()
        if p:
            self.app.run_async(lambda: self.app.api.project(p["id"]), self._show_details)

    def _show_details(self, p):
        win = tk.Toplevel(self.app.root, bg=theme.PANEL)
        win.title("Downloads - " + p["title"])
        win.transient(self.app.root)
        body = tk.Frame(win, bg=theme.PANEL, padx=24, pady=20)
        body.pack()
        theme.label(body, p["title"], theme.FONT_H2, bg=theme.PANEL, wraplength=380).pack(anchor="w")
        theme.label(body, "%d total downloads" % p["downloads"], theme.FONT_BOLD, theme.PURPLE_SOFT, bg=theme.PANEL).pack(anchor="w", pady=(4, 10))
        theme.label(body, "Last 30 days", theme.FONT_SMALL, theme.MUTED, bg=theme.PANEL).pack(anchor="w")
        days = p.get("downloads_last_30_days", [])
        if not days:
            theme.label(body, "No downloads in the last 30 days.", bg=theme.PANEL).pack(anchor="w", pady=6)
        biggest = max([d["n"] for d in days] or [1])
        for d in days[-14:]:
            row = tk.Frame(body, bg=theme.PANEL)
            row.pack(fill="x", pady=1)
            theme.label(row, d["day"], theme.FONT_SMALL, theme.MUTED, bg=theme.PANEL, width=11).pack(side="left")
            tk.Frame(row, bg=theme.PURPLE, height=10, width=max(4, int(220 * d["n"] / biggest))).pack(side="left")
            theme.label(row, " %d" % d["n"], theme.FONT_SMALL, bg=theme.PANEL).pack(side="left")
        theme.button(body, "Close", win.destroy, "ghost").pack(anchor="e", pady=(14, 0))
        self.app.center(win)


# ====================================================================== categories & languages
class NamedListPage(Page):
    """Manage categories (name + description) or programming-language tags (name only)."""

    def __init__(self, parent, app, kind):
        super().__init__(parent, app)
        self.kind = kind                                      # "categories" or "languages"
        self.is_cat = kind == "categories"
        self.rows = []
        word = "category" if self.is_cat else "language tag"
        self.header("Categories" if self.is_cat else "Programming-language tags",
                    "Organize how visitors browse your projects" if self.is_cat else "Tags shown on every project card")

        add = theme.card(self, padx=16, pady=12)
        add.pack(fill="x", pady=(0, 12))
        self.name_var = tk.StringVar()
        self.desc_var = tk.StringVar()
        theme.label(add, "New %s:" % word, theme.FONT_BOLD, bg=theme.CARD).pack(side="left")
        e = theme.entry(add, self.name_var, width=24)
        e.pack(side="left", padx=8, ipady=5)
        e.bind("<Return>", lambda _e: self.add())
        if self.is_cat:
            theme.label(add, "Description:", theme.FONT_SMALL, theme.MUTED, bg=theme.CARD).pack(side="left", padx=(8, 0))
            theme.entry(add, self.desc_var, width=34).pack(side="left", padx=8, ipady=5)
        theme.button(add, "Add", self.add).pack(side="left")

        cols = [("id", "ID"), ("name", "Name")] + ([("desc", "Description")] if self.is_cat else []) + [("n", "Projects")]
        widths = [50, 200] + ([320] if self.is_cat else []) + [80]
        frame, self.tree = theme.make_table(self, cols, widths, 12)
        frame.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda _e: self.edit())

        actions = tk.Frame(self, bg=theme.BG)
        actions.pack(fill="x", pady=(10, 0))
        theme.button(actions, "Rename / Edit", self.edit).pack(side="left")
        theme.button(actions, "Delete", self.delete, "danger").pack(side="right")
        self.note = "Projects in a deleted category become 'Uncategorized' (they are not deleted)." if self.is_cat \
            else "Deleting a tag removes it from all projects."
        theme.label(actions, self.note, theme.FONT_SMALL, theme.MUTED).pack(side="right", padx=14)

    def refresh(self):
        fetch = self.app.api.categories if self.is_cat else self.app.api.languages
        self.app.run_async(fetch, self._loaded)

    def _loaded(self, rows):
        self.rows = rows
        self.tree.delete(*self.tree.get_children())
        for r in rows:
            values = [r["id"], r["name"]] + ([r["description"]] if self.is_cat else []) + [r["projects"]]
            self.tree.insert("", "end", iid=str(r["id"]), values=values)

    def _done(self, message):
        self.app.toast(message)
        self.app.pages["projects"].dirty = True
        self.refresh()

    def add(self):
        name = self.name_var.get().strip()
        if not name:
            return messagebox.showinfo("Name needed", "Please type a name first.")
        body = {"name": name}
        if self.is_cat:
            body["description"] = self.desc_var.get().strip()
        self.app.run_async(lambda: self.app.api.post_json("/api/" + self.kind, body),
                           lambda _r: (self.name_var.set(""), self.desc_var.set(""), self._done("Added: " + name)))

    def _selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select a row", "Please click a row in the table first.")
            return None
        return next(r for r in self.rows if str(r["id"]) == sel[0])

    def edit(self):
        r = self._selected()
        if not r:
            return
        fields = [("name", "Name", r["name"])] + ([("description", "Description", r["description"])] if self.is_cat else [])

        def save(values):
            self.app.run_async(lambda: self.app.api.put_json("/api/%s/%d" % (self.kind, r["id"]), values),
                               lambda _r: self._done("Saved"))
        FormDialog(self.app, "Edit " + ("category" if self.is_cat else "language tag"), fields, save)

    def delete(self):
        r = self._selected()
        if r and messagebox.askyesno("Delete", "Delete '%s'?\n\n%s" % (r["name"], self.note), icon="warning"):
            self.app.run_async(lambda: self.app.api.delete("/api/%s/%d" % (self.kind, r["id"])),
                               lambda _r: self._done("Deleted: " + r["name"]))


# ====================================================================== settings / website content
class SettingsPage(Page):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.header("Website content & settings", "Edit the text shown on the public website")
        cols = tk.Frame(self, bg=theme.BG)
        cols.pack(fill="both", expand=True)
        left = theme.card(cols, padx=18, pady=14)
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))
        right = tk.Frame(cols, bg=theme.BG)
        right.pack(side="left", fill="both")

        self.vars = {}
        for key, text in (("site_name", "Website name"), ("tagline", "Tagline"),
                          ("hero_title", "Homepage headline"), ("hero_subtitle", "Homepage sub-headline"),
                          ("contact_email", "Public contact email"), ("footer_text", "Footer text")):
            theme.label(left, text, theme.FONT_SMALL, theme.MUTED, bg=theme.CARD).pack(anchor="w", pady=(6, 1))
            self.vars[key] = tk.StringVar()
            theme.entry(left, self.vars[key], width=50).pack(fill="x", ipady=4)
        theme.label(left, "About text", theme.FONT_SMALL, theme.MUTED, bg=theme.CARD).pack(anchor="w", pady=(8, 1))
        self.about = theme.textbox(left, height=5)
        self.about.pack(fill="x")

        box = theme.card(right, padx=18, pady=14)
        box.pack(fill="x")
        theme.label(box, "Uploads", theme.FONT_H2, bg=theme.CARD).pack(anchor="w")
        theme.label(box, "Allowed file extensions (comma separated)", theme.FONT_SMALL, theme.MUTED, bg=theme.CARD).pack(anchor="w", pady=(8, 1))
        self.vars["allowed_extensions"] = tk.StringVar()
        theme.entry(box, self.vars["allowed_extensions"], width=36).pack(fill="x", ipady=4)
        self.blocked = theme.label(box, "", theme.FONT_SMALL, theme.MUTED, bg=theme.CARD, wraplength=300, justify="left")
        self.blocked.pack(anchor="w", pady=(2, 0))
        theme.label(box, "Maximum upload size (MB)", theme.FONT_SMALL, theme.MUTED, bg=theme.CARD).pack(anchor="w", pady=(8, 1))
        self.vars["max_upload_mb"] = tk.StringVar()
        theme.entry(box, self.vars["max_upload_mb"], width=10).pack(anchor="w", ipady=4)

        pw = theme.card(right, padx=18, pady=14)
        pw.pack(fill="x", pady=(12, 0))
        theme.label(pw, "Change admin password", theme.FONT_H2, bg=theme.CARD).pack(anchor="w")
        self.pw_vars = {}
        for key, text in (("current", "Current password"), ("new", "New password (min 8)"), ("again", "Repeat new password")):
            theme.label(pw, text, theme.FONT_SMALL, theme.MUTED, bg=theme.CARD).pack(anchor="w", pady=(6, 1))
            self.pw_vars[key] = tk.StringVar()
            theme.entry(pw, self.pw_vars[key], width=36, show="*").pack(fill="x", ipady=4)
        theme.button(pw, "Change password", self.change_password, "ghost").pack(anchor="w", pady=(10, 0))

        bottom = tk.Frame(self, bg=theme.BG)
        bottom.pack(fill="x", pady=(12, 0))
        theme.button(bottom, "Save website settings", self.save, pady=10).pack(side="left")

    def refresh(self):
        self.app.run_async(self.app.api.settings, self._loaded)

    def _loaded(self, data):
        s = data["settings"]
        for key, var in self.vars.items():
            var.set(s.get(key, ""))
        self.about.delete("1.0", "end")
        self.about.insert("1.0", s.get("about_text", ""))
        self.blocked.configure(text="Never allowed (security): " + ", ".join(data["blocked_extensions"]) +
                               "\nServer limit: %s MB" % data["hard_max_upload_mb"])

    def save(self):
        values = {k: v.get().strip() for k, v in self.vars.items()}
        values["about_text"] = self.about.get("1.0", "end").strip()
        self.app.run_async(lambda: self.app.api.save_settings(values),
                           lambda _r: (self.app.toast("Settings saved - the website is updated"), self.refresh()))

    def change_password(self):
        p = {k: v.get() for k, v in self.pw_vars.items()}
        if p["new"] != p["again"]:
            return messagebox.showwarning("Passwords differ", "The new password and the repeat do not match.")

        def done(_r):
            for v in self.pw_vars.values():
                v.set("")
            self.app.toast("Password changed")
        self.app.run_async(lambda: self.app.api.change_password(p["current"], p["new"]), done)


# ====================================================================== messages
class MessagesPage(Page):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.rows = []
        self.header("Messages", "Messages sent from the website contact form")
        cols = [("date", "Date"), ("name", "Name"), ("email", "Email"), ("text", "Message"), ("status", "Status")]
        frame, self.tree = theme.make_table(self, cols, [120, 130, 180, 300, 60], 9)
        frame.pack(fill="x")
        self.tree.bind("<<TreeviewSelect>>", self._select)
        self.view = theme.textbox(self, height=8)
        self.view.pack(fill="both", expand=True, pady=10)
        self.view.configure(state="disabled")
        actions = tk.Frame(self, bg=theme.BG)
        actions.pack(fill="x")
        theme.button(actions, "Refresh", self.refresh, "ghost").pack(side="left")
        theme.button(actions, "Delete message", self.delete, "danger").pack(side="right")

    def refresh(self):
        self.app.run_async(self.app.api.messages, self._loaded)

    def _loaded(self, rows):
        self.rows = rows
        self.tree.delete(*self.tree.get_children())
        for m in rows:
            self.tree.insert("", "end", iid=str(m["id"]), values=(
                m["created_at"][:16], m["name"], m["email"], m["message"].replace("\n", " ")[:80],
                "read" if m["is_read"] else "NEW"))
        self.app.set_unread(sum(1 for m in rows if not m["is_read"]))

    def _current(self):
        sel = self.tree.selection()
        return next((m for m in self.rows if str(m["id"]) == sel[0]), None) if sel else None

    def _select(self, _e=None):
        m = self._current()
        if not m:
            return
        self.view.configure(state="normal")
        self.view.delete("1.0", "end")
        self.view.insert("1.0", "From: %s <%s>\nDate: %s\n\n%s" % (m["name"], m["email"], m["created_at"], m["message"]))
        self.view.configure(state="disabled")
        if not m["is_read"]:
            m["is_read"] = 1
            self.tree.set(str(m["id"]), "status", "read")
            self.app.set_unread(sum(1 for x in self.rows if not x["is_read"]))
            self.app.run_async(lambda: self.app.api.post_json("/api/messages/%d/read" % m["id"]), lambda _r: None)

    def delete(self):
        m = self._current()
        if m and messagebox.askyesno("Delete message", "Delete the message from %s?" % m["name"]):
            self.app.run_async(lambda: self.app.api.delete("/api/messages/%d" % m["id"]), lambda _r: self.refresh())
