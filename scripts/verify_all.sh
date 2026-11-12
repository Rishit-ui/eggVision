#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="${PYTHON_BIN:-$repo_root/backend/.venv/bin/python}"

if [[ ! -x "$python_bin" ]]; then
  python_bin="${PYTHON_BIN:-python3}"
fi

run_id="$(date -u +%Y%m%d-%H%M%S)"
artifact_root="$repo_root/artifacts/verification/$run_id"
mkdir -p "$artifact_root"
export PYTHONPATH="$repo_root:$repo_root/backend${PYTHONPATH:+:$PYTHONPATH}"

"$python_bin" "$repo_root/scripts/protected_data_manifest.py" --output "$artifact_root/protected-data-before.json"
"$python_bin" -m pip check
"$python_bin" -m ruff check backend ml scripts tests
"$python_bin" -m coverage run --source=backend,ml,scripts -m pytest tests ml/tests -q --junitxml="$artifact_root/pytest.xml"
"$python_bin" -m coverage xml -o "$artifact_root/coverage.xml"
"$python_bin" -m coverage html -d "$artifact_root/htmlcov"
"$python_bin" -c "import json; from app.main import app; from pathlib import Path; Path('$artifact_root/openapi.json').write_text(json.dumps(app.openapi(), indent=2), encoding='utf-8')"

pushd "$repo_root/frontend" >/dev/null
npm ci
npm run lint
npm run type-check
npm run build
popd >/dev/null

if docker info >"$artifact_root/docker-info.log" 2>&1; then
  docker compose config --no-interpolate >"$artifact_root/docker-compose-config.log"
  docker build -f docker/backend.Dockerfile -t eggvision-backend-verify . >"$artifact_root/docker-backend-build.log"
  docker build -f docker/frontend.Dockerfile -t eggvision-frontend-verify ./frontend >"$artifact_root/docker-frontend-build.log"
fi

"$python_bin" "$repo_root/scripts/protected_data_manifest.py" --output "$artifact_root/protected-data-after.json" --compare "$artifact_root/protected-data-before.json"
printf 'Verification completed: %s\n' "$artifact_root"
