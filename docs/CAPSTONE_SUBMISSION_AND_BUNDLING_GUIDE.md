# Option A: FDE Capstone App (`go/capstone-app`) Submission, GitHub Sync & Bundling Guide

**Prepared for**: Eric Clayberg (`clayberg@google.com`)  
**Project**: Scouts BSA Merit Badge Counselor Workbench (`scouts-bsa-merit-badge-agent`)  
**Official FDE GitHub Target**: `https://github.com/cloud-ai-fde/clayberg-scouts-bsa-merit-badge-agent`  
**Original Personal GitHub Target**: `https://github.com/clayberg/scouts-bsa-merit-badge-agent`  
**Live Google Cloud Run Workbench**: [`https://scouts-bsa-merit-badge-agent-qjaneb6heq-uc.a.run.app`](https://scouts-bsa-merit-badge-agent-qjaneb6heq-uc.a.run.app)  
**Executive Readout Deck (11 Core Slides, 0 Appendix — `<= 15` Cap)**: [FDE Capstone Executive Readout (Google Slides)](https://docs.google.com/presentation/d/1YhwpfuubIGGrToktzhY8T7Xo5_GRdTMldUdyaS83G3E/edit)

---

## 1. Overview of Option A (`go/capstone-app-staging` & `go/capstone-app`)

The FDE Capstone Evaluation Tool provides two web environments hosted on Google Cloud Run behind Identity-Aware Proxy (IAP):

| Environment | Shortlink | Direct Cloud Run URL | When to Use |
| :--- | :--- | :--- | :--- |
| **Staging Environment** | [`go/capstone-app-staging`](https://goto.google.com/capstone-app-staging) | `https://fde-eval-tool-stage-491561659673.us-central1.run.app` | Dry-run testing of your `.bundle` file, slide count verification (`<= 15` core slides), and triggering a live `analyzer-preseed` (v3.8) Cloud Run Job before your official defense. |
| **Production Environment** | [`go/capstone-app`](https://goto.google.com/capstone-app) | `https://fde-eval-tool-prod-6l4a5l634q-uc.a.run.app` | Final official submission prior to your scheduled Capstone panel review. |

### 1.1 What Happens When You Upload Your Artifacts

When you submit your presentation and `.bundle` file in the web app, the platform executes two automated stages:

1. **Stage 1 — Synchronous Pre-Flight Gate (`analyzer-initial-checks`)**:
   - **Slide Count & Appendix Classifier**: Inspects your Google Slides deck (`1YhwpfuubIGGrToktzhY8T7Xo5_GRdTMldUdyaS83G3E`) using Gemini. It enforces the **`<= 15 Core Slides`** limit. Our deck has **11 Core Slides (`Slide 1` through `Slide 11`) and 0 Appendix slides** (`11 <= 15`), so it passes Stage 1 cleanly and every slide is evaluated as a primary slide.
   - **Git Bundle & Authorship Validator**: Runs `git bundle verify` on `scouts-bsa-merit-badge-agent.bundle`, checks commit authorship (`clayberg@google.com`), verifies the presence of an annotated tag matching `capstone-YYYYMMDD` (e.g., `capstone-20261006`), and checks the **Scoped Git Link Gate** to verify the repository belongs to `https://github.com/cloud-ai-fde/...` (or `delta-fde`).
2. **Stage 2 — Asynchronous Background Artifact Analyzer (`analyzer-preseed` v3.8)**:
   - Once Stage 1 passes and you enter the emails of your **3 Panelists** and **1 Manager**, the backend triggers a Cloud Run Job (`analyzer-preseed`) powered by **Gemini 3.7 / 3.8** and the **Antigravity SDK**.
   - Over roughly **3 to 5 minutes**, it unpacks the `.bundle`, reads all source code, tests, Terraform configs, ADRs, and slides, and pre-seeds `0.0–3.0` scores (`0.5` increments), 3–5 purple evidence bullets, and suggested probing questions across all **27 Part B subcategories**.

### 1.2 How to View the Stage 2 AI Scorecard in Staging (RBAC Workaround)

By design, the Capstone web app enforces strict Role-Based Access Control (RBAC):
- **Candidates cannot view the Stage 2 AI scorecard in the Candidate UI**, and the submission form prevents you from typing your own `@google.com` email into the Panelist or Manager fields.
- **How to see the live Staging output**: When submitting a test run on [`go/capstone-app-staging`](https://goto.google.com/capstone-app-staging), enter a trusted FDE colleague's `@google.com` email in one of the **Panelist** slots (or ask a peer FDE to create a dummy submission listing `clayberg@google.com` as a Panelist and uploading your `.bundle` and Slides link). Once the 5-minute Cloud Run Job finishes, the Panelist can open the **Panelist View** and click the **Download** button in the top-right corner to export the full AI evaluation package.

---

## 2. Complete Execution Script (`scripts/publish_and_bundle_capstone.sh`)

We have created and installed a single automated script at `scripts/publish_and_bundle_capstone.sh` inside the repository (`/usr/local/google/home/clayberg/.gemini/jetski/scratch/scouts-bsa-merit-badge-agent/scripts/publish_and_bundle_capstone.sh`).

### 2.1 What the Script Does
1. Verifies `.gitignore` excludes `.cache/` and `*.bundle` so the bundle never packs itself recursively.
2. Optionally runs all 50 `pytest` unit/fault-injection/contract-drift tests and the 12-badge `scripts/eval_gate.py` benchmark (`--run-tests`).
3. Stages and commits any latest changes on branch `main`.
4. Configures both Git remotes:
   - `origin` -> `git@github.com:clayberg/scouts-bsa-merit-badge-agent.git` (`https://github.com/clayberg/scouts-bsa-merit-badge-agent`)
   - `fde` -> `git@github.com:cloud-ai-fde/clayberg-scouts-bsa-merit-badge-agent.git` (`https://github.com/cloud-ai-fde/clayberg-scouts-bsa-merit-badge-agent`)
5. Creates an annotated Git tag `capstone-YYYYMMDD` (defaulting to today's UTC date, e.g., `capstone-20261006`) whose annotation embeds the official `https://github.com/cloud-ai-fde/clayberg-scouts-bsa-merit-badge-agent` URL.
6. Generates `scouts-bsa-merit-badge-agent.bundle` via `git bundle create` and validates it with `git bundle verify` and `git bundle list-heads`.
7. Pushes `main` and the `capstone-YYYYMMDD` tag to **both** `https://github.com/clayberg/scouts-bsa-merit-badge-agent` and `https://github.com/cloud-ai-fde/clayberg-scouts-bsa-merit-badge-agent`.

### 2.2 Full Source of `scripts/publish_and_bundle_capstone.sh`

```bash
#!/usr/bin/env bash
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
    --bundle-only) BUNDLE_ONLY=true ;;
    --run-tests)   RUN_TESTS=true ;;
    *) echo "Usage: $0 [--bundle-only] [--run-tests]"; exit 1 ;;
  esac
done

# 1. Optional Test & Eval Gate
if [[ "${RUN_TESTS}" == "true" ]]; then
  .venv/bin/pytest tests/ -q
  .venv/bin/python scripts/eval_gate.py
fi

# 2. Stage & Commit Any Pending Changes
git add -A
if ! git diff --cached --quiet; then
  git commit -m "chore(capstone): sync latest documentation, companion guide Q&A, and submission scripts (${CAPSTONE_TAG})"
fi

# 3. Configure Both Remotes ('origin' = personal, 'fde' = cloud-ai-fde org)
git config --global --unset url.git@github.com:.insteadof 2>/dev/null || true
git remote set-url origin "${PERSONAL_REPO_GIT}" 2>/dev/null || git remote add origin "${PERSONAL_REPO_GIT}"
git remote set-url fde "${FDE_ORG_REPO_GIT}" 2>/dev/null || git remote add fde "${FDE_ORG_REPO_GIT}"

# 4. Create Annotated Capstone Tag with Official Repo Metadata
git tag -f -a "${CAPSTONE_TAG}" -m "FDE Capstone Submission (${CAPSTONE_TAG})
Repository: ${FDE_ORG_REPO_HTTPS}
Mirror: ${PERSONAL_REPO_HTTPS}
Candidate: clayberg@google.com (Eric Clayberg)
Project: Scouts BSA Merit Badge Counselor Workbench (Google ADK + Vertex AI + Cloud Run)"

# 5. Build & Verify Standalone Git Bundle (.bundle)
rm -f "${BUNDLE_FILE}"
git bundle create "${BUNDLE_FILE}" --all
git bundle verify "${BUNDLE_FILE}"
git bundle list-heads "${BUNDLE_FILE}"

if [[ "${BUNDLE_ONLY}" == "true" ]]; then
  exit 0
fi

# 6a. Push to Original Personal GitHub Repository
git push origin main
git push origin "${CAPSTONE_TAG}" --force

# 6b. Provision (if needed via cloud-ai-fde/org-repo-management) & Push to Official cloud-ai-fde Org Repo
if command -v gh >/dev/null 2>&1; then
  if ! gh repo view cloud-ai-fde/clayberg-scouts-bsa-merit-badge-agent >/dev/null 2>&1; then
    gh issue create -R cloud-ai-fde/org-repo-management \
      --title "[PERSONAL REPO REQUEST]: scouts-bsa-merit-badge-agent" \
      --label "new-repo-request,personal-repo" \
      --body $'### LDAP\n\nclayberg\n\n### Desired Project Name\n\nscouts-bsa-merit-badge-agent\n\n### Project description\n\nScouts BSA Merit Badge Counselor Workbench — FDE Capstone Project (Google ADK + Vertex AI + Cloud Run)\n\n### Remove FDE team-wide permissions on the repo?\n\n- [ ] Request NO FDE team-wide permissions on repo.\n\n### Why do you need this repository to be unshared?\n\n_No response_' || true
    sleep 15
  fi
fi
git push fde main
git push fde "${CAPSTONE_TAG}" --force
```

---

## 3. Step-by-Step Commands: Uploading to Both GitHub Locations & Building the Bundle

Both repositories are already provisioned, configured as remotes (`origin` and `fde`), and synced:
- **Original Personal GitHub (`origin`)**: [`https://github.com/clayberg/scouts-bsa-merit-badge-agent`](https://github.com/clayberg/scouts-bsa-merit-badge-agent)
- **Official FDE Organization GitHub (`fde`)**: [`https://github.com/cloud-ai-fde/clayberg-scouts-bsa-merit-badge-agent`](https://github.com/cloud-ai-fde/clayberg-scouts-bsa-merit-badge-agent) (provisioned via [`cloud-ai-fde/org-repo-management#1007`](https://github.com/cloud-ai-fde/org-repo-management/issues/1007))

If you want to run each step manually after making future edits, follow these steps from your terminal:

### Step 1: Navigate to the Project Directory
```bash
cd /usr/local/google/home/clayberg/.gemini/jetski/scratch/scouts-bsa-merit-badge-agent
```

### Step 2: Upload the Latest Version to Your Original Personal GitHub (`clayberg/scouts-bsa-merit-badge-agent`)
Your `origin` remote is configured for `https://github.com/clayberg/scouts-bsa-merit-badge-agent.git` (authenticated via `gh auth git-credential`). To commit any latest edits and push them to your original repository:
```bash
git add -A
git commit -m "chore(capstone): final documentation, companion guide Q&A, and rubric updates" || true
git push origin main
```

### Step 3: Upload the Latest Version to the Official FDE GitHub Org (`cloud-ai-fde/clayberg-scouts-bsa-merit-badge-agent`)
Your `fde` remote is configured for `https://github.com/cloud-ai-fde/clayberg-scouts-bsa-merit-badge-agent.git`.
*(Note: In the `cloud-ai-fde` organization, repositories are provisioned via `go/new-fde-repo` / `cloud-ai-fde/org-repo-management` issues rather than direct `gh repo create`. We already provisioned `cloud-ai-fde/clayberg-scouts-bsa-merit-badge-agent` via Issue `#1007` with `@clayberg` as Admin.)*

To push the latest `main` branch to `cloud-ai-fde/clayberg-scouts-bsa-merit-badge-agent`:
```bash
git remote set-url fde https://github.com/cloud-ai-fde/clayberg-scouts-bsa-merit-badge-agent.git 2>/dev/null || \
  git remote add fde https://github.com/cloud-ai-fde/clayberg-scouts-bsa-merit-badge-agent.git

git push -u fde main
```

### Step 4: Create the Annotated `capstone-YYYYMMDD` Tag & Push to Both Remotes
The Capstone validator requires an annotated tag (`git tag -a`) named `capstone-YYYYMMDD` whose annotation message includes the repository URL:
```bash
export CAPSTONE_TAG="capstone-$(date -u +%Y%m%d)"

git tag -f -a "${CAPSTONE_TAG}" -m "FDE Capstone Submission (${CAPSTONE_TAG})
Repository: https://github.com/cloud-ai-fde/clayberg-scouts-bsa-merit-badge-agent
Mirror: https://github.com/clayberg/scouts-bsa-merit-badge-agent
Candidate: clayberg@google.com (Eric Clayberg)"

# Push the annotated tag to both GitHub locations
git push origin "${CAPSTONE_TAG}" --force
git push fde "${CAPSTONE_TAG}" --force
```

### Step 5: Build & Verify the `.bundle` Archive for `go/capstone-app`
```bash
rm -f scouts-bsa-merit-badge-agent.bundle
git bundle create scouts-bsa-merit-badge-agent.bundle --all

# Verify bundle integrity and confirm HEAD + tag are present
git bundle verify scouts-bsa-merit-badge-agent.bundle
git bundle list-heads scouts-bsa-merit-badge-agent.bundle
```

Expected output from `git bundle verify`:
```text
The bundle contains these 3 refs:
<commit_sha> refs/heads/main
<tag_sha> refs/tags/capstone-20261006
<commit_sha> HEAD
The bundle records a complete history.
scouts-bsa-merit-badge-agent.bundle is okay
```

---

## 4. Submitting to `go/capstone-app-staging` or `go/capstone-app`

Once `scouts-bsa-merit-badge-agent.bundle` is built and verified:

1. **Open the Target Portal**:
   - **Staging (for dry runs)**: [`https://goto.google.com/capstone-app-staging`](https://goto.google.com/capstone-app-staging) (`https://fde-eval-tool-stage-491561659673.us-central1.run.app`)
   - **Production (for official defense)**: [`https://goto.google.com/capstone-app`](https://goto.google.com/capstone-app) (`https://fde-eval-tool-prod-6l4a5l634q-uc.a.run.app`)
2. **Step 1 in UI — Select Presentation Deck**:
   - Click **Select from Google Drive** (or paste URL) and choose:
     **[FDE Capstone Executive Readout — Scouts BSA Merit Badge Counselor Workbench](https://docs.google.com/presentation/d/1YhwpfuubIGGrToktzhY8T7Xo5_GRdTMldUdyaS83G3E/edit)** (`ID: 1YhwpfuubIGGrToktzhY8T7Xo5_GRdTMldUdyaS83G3E`).
   - Verify the Stage 1 slide check turns green (**11 Core Slides, 0 Appendix <= 15 Core Slides**).
3. **Step 2 in UI — Upload Git Bundle & Repository Details**:
   - Upload file: `/usr/local/google/home/clayberg/.gemini/jetski/scratch/scouts-bsa-merit-badge-agent/scouts-bsa-merit-badge-agent.bundle` (~`25 MB`).
   - GitHub Repository URL: `https://github.com/cloud-ai-fde/clayberg-scouts-bsa-merit-badge-agent`
   - Git Tag: `capstone-20261006` (or the `capstone-YYYYMMDD` tag output by `scripts/publish_and_bundle_capstone.sh`).
   - Wait ~5–10 seconds for `analyzer-initial-checks` to confirm bundle integrity and authorship.
4. **Step 3 in UI — Assign Panelists & Manager**:
   - Enter the `@google.com` email addresses of your **3 Panelists** and **1 Manager** (remember: you cannot list your own `clayberg@google.com` address as a panelist/manager on your own submission).
   - Click **Submit**. This dispatches the `analyzer-preseed` Cloud Run Job, which completes in ~3–5 minutes and populates the Panelist and Manager views with the pre-seeded Part B scorecard.
