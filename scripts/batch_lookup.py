import sys
from pathlib import Path
import sqlite3
import tkinter as tk
from tkinter import ttk

sys.path.append(str(Path(__file__).resolve().parents[1]))

from core.paths import DB_PATH
from core.location import resolve_batch_location


def clean(v):
    return "" if v is None else str(v).strip()


def lookup_batch():
    batch_id = batch_var.get().strip()

    for item in result_tree.get_children():
        result_tree.delete(item)

    if not batch_id:
        status_var.set("Enter a batch ID.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    loc = resolve_batch_location(conn, batch_id)
    conn.close()

    if not loc or not loc.get("found"):
        status_var.set(f"Not found: {batch_id}")
        return

    location = ""
    if loc.get("box_id") or loc.get("segment"):
        location = f"{loc.get('box_id', '')}:{loc.get('segment', '')}"

    values = (
        loc.get("batch_id", ""),
        loc.get("source_system", ""),
        loc.get("source_table", ""),
        loc.get("box_id", ""),
        loc.get("segment", ""),
        location,
        loc.get("physical_location", ""),
        loc.get("shelf_id", ""),
        loc.get("shelf_level", ""),
        loc.get("box_type", ""),
        loc.get("batch_notes", ""),
        loc.get("box_notes", ""),
    )

    result_tree.insert("", "end", values=values)
    status_var.set(f"Found: {batch_id}")

    add_recent(batch_id, location)


def add_recent(batch_id, location):
    recent_tree.insert("", 0, values=(batch_id, location))

    children = recent_tree.get_children()
    if len(children) > 20:
        recent_tree.delete(children[-1])


def use_recent(event):
    selected = recent_tree.selection()
    if not selected:
        return

    values = recent_tree.item(selected[0], "values")
    if not values:
        return

    batch_var.set(values[0])
    lookup_batch()

def get_last_batch_by_code(code):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    row = conn.execute("""
        SELECT batch_id
        FROM batches
        WHERE batch_id GLOB ?
        ORDER BY CAST(substr(batch_id, 1, length(batch_id)-1) AS INTEGER) DESC
        LIMIT 1
        """,
        (f"[0-9]*{code}",)
    ).fetchone()

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

def lookup_last_code(code):
    batch_id = get_last_batch_by_code(code)

    if not batch_id:
        status_var.set(f"No batch found for code {code}.")
        return

    batch_var.set(batch_id)
    lookup_batch()

def lookup_last_tcgp():
    t_batch = get_last_batch_by_code("T")
    si_batch = get_last_si_batch()

    for item in result_tree.get_children():
        result_tree.delete(item)

    shown = []

    for batch_id in (t_batch, si_batch):
        if not batch_id:
            continue

        batch_var.set(batch_id)
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        loc = resolve_batch_location(conn, batch_id)
        conn.close()

        if not loc or not loc.get("found"):
            continue

        location = f"{loc.get('box_id', '')}:{loc.get('segment', '')}" if (loc.get("box_id") or loc.get("segment")) else ""

        values = (
            loc.get("batch_id", ""),
            loc.get("source_system", ""),
            loc.get("source_table", ""),
            loc.get("box_id", ""),
            loc.get("segment", ""),
            location,
            loc.get("physical_location", ""),
            loc.get("shelf_id", ""),
            loc.get("shelf_level", ""),
            loc.get("box_type", ""),
            loc.get("batch_notes", ""),
            loc.get("box_notes", ""),
        )

        result_tree.insert("", "end", values=values)
        add_recent(batch_id, location)
        shown.append(batch_id)

    status_var.set("Last TCGP batches: " + ", ".join(shown) if shown else "No TCGP batches found.")

root = tk.Tk()
root.title("Batch Lookup")
root.geometry("1000x500")

batch_var = tk.StringVar()
status_var = tk.StringVar(value="Ready.")

top = tk.Frame(root)
top.pack(fill="x", padx=10, pady=10)

tk.Label(top, text="Batch:").pack(side="left")

entry = tk.Entry(top, textvariable=batch_var, width=40)
entry.pack(side="left", padx=8)
entry.bind("<Return>", lambda event: lookup_batch())

tk.Button(top, text="Search", command=lookup_batch).pack(side="left")
tk.Button(top, text="Last Ebay", command=lambda: lookup_last_code("E")).pack(side="left", padx=4)
tk.Button(top, text="Last BSC", command=lambda: lookup_last_code("B")).pack(side="left", padx=4)
tk.Button(top, text="Last TCGP", command=lookup_last_tcgp).pack(side="left", padx=4)

tk.Label(root, textvariable=status_var).pack(anchor="w", padx=10)

columns = (
    "batch_id",
    "source_system",
    "source_table",
    "box_id",
    "segment",
    "location",
    "physical_location",
    "shelf_id",
    "shelf_level",
    "box_type",
    "batch_notes",
    "box_notes",
)

tk.Label(root, text="Result").pack(anchor="w", padx=10, pady=(10, 0))

result_tree = ttk.Treeview(root, columns=columns, show="headings", height=3)

for col in columns:
    result_tree.heading(col, text=col)
    result_tree.column(col, width=100)

result_tree.column("physical_location", width=180)
result_tree.column("batch_notes", width=180)
result_tree.column("box_notes", width=180)

result_tree.pack(fill="x", padx=10, pady=5)

tk.Label(root, text="Recent Lookups").pack(anchor="w", padx=10, pady=(10, 0))

recent_tree = ttk.Treeview(root, columns=("batch_id", "location"), show="headings", height=12)
recent_tree.heading("batch_id", text="batch_id")
recent_tree.heading("location", text="location")
recent_tree.column("batch_id", width=150)
recent_tree.column("location", width=150)
recent_tree.pack(fill="both", expand=True, padx=10, pady=5)
recent_tree.bind("<Double-1>", use_recent)

entry.focus()
root.mainloop()
