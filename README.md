# OpsAgent-X

Autonomous multi-agent DevOps & reliability engineering platform. Watches
production signals, diagnoses root cause, drafts a patch, verifies it, and
only ships it after a human approves — with hard safety gates at every step
that can take an action.

```
Alert ──▶ Supervisor ──▶ LogAnalyst ─┐
                    └──▶ SecurityAgent ─┴──▶ CodeFixer ──▶ Verification
                                                                 │
                                              pass ──▶ Human-in-the-Loop ──▶ Deploy
                                              fail (retries left) ──▶ back to Supervisor
```

## Stack

| Layer            | Tech                                                              |
|-------------------|--------------------------------------------------------------------|
| Dashboard         | Next.js 15 (App Router) + Tailwind                                 |
| Orchestration     | LangGraph (state machine, conditional fan-out/fan-in, interrupts)  |
| LLM               | DeepSeek-V4 Flash via NVIDIA NIM (OpenAI-compatible API)            |
| State / cache     | Redis (LangGraph checkpoints + live event pub/sub)                 |
| Database          | MongoDB (incidents + audit trail)                                  |
| Infra             | Docker Compose (local) / Kubernetes manifests (production)         |

## File map

```
opsagent-x/
├── docker-compose.yml        # local dev: redis + mongo + backend + frontend
├── .env.example              # copy to .env and fill in
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py           # FastAPI app, CORS, graph lifecycle
│       ├── config.py         # all settings, env-driven
│       ├── db/                # redis_client.py, mongo_client.py
│       ├── llm/
│       │   └── deepseek_client.py   # NIM client + tool-calling loop
│       ├── agents/
│       │   ├── state.py      # shared LangGraph state shape
│       │   ├── prompts.py    # system prompts + safety rules
│       │   ├── supervisor.py, log_analyst.py, security_agent.py,
│       │   │   code_fixer.py, verification.py   # one node each
│       │   └── graph.py      # wires the graph + Redis checkpointer
│       ├── tools/             # k8s_tools.py, security_tools.py, git_tools.py
│       ├── api/                # routes_webhook.py, routes_incidents.py, routes_stream.py
│       └── models/schemas.py
│
├── frontend/
│   ├── app/page.tsx                    # incident list (dashboard home)
│   ├── app/incidents/[id]/page.tsx     # live execution view + approval
│   └── components/                     # AgentGraphView, ExecutionTree,
│                                        # TokenCostPanel, ApprovalPanel, …
│
├── k8s/                       # namespace, redis, mongo, backend (+ RBAC),
│                               # frontend, ingress
└── scripts/send_test_alert.sh # fire a fake incident end-to-end
```

## 1. Get an NVIDIA NIM key

DeepSeek-V4 Flash is served through NVIDIA NIM's OpenAI-compatible API.
Grab a free developer key at **build.nvidia.com/deepseek-ai/deepseek-v4-flash**
and put it in `.env` as `NVIDIA_API_KEY`. (NIM's free tier is for
prototyping — check NVIDIA's current terms before relying on it for
production traffic.)

## 2. Run it locally

```bash
cp .env.example .env        # fill in NVIDIA_API_KEY at minimum
git init repo-under-management   # or point GIT_REPO_PATH at a real repo

docker compose up --build
```

- Backend: http://localhost:8000 (docs at `/docs`, health at `/health`)
- Dashboard: http://localhost:3000

Fire a test incident:

```bash
./scripts/send_test_alert.sh
```

Open the dashboard — the incident will appear, and clicking into it shows
the agent graph lighting up live via Server-Sent Events as Supervisor →
LogAnalyst/SecurityAgent → CodeFixer → Verification run. When it reaches
Human-in-the-Loop, **Approve & deploy** resumes the paused graph.

## 3. How the pipeline maps to DeepSeek-V4 Flash's reasoning modes

NIM controls reasoning depth through `chat_template_kwargs`, not a
different model — `backend/app/llm/deepseek_client.py` wraps this into
three named modes used exactly as in the original design:

| Mode         | `chat_template_kwargs`                              | Used by                  |
|--------------|--------------------------------------------------------|---------------------------|
| `non_think`  | *(omitted)*                                            | Supervisor, SecurityAgent |
| `think_high` | `{"thinking": true, "reasoning_effort": "high"}`       | LogAnalyst                |
| `think_max`  | `{"thinking": true, "reasoning_effort": "max"}`        | CodeFixer                 |

## 4. Safety constraints (enforced in code, not just prompts)

- `k8s_fetch_logs` refuses any namespace not in `ALLOWED_NAMESPACES`.
- `code_patch` refuses any file path that resolves outside the repo root.
- Git tools never push or merge — CodeFixer only commits to a local
  feature branch.
- `deploy_node` is stubbed deliberately — wire it to your real ArgoCD
  sync only after you've watched the full flow in staging.
