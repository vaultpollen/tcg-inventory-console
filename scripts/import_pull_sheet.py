import csv
import sqlite3
from pathlib import Path
from tkinter import Tk, filedialog, messagebox

import sys
from pathlib import Path
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


def clean_int(v):
    try:
        return int(float(clean(v)))
    except Exception:
        return 0


def norm_tcg(v):
    s = clean(v).lower()
    if s in ("magic", "magic the gathering", "mtg"):
        return "mtg"
    if s in ("pokemon", "pokémon"):
        return "pokemon"
    if s in ("yugioh", "yu-gi-oh!", "yu-gi-oh", "ygo"):
        return "yugioh"
    return s


def parse_condition_print(v):
    """
    Pull sheet examples:
      Near Mint
      Near Mint Holofoil
      Lightly Played Reverse Holofoil

    Returns:
      condition, print
    """
    s = clean(v).lower()

    print_type = "normal"

    if "reverse holo" in s or "reverse holofoil" in s:
        print_type = "reverse holofoil"
        s = s.replace("reverse holofoil", "").replace("reverse holo", "")
    elif "holofoil" in s:
        print_type = "holofoil"
        s = s.replace("holofoil", "")
    elif "foil" in s:
        print_type = "foil"
        s = s.replace("foil", "")

    condition_text = clean(s)
    condition = COND_MAP.get(condition_text, condition_text.replace(" ", "_"))

    return condition, print_type


def init_pull_table(conn):
    conn.executescript("""
    DROP TABLE IF EXISTS pull_items;

    CREATE TABLE pull_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id TEXT,
        quantity INTEGER,
        card_name TEXT,
        collector_no TEXT,
        print TEXT,
        condition TEXT,
        tcg TEXT,
        set_name TEXT,
        rarity TEXT
    );

    CREATE INDEX idx_pull_lookup
    ON pull_items (collector_no, print, condition, tcg);
    """)


def import_pull_csv(csv_path):
    conn = sqlite3.connect(DB_PATH)

    try:
        init_pull_table(conn)

        with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            count = 0

            for row in reader:
                tcg = norm_tcg(row.get("Product Line"))
                card_name = clean(row.get("Product Name"))
                condition, print_type = parse_condition_print(row.get("Condition"))
                collector_no = clean(row.get("Number"))
                set_name = clean(row.get("Set"))
                rarity = clean(row.get("Rarity")).lower()
                qty = clean_int(row.get("Quantity"))

                # If pull sheet has no order_id, use source filename as order bucket for now.
                order_id = clean(row.get("order_id")) or Path(csv_path).stem

                if qty <= 0:
                    continue
                if card_name == "" and collector_no == "":
                    continue

                conn.execute(
                    """
                    INSERT INTO pull_items (
                        order_id,
                        quantity,
                        card_name,
                        collector_no,
                        print,
                        condition,
                        tcg,
                        set_name,
                        rarity
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        order_id,
                        qty,
                        card_name,
                        collector_no,
                        print_type,
                        condition,
                        tcg,
                        set_name,
                        rarity,
                    )
                )

                count += 1

        conn.commit()
        return count

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def main():
    root = Tk()
    root.withdraw()

    csv_path = filedialog.askopenfilename(
        title="Select pull sheet CSV",
        filetypes=[("CSV files", "*.csv")]
    )

    if not csv_path:
        return

    try:
        count = import_pull_csv(csv_path)
        messagebox.showinfo("Pull sheet imported", f"Imported pull rows: {count}")
        print(f"Imported pull rows: {count}")

    except Exception as e:
        messagebox.showerror("Import failed", str(e))
        raise


if __name__ == "__main__":
    main()
