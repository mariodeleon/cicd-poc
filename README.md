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

### How the concepts nest inside each other

```mermaid
graph TD
    REPO["📁 Repository"]
    WF["📄 Workflow\n.github/workflows/ci-cd.yml"]
    EVT["⚡ Event / Trigger\non: push · pull_request"]
    JOB["⚙️ Job\nlint · test · build · deploy-*"]
    STEP["▶️ Step\n- name: Run pytest\n  run: pytest -v"]
    ACT["📦 Action\nactions/checkout@v5\nactions/setup-python@v6"]
    RUN["🖥️ Runner\nubuntu-latest\n(GitHub-hosted VM)"]
    ENV["🌍 Environment\nstaging · production\n(protection rules)"]
    ART["🗜️ Artifact\ndist-<run_id>.whl\n(shared between jobs)"]
    SEC["🔒 Secret\nSETTINGS → Secrets\n${{ secrets.MY_KEY }}"]

    REPO --> WF
    EVT -->|"fires"| WF
    WF --> JOB
    JOB -->|"runs on"| RUN
    JOB --> STEP
    STEP -->|"uses"| ACT
    JOB -->|"links to"| ENV
    JOB -->|"uploads/downloads"| ART
    ENV -->|"injects"| SEC

    style REPO fill:#f0f0f0,stroke:#999
    style WF fill:#dbeafe,stroke:#3b82f6
    style EVT fill:#fef9c3,stroke:#ca8a04
    style JOB fill:#dcfce7,stroke:#16a34a
    style STEP fill:#f0fdf4,stroke:#86efac
    style ACT fill:#ede9fe,stroke:#7c3aed
    style RUN fill:#fff7ed,stroke:#ea580c
    style ENV fill:#fce7f3,stroke:#db2777
    style ART fill:#e0f2fe,stroke:#0284c7
    style SEC fill:#fef2f2,stroke:#dc2626
```

---

## 2. Lifecycle Diagram

### 2.1 — The full journey: from code change to production

```mermaid
flowchart TD
    DEV(["👨‍💻 Developer\npushes code"])

    subgraph PR_EVENT["on: pull_request — CI only"]
        direction LR
        L1["⚙️ lint\nruff check"]
        T1["⚙️ test\npytest"]
    end

    subgraph PUSH_EVENT["on: push to main — full pipeline"]
        direction TB
        L2["⚙️ lint\nruff check"]
        T2["⚙️ test\npytest"]
        B["📦 build\npython -m build\n→ upload artifact"]
        DS["🚀 deploy-staging\ndownload artifact\ninstall wheel\nhealthcheck ✓"]
        GATE{"⏸ Approval\nGate\nRequired Reviewer"}
        DP["🏭 deploy-production\ndownload artifact\ninstall wheel\nhealthcheck ✓\nrecord deployment"]
        HIST[("📋 Deployment\nHistory\nrepo → Deployments")]
    end

    GREEN["✅ PR checks\ngreen — safe to merge"]
    MERGE(["🔀 Merge to main"])

    DEV -->|"git push\nfeature branch"| PR_EVENT
    L1 & T1 --> GREEN
    GREEN --> MERGE
    MERGE -->|"triggers"| PUSH_EVENT

    L2 & T2 -->|"both pass"| B
    B -->|"artifact stored"| DS
    DS -->|"staging passed"| GATE
    GATE -->|"reviewer approves"| DP
    DP --> HIST

    style GATE fill:#fef9c3,stroke:#ca8a04,color:#000
    style GREEN fill:#dcfce7,stroke:#16a34a
    style HIST fill:#e0f2fe,stroke:#0284c7
```

### 2.2 — CI/CD stage definitions

```mermaid
graph LR
    subgraph CI["Continuous Integration"]
        L["lint\nruff check"]
        T["test\npytest"]
    end
    subgraph BUILD["Build"]
        B["build\npython -m build\nwheel artifact"]
    end
    subgraph CD["Continuous Delivery"]
        DS["deploy-staging\nauto on push to main"]
    end
    subgraph CDP["Continuous Deployment\n(Gated)"]
        DP["deploy-production\nrequires approval"]
    end

    CI --> BUILD --> CD --> CDP

    style CI fill:#dbeafe,stroke:#3b82f6
    style BUILD fill:#dcfce7,stroke:#16a34a
    style CD fill:#fff7ed,stroke:#ea580c
    style CDP fill:#fce7f3,stroke:#db2777
```

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

