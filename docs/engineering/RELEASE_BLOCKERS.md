# EggVision release blockers

Last reviewed: 2026-11-13 (Asia/Kolkata)

## External evidence or access required

| Blocker | Why it blocks | What resolves it |
| --- | --- | --- |
| Physical specimens and a controlled capture chamber | Software tests cannot demonstrate optical repeatability, shell-colour robustness or a valid candling workflow. | Calibrated chamber, camera/illumination settings, and documented capture sessions across representative intact eggs. |
| Destructive laboratory ground truth | Haugh Unit and related freshness claims require paired physical measurements; no substitute is present in the repository. | Traceable paired measurements (egg mass, albumen height and protocol metadata, plus optional pH/yolk measures) linked to specimen IDs. |
| Reviewed labels and leakage-safe cohort | There are zero eligible intact shell-on egg images in the repository. Open Images examples are cooked/dishes/carton. | Acquisition and annotation of intact egg images following `ml/ontology.yaml` and `ml/data/custom_collection/README.md`. |
| Model artifacts and evaluation | The only active inference implementation is intentionally `MODEL_NOT_READY`. | Reproducible trained checkpoints, held-out evaluation, calibration, model card, and approval evidence once eligible data exists. |
| Unmerged Alembic fix on master | Render deploys from `master`. Commits `3c7721ba` (fixing `%(here)s/alembic`) and `4c5da8d2` remain on feature branch `codex/eggvision-fix-frontend-build`. Latest deploy on master failed with exit status 255. | Code review and merging of the feature branch into `master` to trigger a clean Render deployment. |
| Vercel project deployment | `https://egg-vision.vercel.app` and preview URLs currently return 404 DEPLOYMENT_NOT_FOUND. | Link the GitHub repository in the Vercel dashboard and trigger an authorized deployment. |
| Provider credentials / production secrets | Production startup validates JWT_SECRET (>= 32 chars), BOOTSTRAP_TOKEN (>= 32 chars), and external S3/Postgres URLs. | Supply actual secrets in Render and Vercel environment dashboards. |

## Non-blocking engineering work

All independent engineering workstreams are complete:
- Automated end-to-end verification harness passing 100% (Run ID `20261113-151145`).
- Next.js production build passing 12/12 static and dynamic routes.
- Full pytest test suite passing with 102 tests (66 backend/cv + 9 security audit + 27 ml) and 0 warnings.
- Test line coverage: 80.7% (1,995 / 2,472 lines covered).
- Code style and linting (ruff, pip check, type check) passing with 0 errors.
- Protected research data integrity verified before and after runs (0 files altered).
- OpenAPI specification generation verified.
- 6-class visible shell defect ontology documented in `ml/ontology.yaml`.
- Login rate limiting (sliding window, proxy-aware) and admin user authorization implemented and tested.
