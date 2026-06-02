import sys
from pathlib import Path
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

sys.path.append(str(Path(__file__).resolve().parents[1]))

from core.paths import DB_PATH
from core.location import resolve_batch_location


def clean(v):
    return "" if v is None else str(v).strip()


def search_inventory(query):
    q = f"%{query.strip()}%"

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
        SELECT
            row_id,
            name,
            set_name,
            collector_no,
            condition,
            print,
            quantity,
            batch_id,
            tcg
        FROM cards_raw
        WHERE quantity > 0
          AND (
              name LIKE ?
              OR collector_no LIKE ?
              OR set_name LIKE ?
              OR batch_id LIKE ?
          )
        ORDER BY name, set_name, collector_no
        LIMIT 100
    """, (q, q, q, q)).fetchall()

    results = []

    for r in rows:
        loc = resolve_batch_location(conn, r["batch_id"])

        location = ""
        if loc and loc.get("box_id"):
            location = f"{loc.get('box_id', '')}:{loc.get('segment', '')}"

        results.append({
            "row_id": clean(r["row_id"]),
            "name": clean(r["name"]),
            "set_name": clean(r["set_name"]),
            "collector_no": clean(r["collector_no"]),
            "condition": clean(r["condition"]),
            "print": clean(r["print"]),
            "quantity": clean(r["quantity"]),
            "batch_id": clean(r["batch_id"]),
            "location": location,
            "tcg": clean(r["tcg"]),
        })

    conn.close()
    return results


def search_legacy(query):
    q = f"%{query.strip()}%"

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
        SELECT
            box_id,
            segment,
            tcg,
            name,
            condition,
            print,
            state
        FROM legacy_locations
        WHERE name LIKE ?
        ORDER BY tcg, name, box_id, segment
        LIMIT 100
    """, (q,)).fetchall()

    conn.close()

    return [{
        "box_id": clean(r["box_id"]),
        "segment": clean(r["segment"]),
        "tcg": clean(r["tcg"]),
        "name": clean(r["name"]),
        "condition": clean(r["condition"]),
        "print": clean(r["print"]),
        "state": clean(r["state"]),
    } for r in rows]


def run_search():
    query = search_var.get().strip()

    for item in inv_tree.get_children():
        inv_tree.delete(item)

    for item in legacy_tree.get_children():
        legacy_tree.delete(item)

    if not query:
        status_var.set("Enter a search term.")
        return

    inv_results = search_inventory(query)

    for r in inv_results:
        inv_tree.insert("", "end", values=(
            r["quantity"],
            r["name"],
            r["set_name"],
            r["collector_no"],
            r["condition"],
            r["print"],
            r["batch_id"],
            r["location"],
            r["row_id"],
        ))

    legacy_results = search_legacy(query)

    for r in legacy_results:
        legacy_tree.insert("", "end", values=(
            r["tcg"],
            r["name"],
            r["condition"],
            r["print"],
            r["box_id"],
            r["segment"],
            r["state"],
        ))

    status_var.set(
        f"DB results: {len(inv_results)} | Legacy hints: {len(legacy_results)}"
    )


def get_selected_inventory_row():
    selected = inv_tree.selection()

    if not selected:
        messagebox.showwarning("No selection", "Select a database inventory row first.")
        return None

    values = inv_tree.item(selected[0], "values")

    if not values:
        return None

    return {
        "quantity": clean(values[0]),
        "name": clean(values[1]),
        "set_name": clean(values[2]),
        "collector_no": clean(values[3]),
        "condition": clean(values[4]),
        "print": clean(values[5]),
        "batch_id": clean(values[6]),
        "location": clean(values[7]),
        "row_id": clean(values[8]),
    }