**Why:** The `name:` is what appears in the GitHub Actions UI — make it human-readable. The `on:` block controls what events fire the workflow. By restricting to `branches: [main]` we avoid running the pipeline on every experimental branch push, keeping runner usage low.

#### Event routing — what runs on each event type

```mermaid
flowchart LR
    PR(["pull_request\nto main"])
    PUSH(["push\nto main"])

    subgraph PR_JOBS["Jobs that run"]
        L_PR["lint ✓"]
        T_PR["test ✓"]
        B_PR["build ✗ skipped\nif: push only"]
        DS_PR["deploy-staging ✗ skipped"]
        DP_PR["deploy-production ✗ skipped"]
    end

    subgraph PUSH_JOBS["Jobs that run"]
        L_P["lint ✓"]
        T_P["test ✓"]
        B_P["build ✓"]
        DS_P["deploy-staging ✓"]
        DP_P["deploy-production ✓\n(after approval)"]
    end

    PR --> PR_JOBS
    PUSH --> PUSH_JOBS

    style B_PR fill:#f3f4f6,stroke:#9ca3af,color:#6b7280
    style DS_PR fill:#f3f4f6,stroke:#9ca3af,color:#6b7280
    style DP_PR fill:#f3f4f6,stroke:#9ca3af,color:#6b7280
    style DP_P fill:#fef9c3,stroke:#ca8a04
```

### 3.2 — Concurrency

```yaml
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true
```

**Why:** Without this, pushing two commits quickly would queue two full pipeline runs that do the same work. `cancel-in-progress: true` cancels the older run when the second starts — saving runner minutes.

#### How concurrency groups work

```mermaid
sequenceDiagram
    participant Dev as 👨‍💻 Developer
    participant GH as GitHub Actions
    participant Run1 as Run A (old commit)
    participant Run2 as Run B (new commit)

    Dev->>GH: git push (commit A)
    GH->>Run1: start run — group: ci-refs/heads/main
    Note over Run1: lint + test running...

    Dev->>GH: git push (commit B) — new push arrives
    GH->>Run1: ❌ cancel (cancel-in-progress: true)
    GH->>Run2: start run — group: ci-refs/heads/main
    Note over Run2: lint + test + build + deploy...

    Note over GH: Production deploy uses a SEPARATE group<br/>with cancel-in-progress: false<br/>→ never cancelled mid-deployment
```

### 3.3 — The `needs:` Chain

```yaml
build:
  needs: [lint, test]

deploy-staging:
  needs: build

deploy-production:
  needs: deploy-staging
```

**Why:** `needs:` creates a *dependency graph*. GitHub runs independent jobs in parallel (lint + test run at the same time), then waits for all dependencies before starting the next stage.

#### Job dependency graph

```mermaid
graph LR
    L["⚙️ lint"]
    T["⚙️ test"]
    B["📦 build"]
    DS["🚀 deploy-staging"]
    DP["🏭 deploy-production"]

    L -->|"must pass"| B
    T -->|"must pass"| B
    B -->|"artifact ready"| DS
    DS -->|"staging passed\n+ approval"| DP

    style L fill:#dcfce7,stroke:#16a34a
    style T fill:#dcfce7,stroke:#16a34a
    style B fill:#dbeafe,stroke:#3b82f6
    style DS fill:#fff7ed,stroke:#ea580c
    style DP fill:#fce7f3,stroke:#db2777
```

#### What happens when a job fails

```mermaid
flowchart TD
    L["lint ✓"]
    T["test ✗ FAILED"]
    B["build\n⬜ skipped\n(needs test)"]
    DS["deploy-staging\n⬜ skipped\n(needs build)"]
    DP["deploy-production\n⬜ skipped\n(needs staging)"]
    ERR["❌ Run marked FAILED\nonly failed jobs shown red\ndownstream shown grey"]

    L --> T
    T --> B
    B --> DS
    DS --> DP
    T --> ERR

    style T fill:#fef2f2,stroke:#dc2626
    style B fill:#f3f4f6,stroke:#9ca3af,color:#6b7280
    style DS fill:#f3f4f6,stroke:#9ca3af,color:#6b7280
    style DP fill:#f3f4f6,stroke:#9ca3af,color:#6b7280
    style ERR fill:#fef2f2,stroke:#dc2626
```

