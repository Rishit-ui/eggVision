# Verification runbook

## Native Windows verification

Use the project backend environment and run from the repository root:

```powershell
.\scripts\verify_all.ps1
```

The script writes command-specific logs, JUnit XML, coverage XML/HTML, OpenAPI
JSON, runtime metadata and before/after protected-data manifests beneath
`artifacts/verification/<run-id>/`. It exits non-zero if a required check fails.
It never prints configured secret values.

`-SkipFrontend` and `-SkipDocker` are diagnostic switches only. They must not
be used to claim a release passed those checks.

## Linux / CI verification

Create an environment with `backend/requirements.txt`, then run:

```bash
PYTHON_BIN=python3 ./scripts/verify_all.sh
```

The script expects Node 20 and Docker only where the corresponding checks are
to run. Docker integration is recorded as unavailable when a local daemon is
not accessible; a release cannot treat that as evidence of a successful image
build.

## Interpretation

- A passing synthetic CV test validates a deterministic code path only. It is
  not a real-world detector-performance result.
- A passing local build is not a deployed smoke test.
- The protected-data comparison must have no added, changed or removed path.
- Database migration execution against a disposable PostgreSQL database remains
  a separate required integration check until Docker or an approved temporary
  local database is available.
