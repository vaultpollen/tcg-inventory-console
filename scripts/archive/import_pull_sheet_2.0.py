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
    if s in ("digimon", "digimon card game"):
        return "digimon"
    return s


def parse_condition_print(v):
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
    DROP TABLE IF EXISTS loaded_pull_sheet;

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
        rarity TEXT,

        source_file_path TEXT,
        original_row_number INTEGER,
        original_product_line TEXT,
        original_product_name TEXT,
        original_condition TEXT,
        original_number TEXT,
        original_set TEXT,
        original_rarity TEXT,
        original_quantity INTEGER
    );

    CREATE INDEX idx_pull_lookup
    ON pull_items (collector_no, print, condition, tcg);

    CREATE TABLE loaded_pull_sheet (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        source_file_path TEXT,
        fieldnames TEXT
    );
    """)


def import_pull_csv(csv_path):
    csv_path = Path(csv_path)
    conn = sqlite3.connect(DB_PATH)

    try:
        init_pull_table(conn)

        with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []

            conn.execute(
                """
                INSERT INTO loaded_pull_sheet (
                    id,
                    source_file_path,
                    fieldnames
                )
                VALUES (1, ?, ?)
                """,
                (
                    str(csv_path),
                    "|".join(fieldnames),
                )
            )

            count = 0

            for row_number, row in enumerate(reader, start=2):
                original_product_line = clean(row.get("Product Line"))
                original_product_name = clean(row.get("Product Name"))
                original_condition = clean(row.get("Condition"))
                original_number = clean(row.get("Number"))
                original_set = clean(row.get("Set"))
                original_rarity = clean(row.get("Rarity"))
                original_quantity = clean_int(row.get("Quantity"))

                tcg = norm_tcg(original_product_line)
                card_name = original_product_name
                condition, print_type = parse_condition_print(original_condition)
                collector_no = original_number
                set_name = original_set
                rarity = original_rarity.lower()
                qty = original_quantity

                order_id = clean(row.get("order_id")) or csv_path.stem

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
                        rarity,

                        source_file_path,
                        original_row_number,
                        original_product_line,
                        original_product_name,
                        original_condition,
                        original_number,
                        original_set,
                        original_rarity,
                        original_quantity
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

                        str(csv_path),
                        row_number,
                        original_product_line,
                        original_product_name,
                        original_condition,
                        original_number,
                        original_set,
                        original_rarity,
                        original_quantity,
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
