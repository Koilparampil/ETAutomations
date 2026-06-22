from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
from dataclasses import dataclass, field


@dataclass
class UserInputs:
    username: str = ""
    password: str = ""


def get_user_inputs(title:str) -> UserInputs:
    root = tk.Tk()
    root.title(title)
    root.resizable(False, False)

    result: UserInputs | None = None

    # --- Variables ---
    username_var = tk.StringVar(master=root)
    password_var = tk.StringVar(master=root)

    def submit():
        nonlocal result
        username = username_var.get().strip()
        password = password_var.get()  # don't strip passwords

        if not username:
            messagebox.showerror("Missing info", "Please enter a username.")
            return
        if not password:
            messagebox.showerror("Missing info", "Please enter a password.")
            return

        result = UserInputs(username=username, password=password)
        root.destroy()

    def cancel():
        root.destroy()

    # --- Layout ---
    pad = {"padx": 10, "pady": 6}

    tk.Label(root, text="Username").grid(row=1, column=0, sticky="e", **pad)
    user_entry = tk.Entry(root, textvariable=username_var, width=42)
    user_entry.grid(row=1, column=1, columnspan=2, sticky="we", **pad)

    tk.Label(root, text="Password").grid(row=2, column=0, sticky="e", **pad)
    pass_entry = tk.Entry(root, textvariable=password_var, show="*", width=42)
    pass_entry.grid(row=2, column=1, columnspan=2, sticky="we", **pad)

    btn_frame = tk.Frame(root)
    btn_frame.grid(row=3, column=0, columnspan=3, pady=(8, 12))

    tk.Button(btn_frame, text="Cancel", width=12, command=cancel).pack(side="left", padx=6)
    tk.Button(btn_frame, text="Submit", width=12, command=submit).pack(side="left", padx=6)

    # Enter submits, Esc cancels
    root.bind("<Return>", lambda _e: submit())
    root.bind("<Escape>", lambda _e: cancel())

    # Focus order
    user_entry.focus_set()

    root.mainloop()

    if result is None:
        raise SystemExit("User cancelled.")
    return result
