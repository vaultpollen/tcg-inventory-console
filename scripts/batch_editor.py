import sys
from pathlib import Path
import csv
import shutil
import sqlite3
import uuid
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox

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

selected_csv_paths = []


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


def ensure_import_log(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS import_log (
            import_id INTEGER PRIMARY KEY AUTOINCREMENT,
            imported_at TEXT DEFAULT CURRENT_TIMESTAMP,
            filename TEXT,
            batch_id TEXT,
            rows_imported INTEGER
        )
    """)


def archive_imported_csv(csv_path):
    csv_path = Path(csv_path)

    archive_dir = (
        Path(__file__).resolve().parents[1]
        / "inventory_imports"
        / "processed"
        / datetime.now().strftime("%Y-%m-%d")
    )
    archive_dir.mkdir(parents=True, exist_ok=True)

    target = archive_dir / csv_path.name

    if target.exists():
        stamp = datetime.now().strftime("%H%M%S")
        target = archive_dir / f"{csv_path.stem}_{stamp}{csv_path.suffix}"

    shutil.move(str(csv_path), str(target))
    return target


def parse_filename_metadata(csv_path):
    """
    Expected filename format:
      SI101 MTG Normal en 57 1.csv
      SI102 Pokemon Reverse Holofoil en 57 2.csv

    Parsed as:
      batch_id = SI101
      tcg = mtg
      print = normal / reverse holofoil / etc.
      language = en
      box_id = 57
      segment = 1
    """
    csv_path = Path(csv_path)
    stem = csv_path.stem.strip()
    parts = stem.split()

    if len(parts) < 6:
        raise ValueError(
            "Filename must look like:\n\n"
            "SI101 MTG Normal en 57 1.csv\n\n"
            f"Bad file:\n{csv_path.name}"
        )

    batch_id = parts[0]
    tcg = parts[1].lower()
    language = parts[-3].lower()
    box_id = parts[-2]
    segment = parts[-1]
    print_value = " ".join(parts[2:-3]).replace("_", " ").lower()

    tcg_map = {
        "magic": "mtg",
        "mtg": "mtg",
        "pokemon": "pokemon",
        "pokémon": "pokemon",
        "yugioh": "yugioh",
        "yu-gi-oh": "yugioh",
        "ygo": "yugioh",
    }

    return {
        "batch_id": clean(batch_id),
        "tcg": tcg_map.get(tcg, tcg),
        "print": clean(print_value),
        "language": clean(language),
        "box_id": clean(box_id),
        "segment": clean(segment),
    }


def normalize_card_row(row, meta):
    return {
        "row_id": str(uuid.uuid4()),
        "name": clean(find_first(row, ["Card Name", "name", "Product Name", "Title"])),
        "set_code": clean(find_first(row, ["set_code", "Set Code", "Set Abbrev", "Set Abbreviation"])),
        "set_name": clean(find_first(row, ["set_name", "Set Name", "Set"])),
        "collector_no": clean(find_first(row, ["Card #", "collector_no", "Number"])),
        "print": clean(meta["print"]).lower(),
        "rarity": clean(find_first(row, ["Rarity", "rarity"])).lower(),
        "quantity": parse_quantity(row),
        "condition": norm_condition(find_first(row, ["Condition", "condition"])),
        "language": norm_language(meta["language"]),
        "batch_id": clean(meta["batch_id"]),
        "tcg": clean(meta["tcg"]).lower(),
    }


def upsert_batch(conn, batch_id, source_system, box_id, segment, tcg, active, notes):
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
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(batch_id) DO UPDATE SET
            source_system = excluded.source_system,
            box_id = excluded.box_id,
            segment = excluded.segment,
            tcg = excluded.tcg,
            active = excluded.active,
            notes = excluded.notes
        """,
        (
            clean(batch_id),
            clean(source_system) or "NEW_MAP",
            clean(box_id),
            clean(segment),
            clean(tcg).lower(),
            int(active),
            clean(notes),
        )
    )


def insert_cards(conn, card_rows):
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

    for r in card_rows:
        if not r["name"]:
            continue
        if int(r["quantity"] or 0) <= 0:
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


