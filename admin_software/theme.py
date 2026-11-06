"""
theme.py - Colors, fonts and small reusable widgets (dark + purple).
"""
import tkinter as tk
from tkinter import ttk

BG = "#0b0714"
PANEL = "#130c24"
CARD = "#1a1130"
FIELD = "#0f0a1c"
BORDER = "#2d1f4d"
PURPLE = "#a855f7"
PURPLE_DARK = "#7c3aed"
PURPLE_SOFT = "#c084fc"
TEXT = "#f1ebfa"
MUTED = "#9d93b4"
RED = "#ef4444"
RED_DARK = "#b91c1c"
GREEN = "#22c55e"

FONT = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_SMALL = ("Segoe UI", 9)
FONT_H1 = ("Segoe UI", 20, "bold")
FONT_H2 = ("Segoe UI", 13, "bold")
FONT_BIG = ("Segoe UI", 24, "bold")


def setup_styles(root):
    style = ttk.Style(root)
    style.theme_use("clam")
    root.configure(bg=BG)
    root.option_add("*Font", FONT)
    root.option_add("*TCombobox*Listbox.background", FIELD)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", PURPLE_DARK)
    root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")

    style.configure("Treeview", background=CARD, fieldbackground=CARD, foreground=TEXT,
                    rowheight=30, borderwidth=0, bordercolor=BORDER, lightcolor=CARD, darkcolor=CARD, font=FONT)
    style.configure("Treeview.Heading", background=PANEL, foreground=PURPLE_SOFT, font=FONT_BOLD,
                    relief="flat", padding=6)
    style.map("Treeview", background=[("selected", PURPLE_DARK)], foreground=[("selected", "#ffffff")])
    style.map("Treeview.Heading", background=[("active", BORDER)])

    style.configure("TCombobox", fieldbackground=FIELD, background=BORDER, foreground=TEXT,
                    arrowcolor=PURPLE_SOFT, bordercolor=BORDER, lightcolor=FIELD, darkcolor=FIELD, padding=5)
    style.map("TCombobox", fieldbackground=[("readonly", FIELD)], foreground=[("readonly", TEXT)],
              selectbackground=[("readonly", FIELD)], selectforeground=[("readonly", TEXT)])

    style.configure("Vertical.TScrollbar", background=BORDER, troughcolor=PANEL, bordercolor=PANEL,
                    arrowcolor=PURPLE_SOFT, lightcolor=BORDER, darkcolor=BORDER)
    style.configure("Horizontal.TProgressbar", background=PURPLE, troughcolor=FIELD,
                    bordercolor=BORDER, lightcolor=PURPLE, darkcolor=PURPLE)


def button(parent, text, command, kind="primary", **kw):
    colors = {
        "primary": (PURPLE_DARK, PURPLE, "#ffffff"),
        "ghost": (CARD, BORDER, TEXT),
        "danger": (RED_DARK, RED, "#ffffff"),
        "nav": (PANEL, CARD, MUTED),
    }
    normal, hover, fg = colors[kind]
    b = tk.Button(parent, text=text, command=command, bg=normal, fg=fg, activebackground=hover,
                  activeforeground="#ffffff", relief="flat", bd=0, cursor="hand2", highlightthickness=0,
                  font=FONT_BOLD if kind != "nav" else FONT, padx=kw.pop("padx", 16), pady=kw.pop("pady", 8), **kw)
    b._normal, b._hover = normal, hover
    b.bind("<Enter>", lambda e: b.configure(bg=b._hover) if str(b["state"]) != "disabled" else None)
    b.bind("<Leave>", lambda e: b.configure(bg=b._normal))
    return b


def label(parent, text, font=FONT, fg=TEXT, bg=None, **kw):
    return tk.Label(parent, text=text, font=font, fg=fg, bg=bg or parent["bg"], **kw)


def entry(parent, textvariable=None, width=30, show=None):
    return tk.Entry(parent, textvariable=textvariable, width=width, show=show, bg=FIELD, fg=TEXT,
                    insertbackground=TEXT, relief="flat", highlightthickness=1,
                    highlightbackground=BORDER, highlightcolor=PURPLE, font=FONT)


def textbox(parent, height=6, width=40):
    return tk.Text(parent, height=height, width=width, bg=FIELD, fg=TEXT, insertbackground=TEXT,
                   relief="flat", highlightthickness=1, highlightbackground=BORDER,
                   highlightcolor=PURPLE, font=FONT, wrap="word", padx=6, pady=6, undo=True)


def card(parent, **kw):
    return tk.Frame(parent, bg=CARD, highlightthickness=1, highlightbackground=BORDER, **kw)


def make_table(parent, columns, widths, height=14):
    """A Treeview table with a scrollbar. columns = list of (id, heading)."""
    frame = tk.Frame(parent, bg=CARD)
    tree = ttk.Treeview(frame, columns=[c[0] for c in columns], show="headings",
                        height=height, selectmode="browse")
    for (col_id, heading), width in zip(columns, widths):
        tree.heading(col_id, text=heading)
        tree.column(col_id, width=width, minwidth=40, anchor="w")
    scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    return frame, tree


def human_size(num):
    num = float(num or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024 or unit == "GB":
            return "%d %s" % (num, unit) if unit == "B" else "%.1f %s" % (num, unit)
        num /= 1024
