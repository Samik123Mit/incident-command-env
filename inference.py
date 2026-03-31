"""
Baseline inference script for IncidentCommandEnv.

Uses the OpenAI API client to run an LLM agent against all three tasks.
Reads API credentials from environment variables.

Usage:
    API_BASE_URL=https://api.openai.com/v1 MODEL_NAME=gpt-4o OPENAI_API_KEY=... python inference.py
"""

from __future__ import annotations

import json
import os
import sys
import time

import requests
from openai import OpenAI

# ---------------------------------------------------------------------------
# Configuration from environment
# ---------------------------------------------------------------------------

API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME = os.environ.get("MODEL_NAME", "gpt-4o")
API_KEY = os.environ.get("OPENAI_API_KEY") or os.environ.get("HF_TOKEN", "")
ENV_URL = os.environ.get("ENV_URL", "http://localhost:8000")

MAX_STEPS = 25
TEMPERATURE = 0.2
MAX_TOKENS = 1024

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are an expert Site Reliability Engineer (SRE) responding to a production incident.

You must diagnose the root cause and resolve the incident by taking structured actions.

Available actions (respond with EXACTLY ONE JSON object per step):

1. Check all service statuses:
   {"action_type": "check_service_status"}

2. Query logs for a service:
   {"action_type": "query_logs", "target_service": "<service_name>"}

3. Check metrics for a service:
   {"action_type": "check_metrics", "target_service": "<service_name>"}

4. Identify root cause (include your analysis in reasoning):
   {"action_type": "identify_root_cause", "reasoning": "<detailed explanation of root cause, include service name, what went wrong, and evidence>"}

5. Restart a service:
   {"action_type": "restart_service", "target_service": "<service_name>"}

6. Rollback a deploy:
   {"action_type": "rollback_deploy", "target_service": "<service_name>"}

7. Scale a service:
   {"action_type": "scale_service", "target_service": "<service_name>", "parameters": {"replicas": <N>}}

8. Escalate to senior on-call:
   {"action_type": "escalate"}

9. Resolve the incident:
   {"action_type": "resolve_incident"}

STRATEGY:
- Start by checking service statuses to get an overview
- Query logs and metrics for suspicious services
- Identify the root cause with evidence BEFORE taking remediation
- Take the appropriate fix action (restart, rollback, scale)
- Resolve the incident

Respond with ONLY a valid JSON object. No explanation outside the JSON."""


def parse_action(text: str) -> dict:
    """Extract JSON action from model response."""
    text = text.strip()
    if text.startswith("{"):
        end = text.rfind("}") + 1
        text = text[:end]
    elif "{" in text:
        start = text.index("{")
        end = text.rfind("}") + 1
        text = text[start:end]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"action_type": "check_service_status"}


def env_reset(task_id: str) -> dict:
    resp = requests.post(f"{ENV_URL}/reset", json={"task_id": task_id}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def env_step(action: dict) -> dict:
    payload = action.copy()
    resp = requests.post(f"{ENV_URL}/step", json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def format_observation(obs: dict, step_num: int) -> str:
    """Format observation dict into readable text for the agent."""
    parts = []

    if step_num == 1:
        parts.append(f"INCIDENT: {obs.get('incident_summary', '')}")
        alerts = obs.get("active_alerts", [])
        if alerts:
            parts.append("\nACTIVE ALERTS:")
            for a in alerts:
                parts.append(f"  [{a['severity'].upper()}] {a['service']}: {a['title']} - {a['message']}")

    result = obs.get("last_action_result")
    error = obs.get("last_action_error")
    if result:
        parts.append(f"\nACTION RESULT: {result}")
    if error:
        parts.append(f"\nACTION ERROR: {error}")

    logs = obs.get("recent_logs", [])
    if logs:
        parts.append(f"\nLOGS ({len(logs)} entries):")
        for log in logs:
            parts.append(f"  [{log['timestamp']}] {log['level']} | {log['service']} | {log['message']}")

    metrics = obs.get("metrics", [])
    if metrics:
        parts.append(f"\nMETRICS ({len(metrics)} points):")
        for m in metrics:
            parts.append(f"  [{m['timestamp']}] {m['service']}.{m['metric_name']} = {m['value']} {m['unit']}")

    statuses = obs.get("service_statuses", [])
    if statuses:
        parts.append("\nSERVICE STATUSES:")
        for s in statuses:
            parts.append(
                f"  {s['name']}: {s['status']} | CPU: {s['cpu_percent']}% | "
                f"Mem: {s['memory_percent']}% | Replicas: {s['replicas_running']}/{s['replicas_desired']} | "
                f"Last deploy: {s['last_deploy']} ({s['last_deploy_sha']})"
            )

    history = obs.get("investigation_history", [])
    if history:
        parts.append(f"\nINVESTIGATION HISTORY: {'; '.join(history[-5:])}")

    parts.append("\nWhat action do you take next? Respond with a single JSON object.")
    return "\n".join(parts)


def run_task(client: OpenAI, task_id: str) -> float:
    print(f"\n{'='*60}")
    print(f"TASK: {task_id}")
    print(f"{'='*60}")

    obs = env_reset(task_id)
    print(f"Incident: {obs.get('incident_summary', '')}")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]

    for step_num in range(1, MAX_STEPS + 1):
        obs_text = format_observation(obs, step_num)
        messages.append({"role": "user", "content": obs_text})

        try:
            completion = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
                stream=False,
            )
            response_text = completion.choices[0].message.content or "{}"
        except Exception as exc:
            print(f"  Model error: {exc}")
            response_text = '{"action_type": "check_service_status"}'

        action = parse_action(response_text)
        action_type = action.get("action_type", "check_service_status")
        target = action.get("target_service", "")
        print(f"  Step {step_num}: {action_type}" + (f" -> {target}" if target else ""))

        messages.append({"role": "assistant", "content": response_text})

        result = env_step(action)
        obs = result.get("observation", {})
        reward = result.get("reward", obs.get("reward", 0.0))
        done = result.get("done", obs.get("done", False))

        action_result = obs.get("last_action_result", "")
        action_error = obs.get("last_action_error", "")
        print(f"         reward={reward:+.3f} | result={action_result or action_error}")

        if done:
            break

    grade = obs.get("metadata", {}).get("grade", 0.0)
    breakdown = obs.get("metadata", {}).get("grade_breakdown", {})
    feedback = obs.get("metadata", {}).get("grade_feedback", "")

    print(f"\n  FINAL SCORE: {grade}")
    print(f"  Breakdown: {json.dumps(breakdown, indent=2)}")
    print(f"  Feedback: {feedback}")
    return grade


def main():
    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)

    tasks = ["easy_oom_kill", "medium_connection_pool", "hard_cascading_failure"]
    scores = {}

    for task_id in tasks:
        score = run_task(client, task_id)
        scores[task_id] = score

    print(f"\n{'='*60}")
    print("FINAL RESULTS")
    print(f"{'='*60}")
    for tid, sc in scores.items():
        print(f"  {tid}: {sc:.3f}")
    avg = sum(scores.values()) / len(scores)
    print(f"\n  AVERAGE SCORE: {avg:.3f}")


if __name__ == "__main__":
    main()
