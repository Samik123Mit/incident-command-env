# IncidentCommandEnv

**A production incident response environment for training and evaluating AI agents on real SRE workflows.**

---

## Motivation

Site Reliability Engineers handle production incidents daily -- triaging alerts, correlating logs and metrics across services, diagnosing root causes, and executing remediation. This is one of the highest-stakes cognitive tasks in software engineering, yet no standardized RL environment exists for training AI agents to do it.

IncidentCommandEnv fills this gap with realistic multi-service incidents featuring noisy observability data, red-herring alerts, cascading failure chains, and time pressure.

---

## Action Space

| Action | Parameters | Description |
|--------|-----------|-------------|
| `check_service_status` | -- | Get health overview of all services |
| `query_logs` | `target_service` | Retrieve recent logs for a specific service |
| `check_metrics` | `target_service` | Retrieve metrics for a specific service |
| `identify_root_cause` | `reasoning` (text) | Declare the root cause with evidence |
| `restart_service` | `target_service` | Restart a service |
| `rollback_deploy` | `target_service` | Rollback the last deploy for a service |
| `scale_service` | `target_service`, `replicas` | Scale service replicas |
| `escalate` | -- | Escalate to senior on-call |
| `resolve_incident` | -- | Mark the incident as resolved |

## Observation Space

Each observation includes: active alerts, recent logs, metrics, service statuses, investigation history, and incident summary.

## Reward Design

| Component | Weight | Signal |
|-----------|--------|--------|
| Investigation thoroughness | 25% | Did the agent examine the right services? |
| Root cause identification | 30% | Was the root cause correctly identified? |
| Remediation correctness | 30% | Were the required fix actions taken? |
| Efficiency | 15% | Steps taken vs. optimal |
| Resolution bonus | +5% | Full diagnosis + fix + resolution |

---

## Tasks

### Task 1: OOM Kill (Easy) -- Max 15 steps
Web-api memory leak in session cache. Identify and restart.

### Task 2: Connection Pool Exhaustion (Medium) -- Max 20 steps
Bad deploy leaks DB connections. Trace through cross-service symptoms and rollback.

### Task 3: Cascading Failure (Hard) -- Max 25 steps
Auth-service deploy causes cascading timeouts. Search-service CPU alert is a red herring.

---

## Setup

```bash
pip install -e .
# or
uv sync

# Run server
uv run server
# or
python -m server.app

# Run inference
API_BASE_URL=https://api.openai.com/v1 MODEL_NAME=gpt-4o OPENAI_API_KEY=sk-... python inference.py
```

## Docker

```bash
docker build -t incident-command-env .
docker run -p 8000:8000 incident-command-env
```

## Baseline Scores (GPT-4o)

| Task | Score |
|------|-------|
| easy_oom_kill | 0.85 |
| medium_connection_pool | 0.72 |
| hard_cascading_failure | 0.55 |
| **Average** | **0.71** |

---

## Project Structure

```
incident-command-env/
├── openenv.yaml
├── pyproject.toml
├── uv.lock
├── Dockerfile
├── __init__.py
├── models.py
├── client.py
├── tasks/__init__.py
├── server/
│   ├── __init__.py
│   ├── app.py
│   ├── incident_command_environment.py
│   ├── Dockerfile
│   └── requirements.txt
├── inference.py
└── README.md
```

## License

MIT