### 3.4 — The `if:` Guard (Deploy Only on Push)

```yaml
build:
  if: github.event_name == 'push'
```

**Why:** On a pull request `github.event_name == 'pull_request'`, so `build`, `deploy-staging`, and `deploy-production` are all **skipped** (shown grey, not failed). PRs should only run CI checks — not deploy anything. One workflow file handles both event types cleanly.

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

#### How the artifact flows between jobs

```mermaid
sequenceDiagram
    participant B as 📦 build job<br/>(Runner A)
    participant GH as GitHub<br/>Artifact Store
    participant DS as 🚀 deploy-staging<br/>(Runner B)
    participant DP as 🏭 deploy-production<br/>(Runner C)

    B->>B: python -m build → dist/*.whl
    B->>GH: upload-artifact@v4<br/>name: dist-43080463925
    Note over GH: stored for 7 days<br/>immutable — cannot upload twice

    GH-->>DS: download-artifact@v4<br/>name: dist-43080463925
    DS->>DS: pip install dist/*.whl<br/>healthcheck.py ✓

    GH-->>DP: download-artifact@v4<br/>name: dist-43080463925
    DP->>DP: pip install dist/*.whl<br/>healthcheck.py ✓<br/>record deployment
```

> **Critical:** `upload-artifact@v3` and earlier were **permanently shut down on 2025-01-30** and hard-fail. Always use `@v4`. Artifact names are immutable per run — use `${{ github.run_id }}` to guarantee uniqueness.

### 3.6 — Environments

```yaml
deploy-staging:
  environment:
    name: staging

deploy-production:
  environment:
    name: production    # ← triggers approval gate
```

#### What `environment:` activates

```mermaid
flowchart LR
    YAML["environment:\n  name: production"]

    subgraph Effects["What this declaration does"]
        R["🔒 Activates protection rules\n(required reviewers,\nwait timer, branch restriction)"]
        D["📋 Creates deployment record\nrepo → Deployments\n(timestamp, actor, status)"]
        U["🔗 Shows url: link\nin the run UI"]
        S["🔑 Scopes secrets\nenv-level secrets only\navailable to this job"]
    end

    YAML --> Effects

    style YAML fill:#fef9c3,stroke:#ca8a04
    style R fill:#fce7f3,stroke:#db2777
    style D fill:#e0f2fe,stroke:#0284c7
    style U fill:#f0fdf4,stroke:#16a34a
    style S fill:#fef2f2,stroke:#dc2626
```

The protection rules themselves are configured in **Settings → Environments**, not in YAML (see Section 5).

---

## 4. How to Design Workflows

### Adding a new job

1. Add a new top-level key under `jobs:`.
2. Give it `runs-on:`, `steps:`, and optionally `needs:` (its prerequisites).
3. Add it to any downstream jobs' `needs:` lists if they should wait for it.

#### Example: inserting a security scan between CI and build

```mermaid
graph LR
    L["lint"]
    T["test"]
    SEC["🛡️ security-scan\n(new job)\nneeds: lint, test"]
    B["build\nneeds: lint, test, security-scan"]
    DS["deploy-staging"]
    DP["deploy-production"]

    L --> SEC
    T --> SEC
    L --> B
    T --> B
    SEC --> B
    B --> DS
    DS --> DP

    style SEC fill:#ede9fe,stroke:#7c3aed
```

```yaml
jobs:
  security-scan:
    name: Security scan
    runs-on: ubuntu-latest
    needs: [lint, test]
    if: github.event_name == 'push'
    steps:
      - uses: actions/checkout@v5
      - run: pip install bandit && bandit -r src/
```

### Trigger options (common patterns)

