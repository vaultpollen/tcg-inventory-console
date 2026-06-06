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

from core.paths import DB_PATH, PICK_WAVE_CSV


def clean(v):
    return "" if v is None else str(v).strip()


def clean_int(v):
    try:
        return int(float(clean(v)))
    except Exception:
        return 0


def norm_key(v):
    return clean(v).lower()


def load_ok_pick_rows():
    rows = []

    with open(PICK_WAVE_CSV, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        for r in reader:
            if clean(r.get("status")) != "OK":
                continue

            qty = clean_int(r.get("qty_to_pick"))
            if qty <= 0:
                continue

            rows.append({
                "pull_id": clean_int(r.get("pull_id")),
                "order_id": clean(r.get("order_id")),
                "card_name": clean(r.get("card_name")),
                "inventory_name": clean(r.get("inventory_name")),
                "collector_no": clean(r.get("collector_no")),
                "condition": clean(r.get("condition")),
                "print": clean(r.get("print")),
                "qty_to_pick": qty,
            })

    return rows


def get_loaded_pull_sheet(conn):
    row = conn.execute("""
        SELECT source_file_path, fieldnames
        FROM loaded_pull_sheet
        WHERE id = 1
    """).fetchone()

    if row is None:
        raise ValueError("No loaded_pull_sheet record found.")

    source_file_path = clean(row[0])
    fieldnames = clean(row[1]).split("|") if clean(row[1]) else []

    if not source_file_path:
        raise ValueError("Loaded pull sheet path is blank.")

    return Path(source_file_path), fieldnames


def build_pick_maps(pick_rows):
    by_pull_id = defaultdict(int)
    by_match_key = defaultdict(int)

    for r in pick_rows:
        qty = clean_int(r["qty_to_pick"])

        if r["pull_id"] > 0:
            by_pull_id[r["pull_id"]] += qty

        # fallback when pull_id was missing from older pick_wave.csv
        name = r["card_name"] or r["inventory_name"]

        key = (
            norm_key(r["order_id"]),
            norm_key(name),
            norm_key(r["collector_no"]),
            norm_key(r["condition"]),
            norm_key(r["print"]),
        )

        by_match_key[key] += qty

    return by_pull_id, by_match_key


def backup_file(path):
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = path.with_name(f"{path.stem}.before_rewrite_{stamp}{path.suffix}")
    shutil.copy2(path, backup_path)
    return backup_path


def rewrite_pull_sheet():
    pick_rows = load_ok_pick_rows()

    if not pick_rows:
        raise ValueError("No OK rows found in pick_wave.csv.")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        source_path, fieldnames = get_loaded_pull_sheet(conn)

        if not source_path.exists():
            raise FileNotFoundError(f"Loaded pull sheet not found:\n{source_path}")

        by_pull_id, by_match_key = build_pick_maps(pick_rows)

        pull_rows = conn.execute("""
            SELECT
                id,
                order_id,
                original_product_line,
                original_product_name,
                original_condition,
                original_number,
                original_set,
                original_rarity,
                original_quantity,
                condition,
                print
            FROM pull_items
            ORDER BY id
        """).fetchall()

    finally:
        conn.close()

    output_rows = []
    removed = 0
    reduced = 0
    unchanged = 0

    for r in pull_rows:
        pull_id = int(r["id"])
        original_qty = int(r["original_quantity"] or 0)

        picked_qty = by_pull_id.get(pull_id, 0)

        if picked_qty <= 0:
            key = (
                norm_key(r["order_id"]),
                norm_key(r["original_product_name"]),
                norm_key(r["original_number"]),
                norm_key(r["condition"]),
                norm_key(r["print"]),
            )
            picked_qty = by_match_key.get(key, 0)

        remaining_qty = original_qty - picked_qty

        if remaining_qty <= 0:
            removed += 1
            continue

        if picked_qty > 0:
            reduced += 1
        else:
            unchanged += 1

        out = {h: "" for h in fieldnames}

        if "Product Line" in out:
            out["Product Line"] = clean(r["original_product_line"])
        if "Product Name" in out:
            out["Product Name"] = clean(r["original_product_name"])
        if "Condition" in out:
            out["Condition"] = clean(r["original_condition"])
        if "Number" in out:
            out["Number"] = clean(r["original_number"])
        if "Set" in out:
            out["Set"] = clean(r["original_set"])
        if "Rarity" in out:
            out["Rarity"] = clean(r["original_rarity"])
        if "Quantity" in out:
            out["Quantity"] = remaining_qty

        output_rows.append(out)

    backup_path = backup_file(source_path)

    with open(source_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(output_rows)

    return source_path, backup_path, len(output_rows), removed, reduced, unchanged


def main():
    root = Tk()
    root.withdraw()

    try:
        source_path, backup_path, remaining, removed, reduced, unchanged = rewrite_pull_sheet()

        messagebox.showinfo(
            "Pull sheet rewritten",
            f"Updated original pull sheet:\n{source_path}\n\n"
            f"Remaining rows: {remaining}\n"
            f"Rows removed: {removed}\n"
            f"Rows reduced: {reduced}\n"
            f"Rows unchanged: {unchanged}\n\n"
            f"Backup created:\n{backup_path}"
        )

    except Exception as e:
        messagebox.showerror("Rewrite failed", str(e))
        raise


if __name__ == "__main__":
    main()