def load_batch():
    batch_id = clean(batch_var.get())

    if not batch_id:
        messagebox.showwarning("Missing batch", "Enter a batch ID.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    row = conn.execute(
        """
        SELECT
            batch_id,
            source_system,
            box_id,
            segment,
            tcg,
            active,
            notes
        FROM batches
        WHERE TRIM(batch_id) = TRIM(?)
        """,
        (batch_id,)
    ).fetchone()

    conn.close()

    if row is None:
        source_var.set("NEW_MAP")
        box_var.set("")
        segment_var.set("")
        tcg_var.set("")
        active_var.set(1)
        notes_text.delete("1.0", tk.END)
        status_var.set("New batch.")
        return

    batch_var.set(clean(row["batch_id"]))
    source_var.set(clean(row["source_system"]) or "NEW_MAP")
    box_var.set(clean(row["box_id"]))
    segment_var.set(clean(row["segment"]))
    tcg_var.set(clean(row["tcg"]))
    active_var.set(int(row["active"] or 1))

    notes_text.delete("1.0", tk.END)
    notes_text.insert("1.0", clean(row["notes"]))

    status_var.set("Loaded existing batch.")


def save_batch():
    batch_id = clean(batch_var.get())
    source = clean(source_var.get()) or "NEW_MAP"
    box_id = clean(box_var.get())
    segment = clean(segment_var.get())
    tcg = clean(tcg_var.get())
    active = int(active_var.get())
    notes = clean(notes_text.get("1.0", tk.END))

    if not batch_id:
        messagebox.showerror("Missing batch", "Batch ID is required.")
        return

    if not box_id:
        messagebox.showerror("Missing box", "Box ID is required.")
        return

    conn = sqlite3.connect(DB_PATH)

    try:
        upsert_batch(conn, batch_id, source, box_id, segment, tcg, active, notes)
        conn.commit()

        status_var.set(f"Saved batch: {batch_id}")
        messagebox.showinfo("Saved", f"Batch saved:\n{batch_id}")

    except Exception as e:
        conn.rollback()
        messagebox.showerror("Save failed", str(e))
        raise

    finally:
        conn.close()


def select_csvs():
    global selected_csv_paths

    paths = filedialog.askopenfilenames(
        title="Select CSV batch files",
        filetypes=[("CSV files", "*.csv")]
    )

    if not paths:
        return

    selected_csv_paths = list(paths)
    selected_var.set(f"{len(selected_csv_paths)} file(s) selected")

    if len(selected_csv_paths) == 1:
        try:
            meta = parse_filename_metadata(selected_csv_paths[0])
            batch_var.set(meta["batch_id"])
            source_var.set("TCGPLAYER_CSV")
            box_var.set(meta["box_id"])
            segment_var.set(meta["segment"])
            tcg_var.set(meta["tcg"])
            active_var.set(1)
            status_var.set("Filename parsed into form.")
        except Exception as e:
            messagebox.showerror("Filename parse failed", str(e))
            status_var.set("Filename parse failed.")
    else:
        status_var.set("Bulk import ready.")


def import_selected_csvs():
    if not selected_csv_paths:
        messagebox.showwarning("No files", "Select CSV files first.")
        return

    parsed = []
    grand_total = 0

    try:
        for csv_path in selected_csv_paths:
            meta = parse_filename_metadata(csv_path)
            card_rows = []

            with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)

                for row in reader:
                    nr = normalize_card_row(row, meta)
                    if nr["name"] and int(nr["quantity"] or 0) > 0:
                        card_rows.append(nr)

            parsed.append({
                "path": Path(csv_path),
                "meta": meta,
                "rows": card_rows,
            })

    except Exception as e:
        messagebox.showerror("Import preparation failed", str(e))
        raise

    if not parsed:
        messagebox.showwarning("Nothing to import", "No usable CSV files found.")
        return

    msg = "\n".join(
        f"{p['path'].name}: {p['meta']['batch_id']} → box {p['meta']['box_id']} segment {p['meta']['segment']} | rows {len(p['rows'])}"
        for p in parsed[:20]
    )

    if len(parsed) > 20:
        msg += f"\n...and {len(parsed) - 20} more."

    if not messagebox.askyesno(
        "Confirm import",
        f"Import these CSVs into SQLite?\n\n{msg}\n\n"
        f"Files will be moved to inventory_imports/processed after successful commit."
    ):
        return

    conn = sqlite3.connect(DB_PATH)

    try:
        ensure_import_log(conn)

        for p in parsed:
            meta = p["meta"]
            rows = p["rows"]

            upsert_batch(
                conn,
                meta["batch_id"],
                "TCGPLAYER_CSV",
                meta["box_id"],
                meta["segment"],
                meta["tcg"],
                1,
                "Created/updated by CSV ingest.",
            )

            inserted = insert_cards(conn, rows)
            grand_total += inserted

            conn.execute(
                """
                INSERT INTO import_log (
                    filename,
                    batch_id,
                    rows_imported
                )
                VALUES (?, ?, ?)
                """,
                (
                    p["path"].name,
                    meta["batch_id"],
                    inserted,
                )
            )

        conn.commit()

    except Exception as e:
        conn.rollback()
        messagebox.showerror("Import failed", str(e))
        raise

    finally:
        conn.close()

    archived_count = 0
    archive_errors = []

    for p in parsed:
        try:
            archive_imported_csv(p["path"])
            archived_count += 1
        except Exception as e:
            archive_errors.append(f"{p['path'].name}: {e}")

    selected_csv_paths.clear()
    selected_var.set("0 files selected")
    status_var.set(f"Imported {grand_total} card rows from {len(parsed)} file(s).")

    if archive_errors:
        messagebox.showwarning(
            "Import succeeded, archive incomplete",
            f"Database import succeeded.\n\n"
            f"Imported card rows: {grand_total}\n"
            f"Archived CSV files: {archived_count}/{len(parsed)}\n\n"
            f"Archive errors:\n" + "\n".join(archive_errors[:10])
        )
    else:
        messagebox.showinfo(
            "Import complete",
            f"Imported {grand_total} card rows.\n"
            f"Batch files processed: {len(parsed)}\n"
            f"CSV files archived: {archived_count}"
        )