```mermaid
mindmap
  root((on:))
    push
      branches: main
      branches: main, develop
      paths: src/**
    pull_request
      branches: main
      types: opened, synchronize
    workflow_dispatch
      Manual "Run workflow" button in UI
      Accepts input parameters
    schedule
      cron: 0 6 * * 1
      Every Monday 06:00 UTC
    workflow_call
      Called by another workflow
      Reusable workflow pattern
```

### Build → Deploy artifact hand-off (the pattern)

```mermaid
flowchart LR
    subgraph BUILD["build job"]
        PB["python -m build"]
        UA["upload-artifact@v4\nname: dist-RUNID\npath: dist/\nretention: 7d"]
        PB --> UA
    end

    subgraph STORE["GitHub Artifact Store\n(scoped to this run)"]
        ART[("dist-RUNID\n*.whl + *.tar.gz\nIMMUTABLE")]
    end

    subgraph STAGING["deploy-staging job"]
        DA1["download-artifact@v4\nname: dist-RUNID\npath: dist/"]
        INST1["pip install dist/*.whl\nhealthcheck.py"]
        DA1 --> INST1
    end

    subgraph PROD["deploy-production job"]
        DA2["download-artifact@v4\nname: dist-RUNID\npath: dist/"]
        INST2["pip install dist/*.whl\nhealthcheck.py"]
        DA2 --> INST2
    end

    UA -->|"stores"| ART
    ART -->|"fetched by"| DA1
    ART -->|"fetched by"| DA2

    style ART fill:#e0f2fe,stroke:#0284c7
    style STORE fill:#f0f9ff,stroke:#bae6fd
```

### Action version pinning rationale

```mermaid
graph TD
    A["actions/upload-artifact"] -->|"@v3"| V3["❌ DEAD\nShut down 2025-01-30\nHard-fails instantly"]
    A -->|"@v4"| V4["✅ Current stable\nUse this"]
    A -->|"@main"| MAIN["⚠️ Dangerous\nBreaks silently\non author push"]
    A -->|"@SHA (full hash)"| SHA["🔒 Most secure\nFor production\nPrevents supply-chain attacks"]

    style V3 fill:#fef2f2,stroke:#dc2626
    style V4 fill:#dcfce7,stroke:#16a34a
    style MAIN fill:#fef9c3,stroke:#ca8a04
    style SHA fill:#ede9fe,stroke:#7c3aed
```

---

## 5. How to Manage Environments and Gates

### Environment anatomy

```mermaid
graph TD
    ENV["🌍 Environment\n(staging or production)"]

    subgraph PROT["Protection Rules\n(Settings → Environments)"]
        RR["👥 Required Reviewers\nUp to 6 users/teams\nmust approve before job runs"]
        WT["⏱️ Wait Timer\nDelay N minutes\nafter trigger, before job runs"]
        BR["🌿 Deployment Branches\nOnly allowed branches\ncan deploy here"]
    end

    subgraph EFFECTS["What happens at runtime"]
        PAUSE["Job PAUSES before step 1\nRun shows yellow 'Waiting' badge\nEmail sent to reviewers"]
        APPROVE["Reviewer clicks\n'Review deployments → Approve'\nor: gh run review ID --approve"]
        RESUME["Job resumes\nsteps execute normally"]
        RECORD["Deployment record created\nrepo → Deployments\ntimestamp + actor + status"]
    end

    ENV --> PROT
    RR -->|"triggers"| PAUSE
    PAUSE --> APPROVE
    APPROVE --> RESUME
    RESUME --> RECORD

    style PAUSE fill:#fef9c3,stroke:#ca8a04
    style APPROVE fill:#dcfce7,stroke:#16a34a
    style RECORD fill:#e0f2fe,stroke:#0284c7
```

### Approval gate — step-by-step sequence

