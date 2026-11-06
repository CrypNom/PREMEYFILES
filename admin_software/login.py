"""
login.py - The login screen of PREMEYFILES ADMIN.

The server address is remembered. The password is NEVER saved.
"""
import tkinter as tk

import theme
from api_client import ApiError, load_server_url


class LoginFrame(tk.Frame):
    def __init__(self, parent, app, message=""):
        super().__init__(parent, bg=theme.BG)
        self.app = app
        self.busy = False

        box = theme.card(self, padx=40, pady=34)
        box.place(relx=0.5, rely=0.5, anchor="center")

        theme.label(box, "</>  PREMEYFILES", theme.FONT_H1, theme.PURPLE_SOFT).pack()
        theme.label(box, "ADMIN", theme.FONT_BOLD, theme.MUTED).pack(pady=(0, 20))

        self.url_var = tk.StringVar(value=load_server_url())
        self.user_var = tk.StringVar()
        self.pass_var = tk.StringVar()

        for text, var, show in (("Website address", self.url_var, None),
                                ("Username", self.user_var, None),
                                ("Password", self.pass_var, "*")):
            theme.label(box, text, theme.FONT_SMALL, theme.MUTED).pack(anchor="w", pady=(8, 2))
            e = theme.entry(box, var, width=34, show=show)
            e.pack(fill="x", ipady=6)
            e.bind("<Return>", lambda _e: self.submit())
            if text == "Username":
                self.user_entry = e
            if text == "Password":
                self.pass_entry = e

        self.msg = theme.label(box, message, theme.FONT_SMALL, theme.RED, wraplength=300, justify="left")
        self.msg.pack(anchor="w", pady=(10, 0))

        self.button = theme.button(box, "Log in", self.submit)
        self.button.pack(fill="x", pady=(14, 0))
        self.user_entry.focus_set()

    def submit(self):
        if self.busy:
            return
        username, password = self.user_var.get().strip(), self.pass_var.get()
        if not username or not password:
            self.msg.configure(text="Please enter your username and password.", fg=theme.RED)
            return
        self.busy = True
        self.button.configure(text="Connecting...", state="disabled")
        self.msg.configure(text="")

        url = self.url_var.get()      # read Tk values here: background threads must not touch Tk
        self.app.run_async(
            lambda: self.app.api.login(url, username, password),
            on_done=self._ok, on_error=self._fail,
        )

    def _ok(self, _result):
        self.pass_var.set("")
        self.app.show_main()

    def _fail(self, exc):
        self.busy = False
        self.button.configure(text="Log in", state="normal")
        text = str(exc) if isinstance(exc, ApiError) else "Unexpected error: %s" % exc
        self.msg.configure(text=text, fg=theme.RED)
        self.pass_var.set("")
        self.pass_entry.focus_set()
