from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
from dataclasses import dataclass

def is_valid_txt_file(path: str | Path) -> tuple[bool, str]:
    p = Path(path)

    if not p.exists():
        return False, "File does not exist."

    if not p.is_file():
        return False, "Path is not a file."

    if p.suffix.lower() != ".txt":
        return False, "File must have a .txt extension."
    return True, "OK"

@dataclass
class UserInputs:
    filename: str
    VSHIP_username: str
    VSHIP_password: str
    
    MSC_username: str
    MSC_password: str
    
@dataclass
class UserInputsAuthed:
    filename: str

def get_user_inputs() -> UserInputs:
    root = tk.Tk()
    root.title("ETA Tool Login")
    root.resizable(False, False)
    
    result: UserInputs | None = None
    
    # --- Variables ---
    filename_var = tk.StringVar()
    VSHIP_username_var = tk.StringVar()
    VSHIP_password_var = tk.StringVar()
    MSC_username_var = tk.StringVar()
    MSC_password_var = tk.StringVar()

    # --- Callbacks ---
    def browse_file():
        path = filedialog.askopenfilename(
            title="Select .txt file",
            filetypes=[("Text Files", "*.txt")],
        )
        if path:
            filename_var.set(path)

    def submit():
        nonlocal result
        filename = filename_var.get().strip()
        VSHIP_username = VSHIP_username_var.get().strip()
        VSHIP_password = VSHIP_password_var.get()  # don't strip VSHIP_passwords

        MSC_username = MSC_username_var.get().strip()
        MSC_password = MSC_password_var.get().strip()
        
        ok, reason = is_valid_txt_file(filename)
        if not ok:
            messagebox.showerror("Invalid file", reason)
            return
        if not Path(filename).exists():
            messagebox.showerror("File not found", "The selected file does not exist.")
            return
        if not VSHIP_username:
            messagebox.showerror("Missing info", "Please enter a VSHIP_username.")
            return
        if not VSHIP_password:
            messagebox.showerror("Missing info", "Please enter a VSHIP_password.")
            return

        # Store on the root so we can read it after mainloop exits
        result  = UserInputs(filename=filename, 
                             VSHIP_username=VSHIP_username, 
                             VSHIP_password=VSHIP_password,
                             MSC_username=MSC_username,
                             MSC_password=MSC_password )
        root.destroy()

    def cancel():
        root.destroy()

    # --- Layout ---
    pad = {"padx": 10, "pady": 10}

    tk.Label(root, text="FileName").grid(row=0, column=0, sticky="e", **pad) # type: ignore pyLint warning thing
    file_entry = tk.Entry(root, textvariable=filename_var, width=42)
    file_entry.grid(row=0, column=1, **pad)# type: ignore pyLint warning thing
    tk.Button(root, text="Browse...", command=browse_file).grid(row=0, column=2, **pad)# type: ignore pyLint warning thing


    tk.Label(root, text="VShip Username").grid(row=2, column=0, sticky="e", **pad)# type: ignore pyLint warning thing
    user_entry = tk.Entry(root, textvariable=VSHIP_username_var, width=42)
    user_entry.grid(row=2, column=1, columnspan=2, sticky="we", **pad)# type: ignore pyLint warning thing

    tk.Label(root, text="VShip Password").grid(row=3, column=0, sticky="e", **pad)# type: ignore pyLint warning thing
    pass_entry = tk.Entry(root, textvariable=VSHIP_password_var, show="*", width=42)
    pass_entry.grid(row=3, column=1, columnspan=2, sticky="we", **pad)# type: ignore pyLint warning thing
    
    
    
    tk.Label(root, text="MSC Username").grid(row=5, column=0, sticky="e", **pad)# type: ignore pyLint warning thing
    user_entry = tk.Entry(root, textvariable=MSC_username_var, width=42)
    user_entry.grid(row=5, column=1, columnspan=2, sticky="we", **pad)# type: ignore pyLint warning thing

    tk.Label(root, text="MSC Password").grid(row=6, column=0, sticky="e", **pad)# type: ignore pyLint warning thing
    pass_entry = tk.Entry(root, textvariable=MSC_password_var, show="*", width=42)
    pass_entry.grid(row=6, column=1, columnspan=2, sticky="we", **pad)# type: ignore pyLint warning thing
    
    
    btn_frame = tk.Frame(root)
    btn_frame.grid(row=7, column=0, columnspan=3, pady=(8, 12))

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

def get_user_inputs_authed() -> UserInputs:
    root = tk.Tk()
    root.title("ETA Tool Login")
    root.resizable(False, False)
    
    result: UserInputsAuthed | None = None
    
    # --- Variables ---
    filename_var = tk.StringVar()


    # --- Callbacks ---
    def browse_file():
        path = filedialog.askopenfilename(
            title="Select .txt file",
            filetypes=[("Text Files", "*.txt")],
        )
        if path:
            filename_var.set(path)

    def submit():
        nonlocal result
        filename = filename_var.get().strip()
        ok, reason = is_valid_txt_file(filename)
        if not ok:
            messagebox.showerror("Invalid file", reason)
            return
        if not Path(filename).exists():
            messagebox.showerror("File not found", "The selected file does not exist.")
            return

        # Store on the root so we can read it after mainloop exits
        result  = UserInputsAuthed(filename=filename)
        root.destroy()

    def cancel():
        root.destroy()

    # --- Layout ---
    pad = {"padx": 10, "pady": 10}

    tk.Label(root, text="FileName").grid(row=0, column=0, sticky="e", **pad) # type: ignore pyLint warning thing
    file_entry = tk.Entry(root, textvariable=filename_var, width=42)
    file_entry.grid(row=0, column=1, **pad)# type: ignore pyLint warning thing
    tk.Button(root, text="Browse...", command=browse_file).grid(row=0, column=2, **pad)# type: ignore pyLint warning thing

    btn_frame = tk.Frame(root)
    btn_frame.grid(row=7, column=0, columnspan=3, pady=(8, 12))

    tk.Button(btn_frame, text="Cancel", width=12, command=cancel).pack(side="left", padx=6)
    tk.Button(btn_frame, text="Submit", width=12, command=submit).pack(side="left", padx=6)

    # Enter submits, Esc cancels
    root.bind("<Return>", lambda _e: submit())
    root.bind("<Escape>", lambda _e: cancel())

    # Focus order
    file_entry.focus_set()

    root.mainloop()

    if result is None:
        raise SystemExit("User cancelled.")
    return result