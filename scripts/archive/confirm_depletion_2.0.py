import csv
import shutil
import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from tkinter import Tk, messagebox

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from core.paths import (
    DB_PATH,
    PICK_WAVE_CSV,
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
                "pull_id": clean_int(r.get("pull_id")),
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


def get_loaded_pull_sheet(conn):
    row = conn.execute(
        """
        SELECT source_file_path, fieldnames
        FROM loaded_pull_sheet
        WHERE id = 1
        """
    ).fetchone()

    if row is None:
        return None, []

    source_file_path = clean(row[0])
    fieldnames = clean(row[1]).split("|") if clean(row[1]) else []

    return source_file_path, fieldnames


def calculate_picked_by_pull_id(preview):
    picked = defaultdict(int)

    for r, current_qty, status in preview:
        if status != "OK":
            continue

        pull_id = clean_int(r.get("pull_id"))
        qty = clean_int(r.get("qty_to_pick"))

        if pull_id > 0 and qty > 0:
            picked[pull_id] += qty

    return picked


def backup_pull_sheet(source_path):
    source_path = Path(source_path)

    if not source_path.exists():
        raise FileNotFoundError(f"Loaded pull sheet not found: {source_path}")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = source_path.with_name(f"{source_path.stem}.before_db_pull_{stamp}{source_path.suffix}")

    shutil.copy2(source_path, backup_path)
    return backup_path


def rewrite_loaded_pull_sheet(conn, preview):
    source_file_path, fieldnames = get_loaded_pull_sheet(conn)

    if not source_file_path:
        return None, 0, 0

    source_path = Path(source_file_path)

    if not fieldnames:
        fieldnames = [
            "Product Line",
            "Product Name",
            "Condition",
            "Number",
            "Set",
            "Rarity",
            "Quantity",
        ]

    picked_by_pull_id = calculate_picked_by_pull_id(preview)

    pull_rows = conn.execute(
        """
        SELECT
            id,
            original_product_line,
            original_product_name,
            original_condition,
            original_number,
            original_set,
            original_rarity,
            original_quantity
        FROM pull_items
        ORDER BY id
        """
    ).fetchall()

    output_rows = []
    omitted_rows = 0

    for row in pull_rows:
        pull_id = int(row[0])
        original_qty = int(row[7] or 0)
        picked_qty = int(picked_by_pull_id.get(pull_id, 0))
        remaining_qty = original_qty - picked_qty

        if remaining_qty <= 0:
            omitted_rows += 1
            continue

        out = {h: "" for h in fieldnames}

        if "Product Line" in out:
            out["Product Line"] = clean(row[1])
        if "Product Name" in out:
            out["Product Name"] = clean(row[2])
        if "Condition" in out:
            out["Condition"] = clean(row[3])
        if "Number" in out:
            out["Number"] = clean(row[4])
        if "Set" in out:
            out["Set"] = clean(row[5])
        if "Rarity" in out:
            out["Rarity"] = clean(row[6])
        if "Quantity" in out:
            out["Quantity"] = remaining_qty

        output_rows.append(out)

    backup_path = backup_pull_sheet(source_path)

    with open(source_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(output_rows)

    return backup_path, len(output_rows), omitted_rows


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
            f"Ready to deplete SQLite inventory.\n\n"
            f"OK rows: {len(ok_rows)}\n"
            f"Problem rows: {len(errors)}\n"
            f"Total cards to deplete: {sum(x[0]['qty_to_pick'] for x in ok_rows)}\n\n"
            f"After depletion, the loaded pull sheet will be rewritten in-place with DB-picked quantities removed.\n"
            f"A timestamped backup will be created first.\n\n"
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

        backup_path, remaining_rows, omitted_rows = rewrite_loaded_pull_sheet(conn, preview)

        conn.commit()

        if backup_path:
            sheet_msg = (
                f"\n\nLoaded pull sheet updated.\n"
                f"Remaining rows: {remaining_rows}\n"
                f"Rows removed: {omitted_rows}\n"
                f"Backup:\n{backup_path}"
            )
        else:
            sheet_msg = "\n\nNo loaded pull sheet metadata found, so no pull sheet was rewritten."

        messagebox.showinfo(
            "Depletion complete",
            f"SQLite depletion complete.\n\n"
            f"Rows depleted: {depleted_count}\n"
            f"Cards depleted: {total_cards}"
            f"{sheet_msg}"
        )

        print(f"Rows depleted: {depleted_count}")
        print(f"Cards depleted: {total_cards}")
        if backup_path:
            print(f"Pull sheet backup: {backup_path}")

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    main()