def clear_form():
    batch_var.set("")
    source_var.set("NEW_MAP")
    box_var.set("")
    segment_var.set("")
    tcg_var.set("")
    active_var.set(1)
    notes_text.delete("1.0", tk.END)
    selected_csv_paths.clear()
    selected_var.set("0 files selected")
    status_var.set("Ready.")


root = tk.Tk()
root.title("Add / Update Batch")
root.geometry("650x610")

batch_var = tk.StringVar()
source_var = tk.StringVar(value="NEW_MAP")
box_var = tk.StringVar()
segment_var = tk.StringVar()
tcg_var = tk.StringVar()
active_var = tk.IntVar(value=1)
selected_var = tk.StringVar(value="0 files selected")
status_var = tk.StringVar(value="Ready.")

frame = tk.Frame(root)
frame.pack(fill="both", expand=True, padx=15, pady=15)

tk.Label(frame, text="Batch Location").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))

tk.Label(frame, text="Batch ID").grid(row=1, column=0, sticky="w")
tk.Entry(frame, textvariable=batch_var, width=42).grid(row=1, column=1, sticky="w")
tk.Button(frame, text="Load", command=load_batch).grid(row=1, column=2, padx=5)

tk.Label(frame, text="Source").grid(row=2, column=0, sticky="w", pady=5)
tk.Entry(frame, textvariable=source_var, width=42).grid(row=2, column=1, sticky="w")

tk.Label(frame, text="Box ID").grid(row=3, column=0, sticky="w", pady=5)
tk.Entry(frame, textvariable=box_var, width=42).grid(row=3, column=1, sticky="w")

tk.Label(frame, text="Segment").grid(row=4, column=0, sticky="w", pady=5)
tk.Entry(frame, textvariable=segment_var, width=42).grid(row=4, column=1, sticky="w")

tk.Label(frame, text="TCG").grid(row=5, column=0, sticky="w", pady=5)
tk.Entry(frame, textvariable=tcg_var, width=42).grid(row=5, column=1, sticky="w")

tk.Label(frame, text="Active").grid(row=6, column=0, sticky="w", pady=5)
tk.Checkbutton(frame, variable=active_var).grid(row=6, column=1, sticky="w")

tk.Label(frame, text="Notes").grid(row=7, column=0, sticky="nw", pady=5)
notes_text = tk.Text(frame, width=43, height=5)
notes_text.grid(row=7, column=1, sticky="w")

button_frame = tk.Frame(frame)
button_frame.grid(row=8, column=1, sticky="w", pady=12)

tk.Button(button_frame, text="Save Location Only", command=save_batch, width=18).pack(side="left", padx=3)
tk.Button(button_frame, text="Clear", command=clear_form, width=10).pack(side="left", padx=3)

tk.Label(frame, text="CSV Inventory Import").grid(row=9, column=0, columnspan=3, sticky="w", pady=(16, 6))

tk.Label(
    frame,
    text="Expected filename: SI101 MTG Normal en 57 1.csv",
    fg="#555555"
).grid(row=10, column=1, sticky="w")

csv_frame = tk.Frame(frame)
csv_frame.grid(row=11, column=1, sticky="w", pady=8)

tk.Button(csv_frame, text="Select CSV(s)", command=select_csvs, width=16).pack(side="left", padx=3)
tk.Label(csv_frame, textvariable=selected_var).pack(side="left", padx=8)

tk.Button(
    frame,
    text="Import Selected CSVs",
    command=import_selected_csvs,
    width=24
).grid(row=12, column=1, sticky="w", pady=8)

tk.Label(frame, textvariable=status_var).grid(row=13, column=0, columnspan=3, sticky="w", pady=8)

root.mainloop()