def deplete_selected(qty):
    row = get_selected_inventory_row()
    if row is None:
        return

    try:
        qty = int(qty)
    except Exception:
        messagebox.showerror("Invalid quantity", "Quantity must be a whole number.")
        return

    if qty <= 0:
        messagebox.showerror("Invalid quantity", "Quantity must be greater than zero.")
        return

    current_qty = int(float(row["quantity"] or 0))

    if qty > current_qty:
        messagebox.showerror(
            "Too many",
            f"Cannot deplete {qty}. Current quantity is only {current_qty}."
        )
        return

    confirm = messagebox.askyesno(
        "Confirm depletion",
        f"Deplete {qty} from this row?\n\n"
        f"{row['name']}\n"
        f"{row['set_name']}\n"
        f"#{row['collector_no']} | {row['condition']} | {row['print']}\n"
        f"Batch: {row['batch_id']} | Location: {row['location']}\n"
        f"Row ID: {row['row_id']}"
    )

    if not confirm:
        return

    conn = sqlite3.connect(DB_PATH)

    try:
        db_row = conn.execute(
            """
            SELECT quantity
            FROM cards_raw
            WHERE row_id = ?
            """,
            (row["row_id"],)
        ).fetchone()

        if db_row is None:
            raise ValueError(f"row_id not found: {row['row_id']}")

        db_qty = int(db_row[0] or 0)

        if qty > db_qty:
            raise ValueError(f"Database quantity is now only {db_qty}. Refresh and try again.")

        conn.execute(
            """
            UPDATE cards_raw
            SET quantity = quantity - ?
            WHERE row_id = ?
            """,
            (qty, row["row_id"])
        )

        conn.execute(
            """
            INSERT INTO depletion_log (
                order_id,
                row_id,
                batch_id,
                card_name,
                collector_no,
                print,
                condition,
                qty_depleted
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "MANUAL_LOOKUP",
                row["row_id"],
                row["batch_id"],
                row["name"],
                row["collector_no"],
                row["print"],
                row["condition"],
                qty,
            )
        )

        conn.commit()

    except Exception as e:
        conn.rollback()
        messagebox.showerror("Depletion failed", str(e))
        raise

    finally:
        conn.close()

    messagebox.showinfo("Depleted", f"Depleted {qty} from:\n{row['name']}")
    run_search()


def deplete_one():
    deplete_selected(1)


def deplete_custom():
    qty = simpledialog.askinteger("Custom depletion", "Quantity to deplete:", minvalue=1)
    if qty is None:
        return
    deplete_selected(qty)


root = tk.Tk()
root.title("Manual Lookup")
root.geometry("1250x760")

search_var = tk.StringVar()
status_var = tk.StringVar(value="Ready.")

top = tk.Frame(root)
top.pack(fill="x", padx=10, pady=10)

tk.Label(top, text="Search:").pack(side="left")

entry = tk.Entry(top, textvariable=search_var, width=50)
entry.pack(side="left", padx=8)
entry.bind("<Return>", lambda event: run_search())

tk.Button(top, text="Search", command=run_search).pack(side="left", padx=4)

tk.Button(top, text="Deplete 1", command=deplete_one).pack(side="left", padx=12)
tk.Button(top, text="Deplete Custom", command=deplete_custom).pack(side="left", padx=4)

tk.Label(root, textvariable=status_var).pack(anchor="w", padx=10)

tk.Label(root, text="Database Inventory").pack(anchor="w", padx=10, pady=(10, 0))

inv_columns = (
    "qty",
    "name",
    "set_name",
    "collector_no",
    "condition",
    "print",
    "batch_id",
    "location",
    "row_id",
)

inv_tree = ttk.Treeview(root, columns=inv_columns, show="headings", height=14)

for col in inv_columns:
    inv_tree.heading(col, text=col)
    inv_tree.column(col, width=120)

inv_tree.column("name", width=220)
inv_tree.column("set_name", width=180)
inv_tree.column("row_id", width=180)

inv_tree.pack(fill="both", expand=True, padx=10, pady=5)

tk.Label(root, text="Legacy Hints - read only").pack(anchor="w", padx=10, pady=(10, 0))

legacy_columns = (
    "tcg",
    "name",
    "condition",
    "print",
    "box_id",
    "segment",
    "state",
)

legacy_tree = ttk.Treeview(root, columns=legacy_columns, show="headings", height=8)

for col in legacy_columns:
    legacy_tree.heading(col, text=col)
    legacy_tree.column(col, width=130)

legacy_tree.column("name", width=250)

legacy_tree.pack(fill="both", expand=True, padx=10, pady=5)

entry.focus()
root.mainloop()
