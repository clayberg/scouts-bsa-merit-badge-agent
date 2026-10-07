#!/usr/bin/env bash
# ==============================================================================
# Scouts BSA Merit Badge Counselor Workbench — Capstone GitHub Sync & Bundler
# ==============================================================================
# Purpose:
#   1. Commits any pending project changes on branch `main`.
#   2. Configures and syncs BOTH GitHub remotes:
#      - Original / Personal Repo (`origin`):
#        https://github.com/clayberg/scouts-bsa-merit-badge-agent
#      - Official FDE Capstone Org Repo (`fde`):
#        https://github.com/cloud-ai-fde/clayberg-scouts-bsa-merit-badge-agent
#   3. Creates an annotated Capstone release tag (`capstone-YYYYMMDD`) whose
#      annotation embeds the official `cloud-ai-fde` repository URL required by
#      Stage 1 (`analyzer-initial-checks`) of go/capstone-app.
#   4. Builds and verifies the standalone Git bundle:
#      `scouts-bsa-merit-badge-agent.bundle`
#
# Usage:
#   ./scripts/publish_and_bundle_capstone.sh              # Local commit + tag + bundle + push to remotes
#   ./scripts/publish_and_bundle_capstone.sh --bundle-only # Only commit, tag, and build/verify .bundle locally
#   ./scripts/publish_and_bundle_capstone.sh --run-tests   # Run pytest & eval_gate.py before bundling
# ==============================================================================

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_ROOT}"

PERSONAL_REPO_HTTPS="https://github.com/clayberg/scouts-bsa-merit-badge-agent"
PERSONAL_REPO_GIT="${PERSONAL_REPO_HTTPS}.git"

FDE_ORG_REPO_HTTPS="https://github.com/cloud-ai-fde/clayberg-scouts-bsa-merit-badge-agent"
FDE_ORG_REPO_GIT="${FDE_ORG_REPO_HTTPS}.git"

DATE_STAMP="$(date -u +%Y%m%d)"
CAPSTONE_TAG="${CAPSTONE_TAG:-capstone-${DATE_STAMP}}"
BUNDLE_FILE="${PROJECT_ROOT}/scouts-bsa-merit-badge-agent.bundle"

BUNDLE_ONLY=false
RUN_TESTS=false

for arg in "$@"; do
  case "${arg}" in
    --bundle-only)
      BUNDLE_ONLY=true
      ;;
    --run-tests)
      RUN_TESTS=true
      ;;
    *)
      echo "Unknown option: ${arg}"
      echo "Usage: $0 [--bundle-only] [--run-tests]"
      exit 1
      ;;
  esac
done

echo "======================================================================"
echo "1. Pre-Flight Workspace & Git Status Check"
echo "======================================================================"
echo "Project Directory : ${PROJECT_ROOT}"
echo "Target Tag        : ${CAPSTONE_TAG}"
echo "Output Bundle     : ${BUNDLE_FILE}"

# Ensure .cache/ and *.bundle are ignored so the bundle never recursively includes itself
if ! grep -q "^\*.bundle" .gitignore 2>/dev/null; then
  echo "*.bundle" >> .gitignore
fi

echo ""
echo "======================================================================"
echo "1a. Running Blocking Ruff Static Linter (CI/CD Pre-Check)"
echo "======================================================================"
if [[ -x ".venv/bin/ruff" ]]; then
  .venv/bin/ruff check src/ tests/ scripts/
elif command -v ruff >/dev/null 2>&1; then
  ruff check src/ tests/ scripts/
fi

if [[ "${RUN_TESTS}" == "true" ]]; then
  echo ""
  echo "======================================================================"
  echo "1b. Running Automated Test Suite & Golden Evaluation Gate"
  echo "======================================================================"
  if [[ -x ".venv/bin/pytest" ]]; then
    .venv/bin/pytest tests/ -q
    .venv/bin/python scripts/eval_gate.py
  else
    pytest tests/ -q
    python3 scripts/eval_gate.py
  fi
fi

echo ""
echo "======================================================================"
echo "2. Staging & Committing Latest Project Changes"
echo "======================================================================"
git add -A
if ! git diff --cached --quiet; then
  git commit -m "chore(capstone): sync latest documentation, companion guide Q&A, and submission scripts (${CAPSTONE_TAG})"
  echo "Committed latest workspace changes to $(git rev-parse --short HEAD)."
else
  echo "Working tree is clean (HEAD at $(git rev-parse --short HEAD))."
fi

echo ""
echo "======================================================================"
echo "3. Configuring GitHub Remotes (Personal 'origin' + FDE Org 'fde')"
echo "======================================================================"
# Ensure global gitconfig does not force SSH over HTTPS when using gh auth git-credential
git config --global --unset url.git@github.com:.insteadof 2>/dev/null || true

if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "${PERSONAL_REPO_GIT}"
else
  git remote add origin "${PERSONAL_REPO_GIT}"
