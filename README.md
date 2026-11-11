# GitHub Actions CI/CD — Learning PoC

A complete, end-to-end **Continuous Integration / Continuous Delivery / Deployment** proof of concept built with GitHub Actions.

**Purpose:** This repository is an onboarding learning artifact. The pipeline is designed to be *read and understood*, not just run. Every concept is explained here, and the workflow file (`.github/workflows/ci-cd.yml`) is heavily commented so both documents teach the same material.

---

## Table of Contents

1. [Concept Primer](#1-concept-primer)
2. [Lifecycle Diagram](#2-lifecycle-diagram)
3. [Annotated Workflow Walkthrough](#3-annotated-workflow-walkthrough)
4. [How to Design Workflows](#4-how-to-design-workflows)
5. [How to Manage Environments and Gates](#5-how-to-manage-environments-and-gates)
6. [How to Troubleshoot](#6-how-to-troubleshoot)
7. [Run It Yourself](#7-run-it-yourself)

---

## 1. Concept Primer

These are the core GitHub Actions building blocks. Each entry maps to where it appears in this repo.

| Concept | What it is | Where in this repo |
|---|---|---|
| **Workflow** | A YAML file in `.github/workflows/` that defines the entire automation. Triggered by events. | `.github/workflows/ci-cd.yml` |
| **Event / Trigger** | What causes the workflow to run: a push, a pull request, a schedule, manual click, etc. | `on: push` and `on: pull_request` at the top of `ci-cd.yml` |
| **Job** | A group of steps that run sequentially on one runner (VM). Jobs run in parallel by default; `needs:` creates order. | `lint`, `test`, `build`, `deploy-staging`, `deploy-production` |
| **Step** | A single command (`run:`) or reusable action (`uses:`) inside a job. Steps share the same runner filesystem. | Every `- name:` block inside a job |
| **Action** | A reusable, packaged unit of work published to the GitHub Marketplace. Pinned with `@v<N>`. | `actions/checkout@v5`, `actions/setup-python@v6`, `actions/upload-artifact@v4` |
| **Runner** | The virtual machine (or self-hosted server) that executes a job. `ubuntu-latest` = GitHub-hosted Ubuntu VM, free for public repos. | `runs-on: ubuntu-latest` in every job |
| **Artifact** | A file or directory produced by one job and shared with later jobs (or downloadable from the UI). NOT the same as a release asset. | `dist/` wheel uploaded by `build`, downloaded by both deploy jobs |
| **Environment** | A named deployment target (`staging`, `production`) with optional protection rules: required reviewers, wait timers, branch restrictions. | `environment: staging` and `environment: production` |
| **Secret** | An encrypted key-value stored in repo Settings → Secrets, injected as `${{ secrets.MY_SECRET }}`. Never visible in logs. | Not used in this PoC; the deploy is simulated. Real deploys would use `SSH_KEY`, `DEPLOY_TOKEN`, etc. |
| **Concurrency** | Prevents multiple runs of the same workflow/job from overlapping. `cancel-in-progress: true` cancels the older run when a new one starts. | Top-level `concurrency:` (CI) and per-job override for production (non-cancellable) |
| **Context** | Built-in variables provided by GitHub at runtime: `github.sha`, `github.actor`, `github.ref`, `github.event_name`, etc. | Used in the `record deployment` step and `if:` conditions |

---

## 2. Lifecycle Diagram

This shows the complete journey of a code change from commit to production.

```
                        ┌─────────────────────────────────────────────┐
  developer             │         GitHub Actions Runner                │
  ──────────            │                                              │
                        │  on: pull_request (PR opened)                │
  git push ──────────►  │  ┌──────────┐   ┌──────────┐               │
  (feature branch)      │  │  lint    │   │  test    │  ← CI stage    │
                        │  └──────────┘   └──────────┘               │
                        │    (parallel)                                │
                        │       │ both pass → PR gets green checks ✓  │
                        └───────┼─────────────────────────────────────┘
                                │
  git merge ──────────►         │  on: push (main)
  (to main)                     │
                                ▼
                        ┌──────────────┐
                        │   lint       │  CI stage
                        │   test       │  (parallel)
                        └──────┬───────┘
                               │ both pass
                               ▼
                        ┌──────────────┐
                        │   build      │  Build + Delivery stage
                        │  (wheel →    │  produces dist-<run_id>.whl
                        │   artifact)  │  uploaded to workflow artifacts
                        └──────┬───────┘
                               │
                               ▼
                        ┌──────────────┐
                        │ deploy-      │  Staging stage (automatic)
                        │ staging      │  installs wheel, runs healthcheck
                        │ environment  │
                        └──────┬───────┘
                               │ staging healthcheck passed
                               ▼
                        ┌──────────────┐
                        │ ⏸ APPROVAL  │  ← Required Reviewer gate
                        │   GATE       │    (configured in Environment settings)
                        └──────┬───────┘
                               │ reviewer clicks "Approve" in GitHub UI
                               ▼
                        ┌──────────────┐
                        │ deploy-      │  Production stage
                        │ production   │  installs wheel, runs healthcheck,
                        │ environment  │  records deployment metadata
                        └──────────────┘
                               │
                               ▼
                         Deployment history recorded in
                         repo → Deployments → production
```

**CI/CD stage mapping:**

| Stage | Definition | Jobs in this pipeline |
|---|---|---|
| **Continuous Integration (CI)** | Automatically validate every code change | `lint`, `test` |
| **Build** | Produce a versioned, reproducible artifact | `build` |
| **Continuous Delivery (CD)** | Make the artifact ready and deployable at any time | `build` (artifact upload) + `deploy-staging` |
| **Continuous Deployment** | Automatically deploy to staging; gate production | `deploy-staging` (auto), `deploy-production` (gated) |

---

## 3. Annotated Workflow Walkthrough

The full workflow lives in `.github/workflows/ci-cd.yml`. This section walks through each key part and explains *why* it is written that way.

### 3.1 — Name and Triggers

```yaml
name: CI / CD Pipeline

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
```

**Why:** The `name:` is what appears in the GitHub Actions UI — make it human-readable. The `on:` block controls what events fire the workflow. By restricting to `branches: [main]` we avoid running the pipeline on every experimental branch push, keeping runner usage low. Pull requests to `main` get CI (lint + test) so reviewers can see results before merging. Pushes to `main` (i.e. after merge) get the full pipeline including build and deploy.

### 3.2 — Concurrency

```yaml
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true
```

**Why:** Without this, pushing two commits quickly would queue two full pipeline runs that both do the same work. `cancel-in-progress: true` cancels the first run when the second starts — saving time and runner minutes. The `group` is scoped per-ref (branch), so `main` and `feature/x` can run concurrently without cancelling each other.

Note the production deploy job *overrides* this with its own concurrency block and `cancel-in-progress: false` — you never want to interrupt a production deployment midway through because a new commit arrived.

### 3.3 — The `needs:` Chain

```
lint ────────┐
             ├──► build ──► deploy-staging ──► deploy-production
test ────────┘
```

```yaml
build:
  needs: [lint, test]

deploy-staging:
  needs: build

deploy-production:
  needs: deploy-staging
```

**Why:** `needs:` creates a *dependency graph*. GitHub runs independent jobs in parallel (lint + test run at the same time), then waits for all dependencies before starting the next stage. If `lint` fails, `test` still runs (they're parallel) but `build` is skipped — there's no point building broken code.

### 3.4 — The `if:` Guard (Deploy Only on Push)

```yaml
build:
  if: github.event_name == 'push'
```

**Why:** On a pull request, `github.event_name == 'pull_request'`, so `build`, `deploy-staging`, and `deploy-production` are all **skipped** (shown as grey in the UI, not failed). This is intentional: PRs should only run CI checks, not deploy anything. This guard ensures the workflow file can handle both PR and push events without needing two separate workflow files.

### 3.5 — Artifact Upload/Download (v4)

```yaml
# In build job:
- uses: actions/upload-artifact@v4
  with:
    name: dist-${{ github.run_id }}   # unique per run
    path: dist/
    retention-days: 7

# In deploy jobs:
- uses: actions/download-artifact@v4
  with:
    name: dist-${{ github.run_id }}
    path: dist/
```

**Why v4 and unique names:**
- `upload-artifact@v3` and earlier were **permanently shut down on 2025-01-30**. Any workflow still referencing `@v3` will hard-fail with a clear error. Always use `@v4`.
- v4 artifacts are **immutable** — you cannot upload twice with the same name in one run (it errors). Appending `${{ github.run_id }}` guarantees uniqueness.
- Both upload and download must use the exact same `name:`. If you change one, change both.

### 3.6 — Environments

```yaml
deploy-staging:
  environment:
    name: staging
    url: https://github.com/mariodeleon/cicd-poc/actions

deploy-production:
  environment:
    name: production
    url: https://github.com/mariodeleon/cicd-poc/actions
```

**Why:** `environment:` links a job to a named deployment target. This does several things:
1. **Activates protection rules** — if `production` has Required Reviewers, the job pauses for approval before its first step runs.
2. **Creates a deployment record** — visible under repo → Deployments. Each run adds an entry with timestamp, actor, and status.
3. **Shows the `url:` in the UI** — a clickable link next to the job result.

The protection rules themselves are configured in Settings, not in YAML (see Section 5).

---

## 4. How to Design Workflows

### Adding a new job

1. Add a new top-level key under `jobs:`.
2. Give it a `runs-on:`, `steps:`, and optionally `needs:` (its prerequisites).
3. Add it to any other jobs' `needs:` lists if they should wait for it.

```yaml
jobs:
  security-scan:
    name: Security scan
    runs-on: ubuntu-latest
    needs: [lint, test]        # runs after CI but before build
    if: github.event_name == 'push'
    steps:
      - uses: actions/checkout@v5
      - run: pip install bandit && bandit -r src/
```

### Adding a new step

Steps are just `- name: ... run: ...` or `- name: ... uses: ...` inside a job's `steps:` list. They execute sequentially and share the same runner filesystem.

### Trigger options (common patterns)

```yaml
on:
  push:
    branches: [main]           # pushes to main only
  pull_request:
    branches: [main]           # PRs targeting main
  workflow_dispatch:           # manual trigger (adds a "Run workflow" button in UI)
  schedule:
    - cron: '0 6 * * 1'       # every Monday at 06:00 UTC
```

### Action version pinning rationale

Always pin to a major version tag (`@v4`, `@v5`). Never use `@main` or `@latest` in production workflows — they can break silently when the action author pushes a breaking change. For supply-chain security hardening (after the PoC), pin to the full SHA of the action commit instead of a tag.

### Build → Deploy artifact hand-off (the pattern)

The pattern used here — upload in `build`, download in `deploy-*` — is the standard way to share files between jobs. Key rules:
- The artifact name must be consistent (`dist-${{ github.run_id }}`).
- Upload once per name per run (immutability).
- Add `retention-days:` to control storage cost.

---

## 5. How to Manage Environments and Gates

### Creating environments (UI)

1. Go to **repo → Settings → Environments → New environment**
2. Create `staging` (no protection rules for now)
3. Create `production` and configure:
   - **Required reviewers** → add `mariodeleon` (or any collaborator)
   - **Deployment branches** → restrict to `main` only
   - Optional: **Wait timer** (e.g. 5 minutes after staging before production can run)

### Creating environments via `gh` CLI (what was done for this repo)

```bash
# Create environments
gh api repos/mariodeleon/cicd-poc/environments/staging -X PUT -f ""
gh api repos/mariodeleon/cicd-poc/environments/production -X PUT -f ""

# Add required reviewer (get your user ID first)
user_id=$(gh api users/mariodeleon --jq .id)
gh api repos/mariodeleon/cicd-poc/environments/production \
  -X PUT \
  --field "reviewers[][type]=User" \
  --field "reviewers[][id]=$user_id"
```

### How the approval gate works (step by step)

1. A push to `main` triggers the pipeline.
2. `lint` + `test` run → `build` runs → `deploy-staging` runs and passes.
3. `deploy-production` starts — but **before its first step**, GitHub sees the `environment: production` with Required Reviewers.
4. The run **pauses**. An email is sent to the required reviewers. The run UI shows a yellow "Waiting" badge with a **Review deployments** button.
5. A reviewer clicks **Review deployments → Approve and deploy**.
6. The production job resumes and completes.

### How to approve via `gh` CLI (without opening the browser)

```bash
# List pending approvals
gh run list --repo mariodeleon/cicd-poc --status waiting

# Get the run ID, then approve
gh run review <run-id> --approve --repo mariodeleon/cicd-poc
```

### Managing secrets

Secrets are stored encrypted at rest. They are **never** shown in logs (GitHub masks them automatically). To add one:

```bash
# Via gh CLI
gh secret set DEPLOY_SSH_KEY --body "$(cat ~/.ssh/id_cicd)" --repo mariodeleon/cicd-poc

# Reference in workflow:
# run: ssh user@host -i <(echo "${{ secrets.DEPLOY_SSH_KEY }}") ...
```

**Never** hardcode credentials in workflow YAML. Even in private repos — the workflow file is code and must be treated accordingly.

---

## 6. How to Troubleshoot

### Reading the Actions UI

1. Go to **repo → Actions tab** → select a workflow → select a run.
2. The run page shows the **job graph**: boxes for each job, colored by result (green = pass, red = fail, grey = skipped, yellow = waiting for approval).
3. Click a job → click a step to expand its log output.
4. Artifacts produced by the run appear in the **Artifacts** section at the bottom.
5. Deployments per environment appear in **repo → Deployments** (left sidebar).

### `gh` CLI triage cheat-sheet

```bash
# List recent runs (shows run ID, status, branch, duration)
gh run list --repo mariodeleon/cicd-poc

# Filter by workflow, branch, or status
gh run list --workflow=ci-cd.yml --branch main --status failure

# Show job summary for a specific run
gh run view <run-id>

# Show ONLY the failed steps' logs — fastest for triage
gh run view <run-id> --log-failed

# Show ALL logs for the entire run
gh run view <run-id> --log

# Watch a live run in your terminal (streams progress)
gh run watch <run-id>

# Re-run a failed run from the beginning
gh run rerun <run-id>

# Re-run only the failed jobs (skips successful jobs)
gh run rerun <run-id> --failed

# Download artifacts from a run to ./
gh run download <run-id>
```

### Worked failure example

**Scenario:** a test is deliberately broken (see the Operations section in the walkthrough) to demonstrate the triage cycle.

**What you see in the UI:** the `test` job turns red. Because `build` has `needs: [lint, test]`, it is automatically *skipped* (grey). Both deploy jobs are also skipped. The run is marked failed.

**Triage with CLI:**

```bash
# Step 1: find the failed run ID
gh run list --repo mariodeleon/cicd-poc --status failure --limit 3

# Step 2: read only the failed step logs
gh run view <run-id> --log-failed
# Output will show: FAILED tests/test_calc.py::TestAdd::test_add_integers
# AssertionError: assert 999 == 5

# Step 3: fix the code, commit, push
git add src/app/calc.py
git commit -m "fix: restore correct add() implementation"
git push

# Step 4: watch the recovery run
gh run watch   # picks up the newest run automatically
```

**Recovery evidence:** the new run shows all jobs green. The deployment history shows a new successful entry in `production`.

### Common failure signatures

| Symptom in logs | Root cause | Fix |
|---|---|---|
| `Error: This request has been automatically failed because it uses a deprecated version of actions/upload-artifact` | Using `@v3` or earlier | Change to `@v4` |
| `An artifact with this name already exists` | Uploading twice to the same artifact name | Use `name: dist-${{ github.run_id }}` or add `overwrite: true` |
| `Resource not accessible by integration` | Workflow is trying to write to a resource (environments, packages) but the token lacks the scope | Add the required permission to `permissions:` block or re-create the PAT with the right scope |
| `Context access might be invalid: secrets.MY_SECRET` | Secret name typo or secret not created in Settings | Check Settings → Secrets → Actions |
| Deploy job shown as grey/skipped on a PR | Working as intended — `if: github.event_name == 'push'` skips deploy on PRs | No action needed |
| Deploy job runs but health check fails | App is broken — the deploy intentionally surfaces this | Fix the code, re-run |
| `Deploy → Production` stuck on "Waiting" indefinitely | No required reviewer has approved | Click **Review deployments** in the run UI, or use `gh run review <id> --approve` |

---

## 7. Run It Yourself

### Prerequisites

- `git` and `gh` CLI installed
- Authenticated: `gh auth login --hostname github.com`

### Full walkthrough

```bash
# 1. Clone the repo
git clone https://github.com/mariodeleon/cicd-poc.git
cd cicd-poc

# 2. Create a feature branch and make a change
git checkout -b feature/my-change
# edit src/app/calc.py — add a new function, update a docstring, anything
git add .
git commit -m "feat: my change"
git push -u origin feature/my-change

# 3. Open a Pull Request
gh pr create --title "My change" --body "Testing CI pipeline" --base main

# 4. Watch CI run on the PR
gh run list --branch feature/my-change
gh run watch   # live progress in terminal
# Expected: lint ✓  test ✓  build → skipped (PR event)  deploy → skipped

# 5. Merge the PR (triggers full pipeline on main)
gh pr merge --squash --delete-branch

# 6. Watch the full pipeline
gh run list --branch main
gh run watch   # lint ✓ test ✓ build ✓ staging ✓ production → waiting for approval

# 7. Approve production deployment
gh run list --status waiting
gh run review <run-id> --approve

# 8. Confirm production succeeded
gh run view <run-id>
# Check deployment history:
gh api repos/mariodeleon/cicd-poc/deployments --jq '.[0] | {environment, sha, created_at}'

# 9. Download the produced artifact
gh run download <run-id>
ls dist/   # → cicd_poc-0.1.0-py3-none-any.whl

# 10. Trigger the deliberate failure demo
# Edit tests/test_calc.py — change `assert add(2, 3) == 5` to `== 999`
git checkout -b ops/deliberate-failure
git add . && git commit -m "test: deliberate failure for triage demo"
git push -u origin ops/deliberate-failure
gh pr create --title "Deliberate failure" --body "Demo triage" --base main
gh run list --branch ops/deliberate-failure
gh run view <run-id> --log-failed   # see the assertion error
# Fix it, push, watch the recovery
```

---

## Repository Structure

```
repo_cicd-poc/
├── .github/
│   └── workflows/
│       └── ci-cd.yml          # The pipeline — read alongside this README
├── src/
│   └── app/
│       ├── __init__.py
│       └── calc.py            # Tiny Python module: add, subtract, health
├── tests/
│   ├── __init__.py
│   └── test_calc.py           # pytest unit tests
├── scripts/
│   └── healthcheck.py         # Post-deploy smoke test
├── pyproject.toml             # Project metadata + build config
├── requirements-dev.txt       # Dev dependencies: ruff, pytest, build
└── README.md                  # This file
```

---

## Further Reading

- [GitHub Actions documentation](https://docs.github.com/en/actions)
- [Workflow syntax reference](https://docs.github.com/en/actions/writing-workflows/workflow-syntax-for-github-actions)
- [Using environments for deployment](https://docs.github.com/en/actions/deployment/targeting-different-environments/using-environments-for-deployment)
- [Security hardening (SHA pinning, OIDC)](https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions)
