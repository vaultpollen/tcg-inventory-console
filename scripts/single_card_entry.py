import sys
from pathlib import Path
import sqlite3
import tkinter as tk
from tkinter import messagebox, simpledialog
import uuid

sys.path.append(str(Path(__file__).resolve().parents[1]))

from core.paths import DB_PATH


COND_MAP = {
    "near mint": "near_mint",
    "lightly played": "light_played",
    "moderately played": "moderately_played",
    "heavily played": "heavily_played",
    "damaged": "damaged",
}


def clean(v):
    return "" if v is None else str(v).strip()


def norm_condition(v):
    s = clean(v).lower()
    return COND_MAP.get(s, s.replace(" ", "_"))


def get_last_batch_by_code(code):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    row = conn.execute("""
        SELECT batch_id
        FROM batches
        WHERE batch_id GLOB ?
        ORDER BY CAST(substr(batch_id, 1, length(batch_id)-1) AS INTEGER) DESC
        LIMIT 1
    """, (f"[0-9]*{code}",)).fetchone()

    conn.close()
    return row["batch_id"] if row else ""


def get_last_si_batch():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    row = conn.execute("""
        SELECT batch_id
        FROM batches
        WHERE batch_id GLOB 'SI[0-9]*'
        ORDER BY CAST(substr(batch_id, 3) AS INTEGER) DESC
        LIMIT 1
    """).fetchone()

    conn.close()
    return row["batch_id"] if row else ""


def refresh_last_batches():
    last_t_var.set(get_last_batch_by_code("T") or "None")
    last_si_var.set(get_last_si_batch() or "None")


def batch_exists(conn, batch_id):
    row = conn.execute(
        """
        SELECT batch_id
        FROM batches
        WHERE TRIM(batch_id) = TRIM(?)
        """,
        (batch_id,)
    ).fetchone()

    return row is not None


def create_batch_prompt(conn, batch_id):
    create = messagebox.askyesno(
        "Batch not found",
        f"Batch '{batch_id}' does not exist.\n\nCreate it now?"
    )

    if not create:
        return False

    source = simpledialog.askstring(
        "Source System",
        "Source system?",
        initialvalue="MANUAL"
    )

    if source is None:
        return False

    box_id = simpledialog.askstring(
        "Box ID",
        f"Box ID for batch {batch_id}:"
    )

    if not box_id:
        return False

    segment = simpledialog.askstring(
        "Segment",
        f"Segment for batch {batch_id}:"
    )

    if segment is None:
        segment = ""

    tcg = clean(tcg_var.get()).lower()

    conn.execute(
        """
        INSERT INTO batches (
            batch_id,
            source_system,
            box_id,
            segment,
            tcg,
            active,
            notes
        )
        VALUES (?, ?, ?, ?, ?, 1, ?)
        ON CONFLICT(batch_id) DO UPDATE SET
            source_system = excluded.source_system,
            box_id = excluded.box_id,
            segment = excluded.segment,
            tcg = excluded.tcg,
            active = 1,
            notes = excluded.notes
        """,
        (
            batch_id,
            clean(source).upper() or "MANUAL",
            clean(box_id),
            clean(segment),
            tcg,
            "Created from Single Card Entry.",
        )
    )

    return True


