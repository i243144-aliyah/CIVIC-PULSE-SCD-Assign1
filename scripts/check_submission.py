"""Mechanical pre-flight checks for the CivicPulse final submission."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = (
    "README.md",
    "compose.yaml",
    "compose.prod.yaml",
    "backend/requirements.txt",
    "backend/Dockerfile",
    "backend/app/main.py",
    "backend/alembic/versions/0001_initial_complaints_schema.py",
    "frontend/package.json",
    "frontend/Dockerfile",
    ".github/workflows/ci.yml",
    ".github/workflows/cd.yml",
    ".github/workflows/release.yml",
    "docs/TRIAGE.md",
    "docs/RUNBOOK.md",
    "docs/ENGINEERING-NOTES.md",
    "docs/AI-USAGE.md",
    "docs/adr/0001-provider-interface.md",
    "docs/adr/0002-frontend-runtime-config.md",
    "docs/adr/0003-deploy-by-sha.md",
    "docs/adr/0004-pii-and-data-governance.md",
    "scripts/seed.py",
    "scripts/ci_integration_test.sh",
    "scripts/check_submission.py",
)

REQUIRED_MARKERS = {
    ".github/workflows/ci.yml": ("lint-and-type:", "test-backend:", "test-frontend:", "scan:", "manifests:", "integration:"),
    ".github/workflows/cd.yml": ("build-and-push:", "deploy-kind:", "anchore/sbom-action", "kustomize edit set image"),
    ".github/workflows/release.yml": ("v*", "softprops/action-gh-release", "draft: true"),
    "k8s/base/backend-hpa.yaml": ("autoscaling/v2", "minReplicas", "maxReplicas"),
    "k8s/base/backend-vpa.yaml": ("VerticalPodAutoscaler", "updateMode"),
}


def main() -> int:
    errors: list[str] = []
    for relative in REQUIRED_FILES:
        path = ROOT / relative
        if not path.is_file() or not path.read_text(encoding="utf-8").strip():
            errors.append(f"missing or empty: {relative}")

    for relative, markers in REQUIRED_MARKERS.items():
        text = (ROOT / relative).read_text(encoding="utf-8") if (ROOT / relative).is_file() else ""
        for marker in markers:
            if marker not in text:
                errors.append(f"missing marker {marker!r} in {relative}")

    if errors:
        print("Submission checks failed:")
        print("\n".join(f"- {error}" for error in errors))
        return 1

    print(f"Submission checks passed: {len(REQUIRED_FILES)} required files and workflow markers present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())