- The backend's Kubernetes ServiceAccount (`k8s/04-backend.yaml`) has an
  RBAC Role that can only `get`/`list` pods and pod logs in its own
  namespace — no write, delete, or exec permissions anywhere.
- `REQUIRE_HUMAN_APPROVAL=true` by default — a patch cannot reach `deploy`
  without an explicit human approval, even after Verification passes.
- `MAX_RETRIES` caps the Verification → Supervisor retry loop so a bad
  diagnosis can't loop forever; once exhausted it escalates straight to a
  human instead of giving up silently.

## 5. Connecting to a real Kubernetes cluster

By default, LogAnalyst's `k8s_fetch_logs` tool fails cleanly with "no kube
config" — fine for testing the pipeline's error-handling, but you'll want
real logs eventually. The easiest real cluster on Windows/Mac is Docker
Desktop's own built-in Kubernetes — no extra installs.

**1. Enable it.** Docker Desktop → Settings → Kubernetes → check "Enable
Kubernetes" → Apply & Restart. Takes a few minutes the first time. Confirm
with:
```powershell
kubectl get nodes
```
You should see a single `docker-desktop` node in `Ready` state.

**2. Create a real pod to investigate.** This repo includes
`local-k8s-test/checkout-api-pod.yaml` — a throwaway pod that deliberately
crash-loops so LogAnalyst has real logs to fetch, matching the test alert's
"crash-looping" story:
```powershell
kubectl apply -f local-k8s-test/checkout-api-pod.yaml
kubectl get pods -n staging   # should show CrashLoopBackOff after ~30s
```

**3. Export the kubeconfig for the backend container to use.** The
backend runs *inside* a container, so it can't see your host's
`~/.kube/config` directly, and Docker Desktop's cluster address
(`kubernetes.docker.internal`) only resolves on the host — containers need
`host.docker.internal` instead. From the `opsagent-x` root:
```powershell
kubectl config view --raw --minify --context docker-desktop | Out-File -Encoding utf8 kubeconfig-docker-desktop.yaml

$content = Get-Content kubeconfig-docker-desktop.yaml -Raw
$content = $content -replace 'server: https://kubernetes\.docker\.internal:6443', 'server: https://host.docker.internal:6443'
$content = $content -replace 'certificate-authority-data:.*', 'insecure-skip-tls-verify: true'
Set-Content -Encoding utf8 kubeconfig-docker-desktop.yaml -Value $content
```
`insecure-skip-tls-verify` is fine here because this is your own disposable
local cluster — never do this against a staging/production cluster.

**4. Point the backend at it.** In `.env`, set:
```
K8S_KUBECONFIG=/kubeconfig.yaml
```
`docker-compose.yml` already mounts `./kubeconfig-docker-desktop.yaml` to
that path — that's what the placeholder file in the repo is for.

**5. Rebuild and test:**
```powershell
docker compose up --build
```
Then fire a fresh test alert (same `Invoke-RestMethod` block from earlier
in this README). LogAnalyst's `k8s_fetch_logs` should now return the real
log lines from the `checkout-api` pod instead of a config error.

## 6. Deploying to your own Kubernetes cluster

```bash
kubectl apply -f k8s/00-namespace.yaml
cp k8s/01-secrets.example.yaml k8s/01-secrets.yaml   # fill in real values
kubectl apply -f k8s/01-secrets.yaml
kubectl apply -f k8s/02-redis.yaml -f k8s/03-mongo.yaml
kubectl apply -f k8s/04-backend.yaml -f k8s/05-frontend.yaml
kubectl apply -f k8s/06-ingress.yaml
```

Build and push your own images first and update the `image:` fields in
`04-backend.yaml` / `05-frontend.yaml` to point at your registry.

## 7. What's real vs. what to wire up for production

**Real, working code:** the LangGraph state machine (fan-out/fan-in,
retry loop, interrupt-based human approval, Redis checkpointing), the NIM
client and tool-calling loop, the K8s log/PromQL/Trivy/Git tools, the SSE
event stream, the dashboard, and the deploy step (branch merge +
`kubectl rollout restart`).

**To harden before production:**
- Replace the demo `emptyDir` Redis/Mongo in `k8s/` with PVC-backed
  StatefulSets or managed services (ElastiCache, Atlas).
- Wire a real CD system (ArgoCD/Flux) to watch `main` instead of the
  in-process rollout-restart call in `deploy_node` — then `deploy_node`
  just merges the branch and the CD system handles the rest.
- Add SonarQube or another static-analysis step alongside `pytest` in
  `verification_node`.
- Map your actual Alertmanager/Datadog/PagerDuty payload shape to
  `AlertWebhookPayload` in `models/schemas.py`.
- Set `REQUIRE_HUMAN_APPROVAL=false` only after you've built confidence in
  the pipeline's patch quality on your codebase. 