def save_card():
    data = {
        "row_id": str(uuid.uuid4()),
        "name": clean(name_var.get()),
        "set_code": clean(set_code_var.get()),
        "set_name": clean(set_name_var.get()),
        "collector_no": clean(collector_var.get()),
        "print": clean(print_var.get()).lower(),
        "rarity": clean(rarity_var.get()).lower(),
        "quantity": clean(qty_var.get()),
        "condition": norm_condition(condition_var.get()),
        "language": clean(language_var.get()).lower() or "en",
        "batch_id": clean(batch_var.get()),
        "tcg": clean(tcg_var.get()).lower(),
    }

    if not data["name"]:
        messagebox.showerror("Missing field", "Card name is required.")
        return

    if not data["collector_no"]:
        messagebox.showerror("Missing field", "Collector number is required.")
        return

    if not data["batch_id"]:
        messagebox.showerror("Missing field", "Batch ID is required.")
        return

    if not data["tcg"]:
        messagebox.showerror("Missing field", "TCG is required.")
        return

    try:
        data["quantity"] = int(float(data["quantity"] or 1))
    except Exception:
        messagebox.showerror("Invalid quantity", "Quantity must be a number.")
        return

    if data["quantity"] <= 0:
        messagebox.showerror("Invalid quantity", "Quantity must be greater than zero.")
        return

    conn = sqlite3.connect(DB_PATH)

    try:
        if not batch_exists(conn, data["batch_id"]):
            made_batch = create_batch_prompt(conn, data["batch_id"])
            if not made_batch:
                conn.rollback()
                return

        conn.execute(
            """
            INSERT INTO cards_raw (
                row_id,
                name,
                set_code,
                set_name,
                collector_no,
                print,
                rarity,
                quantity,
                condition,
                language,
                batch_id,
                tcg
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["row_id"],
                data["name"],
                data["set_code"],
                data["set_name"],
                data["collector_no"],
                data["print"],
                data["rarity"],
                data["quantity"],
                data["condition"],
                data["language"],
                data["batch_id"],
                data["tcg"],
            )
        )

        conn.commit()

    except Exception as e:
        conn.rollback()
        messagebox.showerror("Save failed", str(e))
        raise

    finally:
        conn.close()

    messagebox.showinfo(
        "Card added",
        f"Added {data['quantity']}x {data['name']} to batch {data['batch_id']}."
    )

    clear_card_fields()
    refresh_last_batches()


def clear_card_fields():
    name_var.set("")
    collector_var.set("")
    qty_var.set("1")

    if not keep_context_var.get():
        set_code_var.set("")
        set_name_var.set("")
        condition_var.set("near_mint")
        print_var.set("normal")
        rarity_var.set("")
        language_var.set("en")
        tcg_var.set("mtg")
        batch_var.set("")


root = tk.Tk()
root.title("Single Card Entry")
root.geometry("620x560")

last_t_var = tk.StringVar()
last_si_var = tk.StringVar()
keep_context_var = tk.IntVar(value=1)

name_var = tk.StringVar()
set_code_var = tk.StringVar()
set_name_var = tk.StringVar()
collector_var = tk.StringVar()
condition_var = tk.StringVar(value="near_mint")
print_var = tk.StringVar(value="normal")
rarity_var = tk.StringVar()
qty_var = tk.StringVar(value="1")
language_var = tk.StringVar(value="en")
tcg_var = tk.StringVar()
batch_var = tk.StringVar()

frame = tk.Frame(root)
frame.pack(fill="both", expand=True, padx=18, pady=18)

tk.Label(frame, text="Last TCGP Batches", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")

tk.Label(frame, text="Last T code:").grid(row=1, column=0, sticky="w")
tk.Label(frame, textvariable=last_t_var).grid(row=1, column=1, sticky="w")

tk.Label(frame, text="Last SI code:").grid(row=2, column=0, sticky="w")
tk.Label(frame, textvariable=last_si_var).grid(row=2, column=1, sticky="w")

tk.Button(frame, text="Refresh Last Batches", command=refresh_last_batches).grid(row=3, column=1, sticky="w", pady=(4, 14))

required_bg = "#fff2a8"
optional_fg = "#888888"

fields = [
    ("Card Name", name_var, True),
    ("Set Code", set_code_var, False),
    ("Set Name", set_name_var, False),
    ("Collector #", collector_var, True),
    ("Condition", condition_var, True),
    ("Print", print_var, True),
    ("Rarity", rarity_var, False),
    ("Quantity", qty_var, True),
    ("Language", language_var, True),
    ("TCG", tcg_var, True),
    ("Batch ID", batch_var, True),
]

start_row = 4

for idx, (label, var, required) in enumerate(fields):
    r = start_row + idx

    display_label = f"{label} *" if required else f"{label} (optional)"

    tk.Label(
        frame,
        text=display_label,
        fg="black" if required else optional_fg
    ).grid(row=r, column=0, sticky="w", pady=4)

    tk.Entry(
        frame,
        textvariable=var,
        width=45,
        bg=required_bg if required else "white",
        fg="black" if required else optional_fg
    ).grid(row=r, column=1, sticky="w", pady=4)

button_frame = tk.Frame(frame)
button_frame.grid(row=start_row + len(fields), column=1, sticky="w", pady=16)

tk.Button(button_frame, text="Add Card", command=save_card, width=18).pack(side="left", padx=4)
tk.Button(button_frame, text="Clear", command=clear_card_fields, width=10).pack(side="left", padx=4)

tk.Checkbutton(
    frame,
    text="Keep set/batch fields after adding",
    variable=keep_context_var
).grid(row=start_row + len(fields) + 1, column=1, sticky="w", pady=(0, 8))

refresh_last_batches()
root.mainloop()
