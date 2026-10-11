# Dataset Requirements

## Egg Types
- White
- Brown
- Desi (local breeds)
- *Future*: Quail, Duck

## Metadata Schema
Each image requires metadata:
- Timestamp
- Ambient temperature
- Ambient humidity
- Storage condition (fridge/room)
- Stated age (days since laid)

## Ground Truth Collection Protocol
- Haugh unit measurement (destructive test)
- Visual inspection of yolk and albumen
- Expert grading

## Data Splitting Strategy
- Egg-level separation (no leakage)
- Farm-level cross-validation
- Time-based splits for temporal drift analysis

## Augmentation Guidelines
- Rotation, slight scaling, brightness adjustments (within realistic physical bounds).

## Storage Format
Images stored in MinIO/S3, metadata and labels in PostgreSQL.
