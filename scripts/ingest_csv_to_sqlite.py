import sys
from pathlib import Path
import csv
import sqlite3
import uuid
from tkinter import Tk, filedialog, simpledialog, messagebox

sys.path.append(str(Path(__file__).resolve().parents[1]))

from core.paths import DB_PATH


LANG_MAP = {
    "english": "en",
    "japanese": "ja",
    "french": "fr",
    "german": "de",
    "italian": "it",
    "spanish": "es",
    "portuguese": "pt",
    "korean": "ko",
    "chinese (simplified)": "zh-hans",
    "chinese (traditional)": "zh-hant",
}

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


def norm_language(v):
    s = clean(v).lower()
    return LANG_MAP.get(s, s)


def find_first(row, candidates):
    for c in candidates:
        if c in row:
            return row[c]
    return ""


def parse_quantity(row):
    raw = clean(find_first(row, ["Add to Quantity", "Quantity", "Qty"]))
    try:
        return int(float(raw))
    except Exception:
        return 0


def normalize_row(row, batch_id, tcg, print_value, language):
    return {
        "row_id": str(uuid.uuid4()),
        "name": clean(find_first(row, ["Card Name", "name", "Product Name", "Title"])),
        "set_code": clean(find_first(row, ["set_code", "Set Code", "Set Abbrev", "Set Abbreviation"])),
        "set_name": clean(find_first(row, ["set_name", "Set Name", "Set"])),
        "collector_no": clean(find_first(row, ["Card #", "collector_no", "Number"])),
        "print": clean(print_value).lower(),
        "rarity": clean(find_first(row, ["Rarity", "rarity"])).lower(),
        "quantity": parse_quantity(row),
        "condition": norm_condition(find_first(row, ["Condition", "condition"])),
        "language": norm_language(language),
        "batch_id": batch_id,
        "tcg": clean(tcg).lower(),
    }


def insert_cards(conn, rows):
    sql = """
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
    """

    count = 0

    for r in rows:
        if not r["name"]:
            continue
        if r["quantity"] <= 0:
            continue

        conn.execute(sql, (
            r["row_id"],
            r["name"],
            r["set_code"],
            r["set_name"],
            r["collector_no"],
            r["print"],
            r["rarity"],
            r["quantity"],
            r["condition"],
            r["language"],
            r["batch_id"],
            r["tcg"],
        ))

        count += 1

    return count


def upsert_batch(conn, batch_id, source_system, box_id, segment, tcg):
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
            active = 1
        """,
        (
            batch_id,
            source_system,
            box_id,
            segment,
            tcg,
            "Created/updated by SQLite CSV ingest.",
        )
    )


def main():
    root = Tk()
    root.withdraw()

    csv_paths = filedialog.askopenfilenames(
        title="Select one or more TCGPlayer CSVs",
        filetypes=[("CSV files", "*.csv")]
    )

    if not csv_paths:
        return

    tcg = simpledialog.askstring("TCG", "TCG value? Example: mtg / pokemon / yugioh")
    if not tcg:
        return

    print_value = simpledialog.askstring("Print", "Print value? Example: normal / foil / reverse holofoil")
    if not print_value:
        return

    language = simpledialog.askstring("Language", "Language? Example: en")
    if not language:
        return

    source_system = simpledialog.askstring("Source", "Source system? Example: TCGPLAYER_CSV / TCGA / BUYSPORTSCARDS")
    if not source_system:
        source_system = "TCGPLAYER_CSV"

    all_rows = []
    batch_count = 0

    conn = sqlite3.connect(DB_PATH)

    try:
        for csv_path in csv_paths:
            csv_path = Path(csv_path)

            default_batch = csv_path.stem.split()[0]

            batch_id = simpledialog.askstring(
                "Batch ID",
                f"Batch ID for:\n{csv_path.name}",
                initialvalue=default_batch
            )

            if not batch_id:
                continue

            box_id = simpledialog.askstring(
                "Box ID",
                f"Box ID for batch {batch_id}:"
            )

            if not box_id:
                continue

            segment = simpledialog.askstring(
                "Segment",
                f"Segment for batch {batch_id}:"
            )

            if segment is None:
                segment = ""

            upsert_batch(
                conn,
                clean(batch_id),
                clean(source_system).upper(),
                clean(box_id),
                clean(segment),
                clean(tcg).lower(),
            )

            batch_count += 1

            with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)

                for row in reader:
                    nr = normalize_row(
                        row,
                        clean(batch_id),
                        clean(tcg),
                        clean(print_value),
                        clean(language),
                    )

                    if nr["name"] and nr["quantity"] > 0:
                        all_rows.append(nr)

        card_count = insert_cards(conn, all_rows)

        conn.commit()

        messagebox.showinfo(
            "Import complete",
            f"Imported directly into SQLite.\n\n"
            f"Batches updated: {batch_count}\n"
            f"Card rows inserted: {card_count}"
        )

    except Exception as e:
        conn.rollback()
        messagebox.showerror("Import failed", str(e))
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    main()
