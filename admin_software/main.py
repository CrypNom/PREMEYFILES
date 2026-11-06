"""
main.py - PREMEYFILES ADMIN (desktop application)

Start it with:   python main.py
"""
import queue
import threading
import tkinter as tk
from tkinter import messagebox

import theme
from api_client import ApiClient, ApiError
from login import LoginFrame
from pages import (DashboardPage, MessagesPage, NamedListPage, ProjectsPage,
                   SettingsPage, UploadPage)

NAV = [
    ("dashboard", "Dashboard"),
    ("projects", "All Projects"),
    ("upload", "Publish New"),
    ("categories", "Categories"),
    ("languages", "Language Tags"),
    ("settings", "Website Content"),
    ("messages", "Messages"),
]


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("PREMEYFILES ADMIN")
        self.root.minsize(1000, 640)
        theme.setup_styles(self.root)
        self.center(self.root, 1180, 720)

        self.api = ApiClient()
        self.results = queue.Queue()
        self.current = None
        self.view = None
        self.pages = {}
        self.nav_buttons = {}
        self._toast_job = None
        self.root.after(50, self._drain)
        self.root.protocol("WM_DELETE_WINDOW", self.quit)

    # ------------------------------------------------------------ background work
    def run_async(self, work, on_done=None, on_error=None):
        """Run `work()` in a thread so the window never freezes, then call
        on_done(result) or on_error(exception) back in the main thread."""
        def target():
            try:
                self.results.put((on_done, work(), None, on_error))
            except Exception as exc:                      # noqa - shown to the user
                self.results.put((on_done, None, exc, on_error))
        threading.Thread(target=target, daemon=True).start()

    def _drain(self):
        try:
            while True:
                on_done, result, exc, on_error = self.results.get_nowait()
                try:
                    if exc is not None:
                        (on_error or self.handle_error)(exc)
                    elif on_done:
                        on_done(result)
                except tk.TclError:
                    pass                                   # the widget was closed meanwhile
        except queue.Empty:
            pass
        self.root.after(50, self._drain)

    def handle_error(self, exc):
        if isinstance(exc, ApiError) and exc.status == 401:
            if self.api.token:                  # first expired request: back to the login screen
                self.api.token = None
                self.show_login(str(exc))
            return                              # later requests that fail the same way: stay quiet
        text = str(exc) if isinstance(exc, ApiError) else "Unexpected error: %r" % exc
        messagebox.showerror("Something went wrong", text)

    # ------------------------------------------------------------ helpers
    def center(self, win, width=None, height=None):
        win.update_idletasks()
        width = width or win.winfo_reqwidth()
        height = height or win.winfo_reqheight()
        x = max(0, (win.winfo_screenwidth() - width) // 2)
        y = max(0, (win.winfo_screenheight() - height) // 3)
        win.geometry("%dx%d+%d+%d" % (width, height, x, y))

    def toast(self, text):
        if not hasattr(self, "status"):
            return
        self.status.configure(text="  " + text)
        if self._toast_job:
            self.root.after_cancel(self._toast_job)
        self._toast_job = self.root.after(5000, lambda: self.status.configure(text=""))

    def set_unread(self, count):
        if "messages" in self.nav_buttons:
            self.nav_buttons["messages"].configure(text="Messages (%d)" % count if count else "Messages")

    # ------------------------------------------------------------ screens
    def _clear(self):
        if self.view is not None:
            self.view.destroy()
        self.view = None
        self.pages = {}
        self.nav_buttons = {}
        self.current = None

    def show_login(self, message=""):
        self._clear()
        self.view = LoginFrame(self.root, self, message)
        self.view.pack(fill="both", expand=True)

    def show_main(self):
        self._clear()
        self.view = tk.Frame(self.root, bg=theme.BG)
        self.view.pack(fill="both", expand=True)

        side = tk.Frame(self.view, bg=theme.PANEL, width=220)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        theme.label(side, "</> PREMEYFILES", theme.FONT_H2, theme.PURPLE_SOFT, bg=theme.PANEL).pack(pady=(22, 0), padx=18, anchor="w")
        theme.label(side, "ADMIN", theme.FONT_SMALL, theme.MUTED, bg=theme.PANEL).pack(padx=18, anchor="w", pady=(0, 20))

        main = tk.Frame(self.view, bg=theme.BG)
        main.pack(side="left", fill="both", expand=True)
        content = tk.Frame(main, bg=theme.BG, padx=26, pady=22)
        content.pack(fill="both", expand=True)
        self.status = tk.Label(main, text="", bg=theme.PANEL, fg=theme.PURPLE_SOFT, anchor="w", font=theme.FONT_SMALL, pady=5)
        self.status.pack(fill="x", side="bottom")

        self.pages = {
            "dashboard": DashboardPage(content, self),
            "projects": ProjectsPage(content, self),
            "upload": UploadPage(content, self),
            "categories": NamedListPage(content, self, "categories"),
            "languages": NamedListPage(content, self, "languages"),
            "settings": SettingsPage(content, self),
            "messages": MessagesPage(content, self),
        }
        for key, text in NAV:
            b = theme.button(side, text, lambda k=key: self.navigate(k), "nav", anchor="w", padx=20, pady=10)
            b.pack(fill="x")
            self.nav_buttons[key] = b

        bottom = tk.Frame(side, bg=theme.PANEL)
        bottom.pack(side="bottom", fill="x", pady=16, padx=14)
        theme.label(bottom, "Signed in as %s" % self.api.username, theme.FONT_SMALL, theme.MUTED, bg=theme.PANEL).pack(anchor="w")
        theme.label(bottom, self.api.base_url, theme.FONT_SMALL, theme.MUTED, bg=theme.PANEL, wraplength=180, justify="left").pack(anchor="w", pady=(0, 8))
        theme.button(bottom, "Log out", self.logout, "ghost", pady=6).pack(fill="x")

        self.navigate("dashboard")

    def navigate(self, key):
        if self.current:
            self.pages[self.current].pack_forget()
            self.nav_buttons[self.current]._normal = theme.PANEL
            self.nav_buttons[self.current].configure(bg=theme.PANEL, fg=theme.MUTED)
        self.current = key
        page = self.pages[key]
        page.pack(fill="both", expand=True)
        btn = self.nav_buttons[key]
        btn._normal = theme.CARD
        btn.configure(bg=theme.CARD, fg=theme.PURPLE_SOFT)
        page.refresh()          # always load fresh data from the website

    def logout(self):
        token_api = self.api
        self.run_async(token_api.logout)          # tell the server to forget the token
        self.show_login()

    def quit(self):
        self.root.destroy()

    def run(self):
        self.show_login()
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