fi

if git remote get-url fde >/dev/null 2>&1; then
  git remote set-url fde "${FDE_ORG_REPO_GIT}"
else
  git remote add fde "${FDE_ORG_REPO_GIT}"
fi

git remote -v

echo ""
echo "======================================================================"
echo "4. Creating Annotated Capstone Tag (${CAPSTONE_TAG})"
echo "======================================================================"
git tag -f -a "${CAPSTONE_TAG}" -m "FDE Capstone Submission (${CAPSTONE_TAG})
Repository: ${FDE_ORG_REPO_HTTPS}
Mirror: ${PERSONAL_REPO_HTTPS}
Candidate: clayberg@google.com (Eric Clayberg)
Project: Scouts BSA Merit Badge Counselor Workbench (Google ADK + Vertex AI + Cloud Run)"

echo "Verified Tag Annotation:"
git show "${CAPSTONE_TAG}" --no-patch

echo ""
echo "======================================================================"
echo "5. Building & Verifying Standalone Git Bundle (.bundle)"
echo "======================================================================"
rm -f "${BUNDLE_FILE}"
git bundle create "${BUNDLE_FILE}" --all

echo ""
echo "Running 'git bundle verify'..."
git bundle verify "${BUNDLE_FILE}"

echo ""
echo "Bundle Heads & Tags:"
git bundle list-heads "${BUNDLE_FILE}"

BUNDLE_SIZE="$(du -h "${BUNDLE_FILE}" | cut -f1)"
echo "Bundle successfully created: ${BUNDLE_FILE} (${BUNDLE_SIZE})"

if [[ "${BUNDLE_ONLY}" == "true" ]]; then
  echo ""
  echo "======================================================================"
  echo "DONE (--bundle-only mode). Skipped remote git push."
  echo "======================================================================"
  exit 0
fi

echo ""
echo "======================================================================"
echo "6. Pushing Latest Code & Tags to Both GitHub Repositories"
echo "======================================================================"

echo "-> [6a] Pushing to Original Personal GitHub Repo (${PERSONAL_REPO_HTTPS})..."
if git push origin main && git push origin "${CAPSTONE_TAG}" --force; then
  echo "   SUCCESS: Pushed main and ${CAPSTONE_TAG} to ${PERSONAL_REPO_HTTPS}"
else
  echo "   WARNING: Could not push to ${PERSONAL_REPO_HTTPS}. Check gh auth status."
fi

echo ""
echo "-> [6b] Pushing to Official FDE Capstone GitHub Org Repo (${FDE_ORG_REPO_HTTPS})..."
if command -v gh >/dev/null 2>&1; then
  if ! gh repo view cloud-ai-fde/clayberg-scouts-bsa-merit-badge-agent >/dev/null 2>&1; then
    echo "   Provisioning cloud-ai-fde/clayberg-scouts-bsa-merit-badge-agent via cloud-ai-fde/org-repo-management (go/new-fde-repo)..."
    gh issue create -R cloud-ai-fde/org-repo-management \
      --title "[PERSONAL REPO REQUEST]: scouts-bsa-merit-badge-agent" \
      --label "new-repo-request,personal-repo" \
      --body $'### LDAP\n\nclayberg\n\n### Desired Project Name\n\nscouts-bsa-merit-badge-agent\n\n### Project description\n\nScouts BSA Merit Badge Counselor Workbench — FDE Capstone Project (Google ADK + Vertex AI + Cloud Run)\n\n### Remove FDE team-wide permissions on the repo?\n\n- [ ] Request NO FDE team-wide permissions on repo.\n\n### Why do you need this repository to be unshared?\n\n_No response_' || true
    sleep 15
  fi
fi

if git push fde main --force && git push fde "${CAPSTONE_TAG}" --force; then
  echo "   SUCCESS: Pushed main and ${CAPSTONE_TAG} to ${FDE_ORG_REPO_HTTPS}"
else
  echo "   WARNING: Could not push to ${FDE_ORG_REPO_HTTPS}. Check gh auth status."
fi

echo ""
echo "======================================================================"
echo "7. Ready for go/capstone-app-staging and go/capstone-app Submission!"
echo "======================================================================"
echo "  1. Staging Web App    : https://goto.google.com/capstone-app-staging"
echo "  2. Production Web App : https://goto.google.com/capstone-app"
echo "  3. Git Bundle File    : ${BUNDLE_FILE} (${BUNDLE_SIZE})"
echo "  4. Annotated Git Tag  : ${CAPSTONE_TAG}"
echo "  5. Official GitHub URL: ${FDE_ORG_REPO_HTTPS}"
echo "  6. Google Slides Deck : https://docs.google.com/presentation/d/1YhwpfuubIGGrToktzhY8T7Xo5_GRdTMldUdyaS83G3E/edit"
echo "======================================================================"
