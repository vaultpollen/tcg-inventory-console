import sys
from pathlib import Path
import sqlite3
import tkinter as tk
from tkinter import messagebox, simpledialog

sys.path.append(str(Path(__file__).resolve().parents[1]))

from core.paths import DB_PATH


STAGE_BATCH_ID = "STAGE"


def clean(v):
    return "" if v is None else str(v).strip()


def stage_summary(conn):
    row = conn.execute(
        """
        SELECT
            COUNT(*) AS row_count,
            COALESCE(SUM(quantity), 0) AS total_qty
        FROM cards_raw
        WHERE UPPER(TRIM(batch_id)) = ?
        """,
        (STAGE_BATCH_ID,)
    ).fetchone()

    return int(row[0] or 0), int(row[1] or 0)


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
        initialvalue="NEW_MAP"
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

    tcg = simpledialog.askstring(
        "TCG",
        f"TCG for batch {batch_id}?",
        initialvalue=""
    )

    if tcg is None:
        tcg = ""

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
            clean(batch_id),
            clean(source).upper() or "NEW_MAP",
            clean(box_id),
            clean(segment),
            clean(tcg).lower(),
            "Created from Push STAGE to Batch.",
        )
    )

    return True


def ensure_stage_batch(conn):
    if batch_exists(conn, STAGE_BATCH_ID):
        return

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
        VALUES ('STAGE', 'STAGE', 'STAGE', 'STAGE', '', 1, ?)
        """,
        ("Temporary holding batch for mobile/on-the-go listing.",)
    )


def push_stage():
    target = clean(target_var.get())

    if not target:
        messagebox.showerror("Missing target", "Enter a target batch ID.")
        return

    if target.upper() == STAGE_BATCH_ID:
        messagebox.showerror("Invalid target", "Target batch cannot be STAGE.")
        return

    conn = sqlite3.connect(DB_PATH)

    try:
        ensure_stage_batch(conn)

        row_count, total_qty = stage_summary(conn)

        if row_count <= 0:
            messagebox.showwarning("Nothing staged", "No cards are currently in STAGE.")
            conn.rollback()
            return

        if not batch_exists(conn, target):
            made = create_batch_prompt(conn, target)
            if not made:
                conn.rollback()
                return

        confirm = messagebox.askyesno(
            "Confirm STAGE move",
            f"Move all STAGE inventory to batch '{target}'?\n\n"
            f"Rows: {row_count}\n"
            f"Total quantity: {total_qty}\n\n"
            f"This updates cards_raw.batch_id from STAGE to {target}."
        )

        if not confirm:
            conn.rollback()
            return

        conn.execute(
            """
            UPDATE cards_raw
            SET batch_id = ?
            WHERE UPPER(TRIM(batch_id)) = ?
            """,
            (
                target,
                STAGE_BATCH_ID,
            )
        )

        conn.commit()

        messagebox.showinfo(
            "STAGE moved",
            f"Moved STAGE to batch {target}.\n\n"
            f"Rows moved: {row_count}\n"
            f"Total quantity moved: {total_qty}"
        )

        target_var.set("")
        refresh_summary()

    except Exception as e:
        conn.rollback()
        messagebox.showerror("Move failed", str(e))
        raise

    finally:
        conn.close()


def refresh_summary():
    conn = sqlite3.connect(DB_PATH)

    try:
        ensure_stage_batch(conn)
        row_count, total_qty = stage_summary(conn)
        conn.commit()
        summary_var.set(f"STAGE rows: {row_count} | STAGE total qty: {total_qty}")

    except Exception as e:
        conn.rollback()
        summary_var.set(f"Error reading STAGE: {e}")

    finally:
        conn.close()


root = tk.Tk()
root.title("Push STAGE to Batch")
root.geometry("460x230")
root.resizable(False, False)

target_var = tk.StringVar()
summary_var = tk.StringVar(value="Ready.")

frame = tk.Frame(root)
frame.pack(fill="both", expand=True, padx=18, pady=18)

tk.Label(frame, text="Push STAGE to Batch", font=("Segoe UI", 13, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))

tk.Label(frame, textvariable=summary_var).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 12))

tk.Label(frame, text="Target Batch ID").grid(row=2, column=0, sticky="w")
tk.Entry(frame, textvariable=target_var, width=32).grid(row=2, column=1, sticky="w")

button_frame = tk.Frame(frame)
button_frame.grid(row=3, column=1, sticky="w", pady=18)

tk.Button(button_frame, text="Push STAGE", command=push_stage, width=14).pack(side="left", padx=4)
tk.Button(button_frame, text="Refresh", command=refresh_summary, width=10).pack(side="left", padx=4)

refresh_summary()
root.mainloop()
