import subprocess
import sys
from pathlib import Path
import tkinter as tk
from tkinter import messagebox
import os

APP_DIR = Path(__file__).parent.resolve()
OUT_DIR = APP_DIR / "pick_outputs"
PICK_WAVE = OUT_DIR / "pick_wave.csv"
PACK_ORDER = OUT_DIR / "pack_order.csv"
PICK_WAVE_XLSX = OUT_DIR / "pick_wave.xlsx"

SCRIPTS = {
    "Import Pull Sheet": "import_pull_sheet.py",
    "Generate Pick Wave": "generate_pick_wave.py",
    "Manual Card Lookup": "manual_card_lookup.py",
    "Batch Lookup": "batch_lookup.py",
    "Add / Update Batch": "batch_editor.py"
}

def open_file(path):
    if not path.exists():
        messagebox.showerror("Missing file", f"File not found:\n{path}")
        return
    os.startfile(path)

def run_script(script_name, status_label):
    script_path = APP_DIR / "scripts" / script_name

    if not script_path.exists():
        messagebox.showerror("Missing script", f"Could not find:\n{script_path}")
        return

    status_label.config(text=f"Running {script_name}...")
    status_label.update_idletasks()

    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(APP_DIR),
            text=True
        )

        if result.returncode != 0:
            messagebox.showerror(
                "Script failed",
                f"{script_name} exited with code {result.returncode}."
            )
            status_label.config(text="Error.")
            return

        status_label.config(text=f"Completed: {script_name}")

    except Exception as e:
        messagebox.showerror("Error", str(e))
        status_label.config(text="Error.")

def open_output_folder():
    OUT_DIR.mkdir(exist_ok=True)
    os.startfile(OUT_DIR)


def make_section(parent, title):
    frame = tk.LabelFrame(
        parent,
        text=f"  {title}  ",
        font=("Segoe UI", 10, "bold"),
        bg="#1f1f1f",
        fg="#dcdcdc",
        padx=14,
        pady=12,
        bd=1,
        relief="solid"
    )
    frame.pack(fill="x", padx=18, pady=9)
    return frame


def make_button(parent, text, command, accent=False):
    bg = "#2d5f8b" if accent else "#2b2b2b"
    active_bg = "#3674a8" if accent else "#3a3a3a"

    btn = tk.Button(
        parent,
        text=text,
        width=36,
        height=2,
        command=command,
        bg=bg,
        fg="#ffffff",
        activebackground=active_bg,
        activeforeground="#ffffff",
        relief="flat",
        bd=0,
        font=("Segoe UI", 10, "bold" if accent else "normal"),
        cursor="hand2"
    )
    btn.pack(pady=5)
    return btn


def main():
    root = tk.Tk()
    root.title("TCG Inventory Console")
    root.geometry("500x720")
    root.resizable(False, False)
    root.configure(bg="#121212")

    title = tk.Label(
        root,
        text="TCG Inventory Console",
        font=("Segoe UI", 20, "bold"),
        bg="#121212",
        fg="#ffffff"
    )
    title.pack(pady=(20, 4))

    subtitle = tk.Label(
        root,
        text="Fulfillment • Lookup • Batch Management",
        font=("Segoe UI", 10),
        bg="#121212",
        fg="#a6a6a6"
    )
    subtitle.pack(pady=(0, 10))

    status = tk.Label(
        root,
        text="Ready.",
        font=("Segoe UI", 10),
        bg="#121212",
        fg="#7fd37f"
    )
    status.pack(pady=(0, 8))

    fulfillment = make_section(root, "ORDER FULFILLMENT")

    make_button(
        fulfillment,
        "1. Import Pull Sheet",
        lambda: run_script("import_pull_sheet.py", status)
    )

    make_button(
        fulfillment,
        "2. Generate Pick Wave",
        lambda: run_script("generate_pick_wave.py", status)
    )

    make_button(
        fulfillment,
        "3. Open Pick Wave Workbook",
        lambda: open_file(PICK_WAVE_XLSX)
    )

    make_button(
        fulfillment,
        "4. Deplete Database",
        lambda: run_script("confirm_depletion.py", status),
    )

    lookup = make_section(root, "LOOKUP TOOLS")

    make_button(
        lookup,
        "Manual Card Lookup",
        lambda: run_script("manual_card_lookup.py", status)
    )

    make_button(
        lookup,
        "Batch Lookup",
        lambda: run_script("batch_lookup.py", status)
    )

    admin = make_section(root, "DATABASE / ADMIN")

    make_button(
        admin,
        "Add / Update Batch",
        lambda: run_script("batch_editor.py", status)
    )

    root.mainloop()

if __name__ == "__main__":
    main()