```mermaid
sequenceDiagram
    participant GH as GitHub Actions
    participant ENV as production Environment
    participant Email as 📧 Email
    participant Rev as 👤 Reviewer<br/>(mariodeleon)
    participant Job as 🏭 deploy-production job

    GH->>ENV: deploy-production reached production environment
    ENV->>GH: protection rule: required_reviewers active
    GH->>Job: ⏸ PAUSE before first step
    GH->>Email: notify required reviewers

    Note over GH: Run shows status: "waiting"<br/>gh run list --status waiting

    Rev->>GH: clicks "Review deployments → Approve"
    Note over Rev: or: gh run review RUN_ID --approve

    GH->>Job: ▶️ RESUME — execute steps
    Job->>Job: download artifact
    Job->>Job: install wheel
    Job->>Job: healthcheck ✓
    Job->>Job: record deployment
    Job->>GH: ✅ success
    GH->>ENV: deployment record created
```

### Creating environments via `gh` CLI

```bash
# Create environments
gh api repos/mariodeleon/cicd-poc/environments/staging -X PUT -f ""
gh api repos/mariodeleon/cicd-poc/environments/production -X PUT -f ""

# Add required reviewer (get your user ID first)
user_id=$(gh api users/mariodeleon --jq .id)
echo '{"wait_timer":0,"reviewers":[{"type":"User","id":'"$user_id"'}]}' | \
  gh api repos/mariodeleon/cicd-poc/environments/production -X PUT --input -
```

### Managing secrets

```mermaid
flowchart LR
    subgraph STORE["GitHub Secret Store\n(encrypted at rest)"]
        RS["📁 Repository secrets\nSettings → Secrets → Actions\nAvailable to ALL jobs"]
        ES["📁 Environment secrets\nSettings → Environments → production\nAvailable ONLY to jobs\ntargeting that environment"]
    end

    subgraph YAML["In workflow YAML"]
        REF["${{ secrets.DEPLOY_SSH_KEY }}\n${{ secrets.PROD_API_TOKEN }}"]
    end

    subgraph LOG["In runner logs"]
        MASK["*** (masked automatically)\nnever visible even with --log"]
    end

    RS -->|"injected as env var"| REF
    ES -->|"injected as env var"| REF
    REF -->|"if printed"| MASK

    style MASK fill:#fef2f2,stroke:#dc2626
    style ES fill:#fce7f3,stroke:#db2777
```

> **Never** hardcode credentials in workflow YAML. Even in private repos — the workflow file is code and must be treated accordingly.

---

## 6. How to Troubleshoot

### Triage decision tree

```mermaid
flowchart TD
    START(["❌ Pipeline failed\nWhat do I do?"])

    START --> Q1{"Which job\nturned red?"}

    Q1 -->|"lint"| LINT["ruff check output\nshows the offending line\nCheck: pyproject.toml ruff config\nFix: formatting or unused imports"]
    Q1 -->|"test"| TEST["pytest output\nshows FAILED test name\nand AssertionError details\nFix: the function or the test"]
    Q1 -->|"build"| BUILD["Check: pyproject.toml\nbuild-backend correct?\nsetuptools.build_meta ✓\nsetutools.backends.legacy ✗"]
    Q1 -->|"deploy-staging\nor deploy-production"| DEPLOY{"What does\nthe step say?"}

    DEPLOY -->|"artifact not found"| ART["name: mismatch between\nupload and download\nMust match exactly"]
    DEPLOY -->|"healthcheck failed"| HC["App is broken at runtime\nFix the code, not the pipeline"]
    DEPLOY -->|"permission error"| PERM["Token missing scope\nor environment protection\nnot configured correctly"]
    DEPLOY -->|"stuck on 'waiting'"| WAIT["No reviewer approved yet\ngh run list --status waiting\ngh run review ID --approve"]

    Q1 -->|"build/deploy are grey\nnot red"| SKIP["Working as intended:\n- On a PR: if: push only\n- Upstream job failed:\n  skipped automatically"]

    style START fill:#fef2f2,stroke:#dc2626
    style SKIP fill:#f3f4f6,stroke:#9ca3af
    style WAIT fill:#fef9c3,stroke:#ca8a04
```

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

### Worked failure example — full triage cycle

