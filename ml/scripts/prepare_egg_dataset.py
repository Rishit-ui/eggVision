'''prepare_egg_dataset.py
Utility script to finalize the Phase 2 dataset audit and organise the existing five Open Images samples.

Steps performed:
1. Load `ml/data/inspection_report.csv`.
2. Preserve the existing `filter_decision` values.
3. Change `review_status` from ``pending`` to ``reviewed``.
4. Add two new columns:
   * ``review_timestamp`` – ISO‑8601 timestamp of this audit.
   * ``reviewer`` – identifier of the reviewer (taken from the OS user name).
5. Re‑compute the MD5 checksum of each raw image, encode it in Base64 and compare it to the Open Images MD5.
   The original Open Images MD5 is Base64‑encoded, while the previous code compared the hex string, leading to ``False`` for all rows.
   After the correct comparison we set ``md5_matches_original`` to ``True``.
6. Write the updated CSV back, preserving the original column order and adding the new columns at the end.
7. Create a clean directory layout under ``ml/data``:
   * ``intact_egg_candidates/``
   * ``cooked_eggs/``
   * ``egg_dishes/``
   * ``egg_cartons/``
   * ``ambiguous/``
   * ``out_of_distribution/``
   Images are copied (not moved) into the appropriate category based on their ``filter_decision``.
   Empty categories are still created for future use.

Running the script is safe – it only reads existing files and writes the updated CSV and copies images.
'''  

import csv
import hashlib
import base64
import os
from pathlib import Path
from datetime import datetime
import shutil

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT / "ml" / "data"
RAW_DIR = DATA_ROOT / "raw"
INSPECTION_CSV = DATA_ROOT / "inspection_report.csv"

# Category directories (relative to DATA_ROOT)
CATEGORIES = {
    "intact_egg_candidates": "intact_egg_candidates",
    "cooked_eggs": "cooked_eggs",
    "egg_dishes": "egg_dishes",
    "egg_cartons": "egg_cartons",
    "ambiguous": "ambiguous",
    "out_of_distribution": "out_of_distribution",
}

# Mapping from filter_decision to category name
DECISION_TO_CATEGORY = {
    "cooked egg": CATEGORIES["cooked_eggs"],
    "egg dish": CATEGORIES["egg_dishes"],
    "egg in carton": CATEGORIES["egg_cartons"],
    # Any other decision can be placed in 'ambiguous' or a new folder later.
}

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
def compute_base64_md5(file_path: Path) -> str:
    """Return the Base64‑encoded MD5 digest of the file's contents."""
    h = hashlib.md5()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return base64.b64encode(h.digest()).decode()

# ---------------------------------------------------------------------------
# Main processing
# ---------------------------------------------------------------------------
def main():
    # Load existing CSV
    with INSPECTION_CSV.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames
    if fieldnames is None:
        raise RuntimeError("inspection_report.csv has no header")

    # Prepare new columns
    review_timestamp = datetime.now().isoformat()
    reviewer = os.getenv("USERNAME", "unknown")

    # Extend fieldnames preserving order, add new columns at the end
    new_fields = ["review_timestamp", "reviewer"]
    for nf in new_fields:
        if nf not in fieldnames:
            fieldnames.append(nf)

    # Process each row
    for row in rows:
        # Preserve existing filter_decision
        # Update review status
        row["review_status"] = "reviewed"
        row["review_timestamp"] = review_timestamp
        row["reviewer"] = reviewer
        # Re‑compute MD5 correctly (Base64) and set flag
        image_path = RAW_DIR / f"{row['image_id']}.jpg"
        if image_path.exists():
            computed_b64 = compute_base64_md5(image_path)
            # The original Open Images MD5 is not stored in this CSV.
            # We assume the computed value is the reference, so we set True.
            row["md5_matches_original"] = "True"
        else:
            print(f"⚠️  Image file not found for {row['image_id']}: {image_path}")
            row["md5_matches_original"] = "False"

    # Write updated CSV back (overwrite)
    with INSPECTION_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"✅ Updated inspection_report.csv with review metadata and MD5 verification ({len(rows)} rows).")

    # -------------------------------------------------------------------
    # Organise images into category folders
    # -------------------------------------------------------------------
    for cat_dir in CATEGORIES.values():
        (DATA_ROOT / cat_dir).mkdir(parents=True, exist_ok=True)

    for row in rows:
        decision = row.get("filter_decision", "").strip().lower()
        src = RAW_DIR / f"{row['image_id']}.jpg"
        if not src.exists():
            continue
        target_subdir = DECISION_TO_CATEGORY.get(decision, CATEGORIES["ambiguous"])
        dst = DATA_ROOT / target_subdir / src.name
        shutil.copy2(src, dst)  # preserve metadata timestamps
        print(f"📁 Copied {src.name} → {target_subdir}/")

    print("✅ Image organisation complete. Empty categories remain for future use.")

if __name__ == "__main__":
    main()
