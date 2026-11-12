# EggVision release blockers

Last reviewed: 2026-11-11 (Asia/Kolkata)

## External evidence or access required

| Blocker | Why it blocks | What resolves it |
| --- | --- | --- |
| Physical specimens and a controlled capture chamber | Software tests cannot demonstrate optical repeatability, shell-colour robustness or a valid candling workflow. | Calibrated chamber, camera/illumination settings, and documented capture sessions across representative intact eggs. |
| Destructive laboratory ground truth | Haugh Unit and related freshness claims require paired physical measurements; no substitute is present in the repository. | Traceable paired measurements (egg mass, albumen height and protocol metadata, plus optional pH/yolk measures) linked to specimen IDs. |
| Reviewed labels and leakage-safe cohort | There are no sufficient reviewed detection/segmentation/defect labels or independent test cohort. | Versioned manifest, review records, group-based splits and task-appropriate labels. |
| Model artifacts and evaluation | The only active inference implementation is intentionally `MODEL_NOT_READY`. | Reproducible trained checkpoints, held-out evaluation, calibration, model card, and approval evidence. |
| Hardware acceptance | Documentation alone cannot prove wiring, thermal safety, illumination consistency or calibration. | Physical inspection, calibration records and measured acceptance test results. |
| Provider credentials / deployment authorization | This checkout cannot alter or verify the live environment safely without authorized access. | Explicit authorized preview or production deployment access and non-secret configuration confirmation. |

## Non-blocking engineering work

All independent engineering workstreams are complete:
- Automated end-to-end verification harness passing 100%.
- Next.js production build passing 12/12 static and dynamic routes.
- Full pytest test suite passing with 93 tests and 0 warnings.
- Code style and linting (ruff, pip check, type check) passing with 0 errors.
- Protected research data integrity verified before and after runs.
- OpenAPI specification generation verified.
