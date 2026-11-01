# Custom Egg Collection

This directory is dedicated to storing **your own photographs of individual, shell‑on chicken eggs**.  It is completely separate from the Open Images data used in earlier phases, so nothing you add here will ever affect the existing dataset.

## Folder layout
```
ml/data/custom_collection/
├─ raw/                # Original photographs, organized by specimen ID
│   └─ <SPECIMEN_ID>/  # e.g. EGG001/EGG001_0001.jpg
├─ metadata/           # One JSON side‑car per photograph
│   └─ <SPECIMEN_ID>/  # e.g. EGG001/EGG001_0001.json
├─ manifests/          # CSV manifest files (images, specimens)
│   ├─ images.csv
│   └─ specimens.csv
└─ inbox/              # Optional staging area for files awaiting registration
```

## How to photograph an egg
1. **Use a plain background** (e.g., white paper or fabric) and avoid clutter.
2. **Lighting** – aim for even, diffuse lighting; record whether it is natural or artificial in the metadata.
3. **Views** – capture each egg from several angles:
   - `top`
   - `side`
   - `oblique`
   - `closeup`
   - `other` (if none of the above apply)
4. **File format** – JPEG, PNG or WebP are accepted.
5. **Preserve the original file** – do *not* edit or rename the source image before registration.

## Specimen IDs
- Assign a **unique** ID to each physical egg, e.g. `EGG001`, `EGG002`.
- **All photographs of the same egg must use the same ID.**
- Do **not** create a new ID just because you photograph a different view.

## Registering photographs
The command‑line helper `register_custom_egg_images.py` handles registration:
```bash
python ml/scripts/register_custom_egg_images.py \
    --source /path/to/photo.jpg \
    --specimen EGG001 \
    --view top \
    [--lighting natural] [--background plain] [--photographer "Alice"]
```
- The script validates the image, detects duplicates (by SHA‑256), copies it into the collection, generates a JSON side‑car and updates the CSV manifests.
- If the image is corrupt, unsupported, or a duplicate, the registration is aborted and a clear error is reported.

## Metadata fields (generated per photograph)
| Field | Description |
|------|-------------|
| `specimen_id` | The egg identifier you supplied (e.g. `EGG001`). |
| `capture_id` | A unique identifier for this photograph (e.g. `EGG001_0001`). |
| `original_filename` | Name of the source file you gave to the script. |
| `stored_filename` | Name of the file inside the collection (`raw/EGG001/…`). |
| `sha256` | SHA‑256 hash of the image bytes (used for duplicate detection). |
| `image_width`, `image_height` | Dimensions in pixels (read safely with Pillow). |
| `format` | Image format (`JPEG`, `PNG`, `WEBP`). |
| `view` | One of `top`, `side`, `oblique`, `closeup`, `other`. |
| `captured_at` | Timestamp supplied by the user (optional; if unknown leave `null`). |
| `registered_at` | ISO‑8601 timestamp of when the script added the image. |
| `lighting` | User‑provided description (e.g., `natural`, `studio`). |
| `background` | Description of the background (e.g., `white paper`). |
| `photographer` | Optional name of the person who took the photo. |
| `provenance` | Free‑form note about how the image was obtained. |
| `license` | Not recorded unless explicitly supplied (most of our images are private). |
| `review_status` | Starts as `pending`; a human reviewer will later set it to `reviewed` or `rejected`. |

## Manifest CSVs
### `images.csv`
```
image_id,specimen_id,stored_filename,view,sha256,width,height,format,captured_at,registered_at,lighting,background,photographer,provenance,license,review_status
```
Each row corresponds to one photograph.

### `specimens.csv`
```
specimen_id,registered_at,notes
```
Records when a specimen ID first entered the collection.

## Why we keep one specimen per split
When we later split the dataset for training/validation/testing we must keep **all photographs of the same physical egg together** in a single split.  This prevents the model from seeing the same egg in both training and evaluation, which would artificially inflate performance.

## Pilot plan
- **10‑15 physical eggs** (specimen IDs `EGG001`‑`EGG015`).
- **5‑8 photos per egg** covering the view categories above.
- **~50‑100 total photographs**.

This pilot is *only* to verify that our registration workflow works and that we can collect consistent, traceable data.  It does **not** constitute a final training set.

---

*Please follow the instructions carefully, keep the original source files unchanged, and let the registration script handle everything else.*