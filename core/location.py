def clean(v):
    return "" if v is None else str(v).strip()

def resolve_batch_location(conn, batch_id):
    batch_id = clean(batch_id)

    if not batch_id:
        return None

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
        WHERE batch_id = ?
        """,
        (batch_id,)
    ).fetchone()

    source_table = "batches"

    if row is None:
        row = conn.execute(
            """
            SELECT
                batch_id,
                'SCAN_BATCHES' AS source_system,
                box_id,
                segment,
                tcg,
                1 AS active,
                notes
            FROM scan_batches
            WHERE batch_id = ?
            """,
            (batch_id,)
        ).fetchone()

        source_table = "scan_batches"

    if row is None:
        return {
            "batch_id": batch_id,
            "found": False,
            "source_table": "",
            "source_system": "",
            "box_id": "",
            "segment": "",
            "physical_location": "",
            "shelf_id": "",
            "shelf_level": "",
            "box_type": "",
            "notes": "",
        }

    box_id = clean(row["box_id"])

    box = None
    if box_id:
        box = conn.execute(
            """
            SELECT
                box_id,
                box_type,
                physical_location,
                shelf_id,
                shelf_level,
                active,
                notes
            FROM box_map
            WHERE box_id = ?
            """,
            (box_id,)
        ).fetchone()

    return {
        "batch_id": clean(row["batch_id"]),
        "found": True,
        "source_table": source_table,
        "source_system": clean(row["source_system"]),
        "box_id": box_id,
        "segment": clean(row["segment"]),
        "tcg": clean(row["tcg"]),
        "active": row["active"],
        "physical_location": clean(box["physical_location"]) if box else "",
        "shelf_id": clean(box["shelf_id"]) if box else "",
        "shelf_level": clean(box["shelf_level"]) if box else "",
        "box_type": clean(box["box_type"]) if box else "",
        "batch_notes": clean(row["notes"]),
        "box_notes": clean(box["notes"]) if box else "",
    }
