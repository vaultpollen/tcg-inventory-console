from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DB_PATH = ROOT / "inventory.db"
OUT_DIR = ROOT / "pick_outputs"
OUT_DIR.mkdir(exist_ok=True)

PICK_WAVE_CSV = OUT_DIR / "pick_wave.csv"
PACK_ORDER_CSV = OUT_DIR / "pack_order.csv"
MISSING_ITEMS_CSV = OUT_DIR / "missing_items.csv"
PICK_WORKFLOW_CSV = OUT_DIR / "pick_workflow.csv"
PICK_WAVE_XLSX = OUT_DIR / "pick_wave.xlsx"

IMPORTS_DIR = ROOT / "inventory_imports"
PROCESSED_IMPORTS_DIR = IMPORTS_DIR / "processed"
PROCESSED_IMPORTS_DIR.mkdir(parents=True, exist_ok=True)

BACKUP_DIR = ROOT / "backups"
BACKUP_DIR.mkdir(exist_ok=True)
