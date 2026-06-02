import csv
import sqlite3
from pathlib import Path
from tkinter import Tk, messagebox

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from core.paths import (
    DB_PATH,
    OUT_DIR,
    PICK_WAVE_CSV,
    PACK_ORDER_CSV,
    MISSING_ITEMS_CSV,
    PICK_WORKFLOW_CSV,
    PICK_WAVE_XLSX,
    DEFAULT_WORKBOOK,
)


def clean(v):
    return "" if v is None else str(v).strip()


def clean_int(v):
    try:
        return int(float(clean(v)))
    except Exception:
        return 0


def load_pick_rows():
    if not PICK_WAVE_CSV.exists():
        raise FileNotFoundError(f"Missing pick wave file: {PICK_WAVE_CSV}")

    rows = []

    with open(PICK_WAVE_CSV, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        for r in reader:
            status = clean(r.get("status"))

            if status != "OK":
                continue

            row_id = clean(r.get("row_id"))
            qty = clean_int(r.get("qty_to_pick"))

            if row_id == "" or qty <= 0:
                continue

            rows.append({
                "order_id": clean(r.get("order_id")),
                "row_id": row_id,
                "batch_id": clean(r.get("batch_id")),
                "card_name": clean(r.get("inventory_name")) or clean(r.get("card_name")),
                "collector_no": clean(r.get("collector_no")),
                "print": clean(r.get("print")),
                "condition": clean(r.get("condition")),
                "qty_to_pick": qty,
            })

    return rows


def preview_depletion(conn, rows):
    preview = []

    for r in rows:
        current = conn.execute(
            """
            SELECT quantity
            FROM cards_raw
            WHERE row_id = ?
            """,
            (r["row_id"],)
        ).fetchone()

        if current is None:
            preview.append((r, None, "ROW_ID_NOT_FOUND"))
            continue

        current_qty = int(current[0] or 0)
        after_qty = current_qty - r["qty_to_pick"]

        if after_qty < 0:
            preview.append((r, current_qty, "WOULD_GO_NEGATIVE"))
        else:
            preview.append((r, current_qty, "OK"))

    return preview


def apply_depletion(conn, preview):
    depleted_count = 0
    total_cards = 0

    for r, current_qty, status in preview:
        if status != "OK":
            continue

        qty = r["qty_to_pick"]

        conn.execute(
            """
            UPDATE cards_raw
            SET quantity = quantity - ?
            WHERE row_id = ?
            """,
            (qty, r["row_id"])
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
                r["order_id"],
                r["row_id"],
                r["batch_id"],
                r["card_name"],
                r["collector_no"],
                r["print"],
                r["condition"],
                qty,
            )
        )

        depleted_count += 1
        total_cards += qty

    return depleted_count, total_cards


def main():
    root = Tk()
    root.withdraw()

    rows = load_pick_rows()

    if not rows:
        messagebox.showwarning(
            "Nothing to deplete",
            "No OK pick rows found in pick_wave.csv."
        )
        return

    conn = sqlite3.connect(DB_PATH)

    try:
        preview = preview_depletion(conn, rows)

        errors = [x for x in preview if x[2] != "OK"]
        ok_rows = [x for x in preview if x[2] == "OK"]

        msg = (
            f"Ready to deplete SQLite inventory only.\n\n"
            f"OK rows: {len(ok_rows)}\n"
            f"Problem rows: {len(errors)}\n"
            f"Total cards to deplete: {sum(x[0]['qty_to_pick'] for x in ok_rows)}\n\n"
            f"Proceed?"
        )

        if not messagebox.askyesno("Confirm depletion", msg):
            return

        if errors:
            err_text = "\n".join(
                f"{x[0]['row_id']} | {x[0]['card_name']} | {x[2]}"
                for x in errors[:20]
            )

            proceed = messagebox.askyesno(
                "Problem rows detected",
                f"Some rows cannot be depleted and will be skipped:\n\n"
                f"{err_text}\n\n"
                f"Proceed with OK rows only?"
            )

            if not proceed:
                return

        depleted_count, total_cards = apply_depletion(conn, preview)

        conn.commit()

        messagebox.showinfo(
            "Depletion complete",
            f"SQLite depletion complete.\n\n"
            f"Rows depleted: {depleted_count}\n"
            f"Cards depleted: {total_cards}"
        )

        print(f"Rows depleted: {depleted_count}")
        print(f"Cards depleted: {total_cards}")

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    main()