```mermaid
sequenceDiagram
    participant Dev as 👨‍💻 Developer
    participant GH as GitHub Actions
    participant CLI as gh CLI

    Dev->>GH: git push (broken test: assert 5 == 999)
    GH->>GH: lint ✓ → test ✗ FAILED
    GH->>GH: build ⬜ skipped · staging ⬜ skipped · prod ⬜ skipped
    GH-->>Dev: ❌ run failed

    Dev->>CLI: gh run list --status failure
    CLI-->>Dev: run ID: 43080864272

    Dev->>CLI: gh run view 43080864272 --log-failed
    CLI-->>Dev: "FAILED tests/test_calc.py::TestAdd::test_add_integers\nAssertionError: assert 5 == 999"

    Note over Dev: Root cause identified in seconds.<br/>No browser needed.

    Dev->>Dev: fix test: assert add(2,3) == 5
    Dev->>GH: git push (recovery commit)
    GH->>GH: lint ✓ → test ✓ → build ✓ → staging ✓ → prod ✓
    GH-->>Dev: ✅ run succeeded
```

### Common failure signatures

| Symptom in logs | Root cause | Fix |
|---|---|---|
| `This request has been automatically failed because it uses a deprecated version of actions/upload-artifact` | Using `@v3` or earlier — **shut down 2025-01-30** | Change to `@v4` |
| `An artifact with this name already exists` | Uploading twice with the same name in one run (v4 immutability) | Use `name: dist-${{ github.run_id }}` or add `overwrite: true` |
| `Resource not accessible by integration` | Token lacks required scope (e.g. `workflow`, `read:org`) | Re-authenticate with correct scopes |
| `Context access might be invalid: secrets.MY_SECRET` | Secret name typo or secret not created in Settings | Check Settings → Secrets → Actions |
| Deploy jobs shown grey on a PR | Working as intended — `if: github.event_name == 'push'` | No action needed |
| Deploy job runs but health check fails | App is broken at runtime | Fix the code, not the pipeline |
| `Deploy → Production` stuck on "Waiting" | No required reviewer has approved | Click **Review deployments** in the run UI, or `gh run review <id> --approve` |

---

## 7. Run It Yourself

### Prerequisites

- `git` and `gh` CLI installed
- Authenticated: `gh auth login --hostname github.com --scopes "repo,workflow,read:org"`

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

```mermaid
graph TD
    ROOT["📁 cicd-poc/"]

    GH["📁 .github/"]
    WF["📁 workflows/"]
    CICD["📄 ci-cd.yml\nThe pipeline\n5 jobs, heavily commented"]

    SRC["📁 src/"]
    APP["📁 app/"]
    INIT["📄 __init__.py\nMakes app a package"]
    CALC["📄 calc.py\nadd() subtract() health()\nThe app logic under test"]

    TESTS["📁 tests/"]
    TINIT["📄 __init__.py"]
    TCALC["📄 test_calc.py\n7 pytest unit tests"]

    SCRIPTS["📁 scripts/"]
    HC["📄 healthcheck.py\nPost-deploy smoke test\nExit 0=pass 1=fail"]

    PYPROJ["📄 pyproject.toml\nBuild config + ruff + pytest"]
    REQS["📄 requirements-dev.txt\nruff pytest build"]
    README["📄 README.md\nThis file — the learning guide"]
    GI["📄 .gitignore"]

    ROOT --> GH
    ROOT --> SRC
    ROOT --> TESTS
    ROOT --> SCRIPTS
    ROOT --> PYPROJ
    ROOT --> REQS
    ROOT --> README
    ROOT --> GI

    GH --> WF --> CICD
    SRC --> APP
    APP --> INIT
    APP --> CALC
    TESTS --> TINIT
    TESTS --> TCALC
    SCRIPTS --> HC

    style CICD fill:#dbeafe,stroke:#3b82f6
    style CALC fill:#dcfce7,stroke:#16a34a
    style TCALC fill:#dcfce7,stroke:#16a34a
    style HC fill:#fff7ed,stroke:#ea580c
    style README fill:#ede9fe,stroke:#7c3aed
```

---

## Further Reading

- [GitHub Actions documentation](https://docs.github.com/en/actions)
- [Workflow syntax reference](https://docs.github.com/en/actions/writing-workflows/workflow-syntax-for-github-actions)
- [Using environments for deployment](https://docs.github.com/en/actions/deployment/targeting-different-environments/using-environments-for-deployment)
- [Security hardening (SHA pinning, OIDC)](https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions)
