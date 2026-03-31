"""Incident Command Environment implementing the OpenEnv Environment interface."""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State

try:
    from ..models import IncidentAction, IncidentObservation
    from ..tasks import TaskScenario, get_task
except ImportError:
    from models import IncidentAction, IncidentObservation
    from tasks import TaskScenario, get_task


class IncidentCommandEnvironment(Environment):
    """OpenEnv-compliant environment for production incident response."""

    SUPPORTS_CONCURRENT_SESSIONS: bool = True

    def __init__(self):
        super().__init__()
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self._scenario: Optional[TaskScenario] = None
        self._task_id: str = "easy_oom_kill"
        self._done: bool = False
        self._cumulative_reward: float = 0.0

        # Tracking
        self._actions_taken: List[str] = []
        self._services_queried_logs: Set[str] = set()
        self._services_queried_metrics: Set[str] = set()
        self._services_checked_status: bool = False
        self._root_cause_identified: bool = False
        self._root_cause_correct: bool = False
        self._remediation_done: Set[str] = set()
        self._incident_resolved: bool = False

        # Observation buffers
        self._last_logs: List[Dict[str, Any]] = []
        self._last_metrics: List[Dict[str, Any]] = []
        self._last_action_result: Optional[str] = None
        self._last_action_error: Optional[str] = None
        self._investigation_history: List[str] = []
        self._services: Dict[str, Dict[str, Any]] = {}

    def reset(self, seed=None, episode_id=None, **kwargs) -> IncidentObservation:
        task_id = kwargs.get("task_id", "easy_oom_kill")
        self._task_id = task_id
        self._scenario = get_task(task_id)
        self._state = State(episode_id=episode_id or str(uuid4()), step_count=0)
        self._done = False
        self._cumulative_reward = 0.0

        self._actions_taken = []
        self._services_queried_logs = set()
        self._services_queried_metrics = set()
        self._services_checked_status = False
        self._root_cause_identified = False
        self._root_cause_correct = False
        self._remediation_done = set()
        self._incident_resolved = False

        self._last_logs = []
        self._last_metrics = []
        self._last_action_result = None
        self._last_action_error = None
        self._investigation_history = []
        self._services = copy.deepcopy(self._scenario.services)

        return IncidentObservation(
            step_number=0,
            active_alerts=self._scenario.initial_alerts,
            recent_logs=[],
            metrics=[],
            service_statuses=[],
            last_action_result="Incident assigned to you. Begin investigation.",
            last_action_error=None,
            investigation_history=[],
            incident_summary=self._scenario.incident_summary,
            done=False,
            reward=0.0,
            metadata={"task_id": task_id, "max_steps": self._scenario.max_steps},
        )

    def step(self, action: IncidentAction, timeout_s=None, **kwargs) -> IncidentObservation:
        if self._done:
            return self._build_observation(0.0, True)

        if self._scenario is None:
            raise RuntimeError("Call reset() before step().")

        self._state.step_count += 1
        self._last_logs = []
        self._last_metrics = []
        self._last_action_result = None
        self._last_action_error = None

        reward = self._execute_action(action)

        if self._state.step_count >= self._scenario.max_steps and not self._done:
            self._done = True
            self._last_action_result = f"Max steps ({self._scenario.max_steps}) reached. Incident unresolved."

        self._cumulative_reward += reward
        return self._build_observation(reward, self._done)

    @property
    def state(self) -> State:
        return self._state

    def grade(self) -> Dict[str, Any]:
        """Grade the current episode. Returns score 0.0-1.0 with breakdown."""
        if self._scenario is None:
            return {"value": 0.0, "breakdown": {}, "feedback": "No scenario loaded."}

        scores: Dict[str, float] = {}

        # Investigation thoroughness (25%)
        root_svc = self._scenario.root_cause_service
        total_services = len(self._scenario.services)
        log_score = 1.0 if root_svc in self._services_queried_logs else 0.0
        metric_score = 1.0 if root_svc in self._services_queried_metrics else 0.0
        status_score = 1.0 if self._services_checked_status else 0.0
        breadth = len(self._services_queried_logs | self._services_queried_metrics) / max(total_services, 1)
        investigation = log_score * 0.3 + metric_score * 0.2 + status_score * 0.1 + breadth * 0.4
        scores["investigation"] = round(min(investigation, 1.0), 3)

        # Root cause (30%)
        if self._root_cause_correct:
            scores["root_cause"] = 1.0
        elif self._root_cause_identified:
            scores["root_cause"] = 0.3
        else:
            scores["root_cause"] = 0.0

        # Remediation (30%)
        required = set(self._scenario.required_remediation)
        done = self._remediation_done & required
        scores["remediation"] = len(done) / len(required) if required else 0.0

        # Efficiency (15%)
        optimal_steps = len(self._scenario.optimal_action_sequence)
        if self._state.step_count <= optimal_steps:
            scores["efficiency"] = 1.0
        elif self._state.step_count <= optimal_steps * 1.5:
            scores["efficiency"] = 0.7
        elif self._state.step_count <= optimal_steps * 2:
            scores["efficiency"] = 0.4
        else:
            scores["efficiency"] = 0.1

        total = (
            scores["investigation"] * 0.25
            + scores["root_cause"] * 0.30
            + scores["remediation"] * 0.30
            + scores["efficiency"] * 0.15
        )

        if self._incident_resolved and self._root_cause_correct:
            total = min(total + 0.05, 1.0)

        total = round(total, 3)

        feedback_parts = []
        if scores["root_cause"] < 1.0:
            feedback_parts.append("Root cause not correctly identified.")
        if scores["remediation"] < 1.0:
            feedback_parts.append("Required remediation actions incomplete.")
        if scores["efficiency"] < 0.5:
            feedback_parts.append("Too many steps taken.")
        if not feedback_parts:
            feedback_parts.append("Excellent incident response!")

        return {"value": total, "breakdown": scores, "feedback": " ".join(feedback_parts)}

    # ------------------------------------------------------------------
    # Action execution
    # ------------------------------------------------------------------

    def _execute_action(self, action: IncidentAction) -> float:
        at = action.action_type
        target = action.target_service or ""
        params = action.parameters or {}
        step = self._state.step_count

        tag = at
        if target:
            tag += f":{target}"
        self._actions_taken.append(tag)

        reward = 0.0

        if at == "check_service_status":
            self._services_checked_status = True
            self._last_action_result = "Service status retrieved for all services."
            self._investigation_history.append(f"Step {step}: Checked all service statuses")
            reward = 0.03

        elif at == "query_logs":
            if not target:
                self._last_action_error = "target_service required for query_logs"
                return -0.02
            if target not in self._scenario.log_bank:
                self._last_action_error = f"No logs available for '{target}'"
                return -0.01
            self._last_logs = self._scenario.log_bank[target]
            self._services_queried_logs.add(target)
            self._last_action_result = f"Retrieved {len(self._last_logs)} log entries for {target}"
            self._investigation_history.append(f"Step {step}: Queried logs for {target}")
            reward = 0.05 if target == self._scenario.root_cause_service else 0.02

        elif at == "check_metrics":
            if not target:
                self._last_action_error = "target_service required for check_metrics"
                return -0.02
            if target not in self._scenario.metric_bank:
                self._last_action_error = f"No metrics available for '{target}'"
                return -0.01
            self._last_metrics = self._scenario.metric_bank[target]
            self._services_queried_metrics.add(target)
            self._last_action_result = f"Retrieved {len(self._last_metrics)} metric points for {target}"
            self._investigation_history.append(f"Step {step}: Checked metrics for {target}")
            reward = 0.05 if target == self._scenario.root_cause_service else 0.02

        elif at == "identify_root_cause":
            reasoning = (action.reasoning or "").lower()
            self._root_cause_identified = True
            matched = sum(1 for kw in self._scenario.root_cause_keywords if kw.lower() in reasoning)
            threshold = max(2, len(self._scenario.root_cause_keywords) // 2)
            if matched >= threshold:
                self._root_cause_correct = True
                self._last_action_result = "Root cause identification recorded. Analysis looks correct."
                self._investigation_history.append(f"Step {step}: Identified root cause (correct)")
                reward = 0.15
            else:
                self._last_action_result = "Root cause identification recorded. Analysis may be incomplete."
                self._investigation_history.append(f"Step {step}: Identified root cause (insufficient evidence)")
                reward = 0.03

        elif at == "restart_service":
            if not target:
                self._last_action_error = "target_service required"
                return -0.02
            if target not in self._services:
                self._last_action_error = f"Unknown service: {target}"
                return -0.02
            self._remediation_done.add("restart_service")
            if target == self._scenario.root_cause_service and "restart_service" in self._scenario.required_remediation:
                svc = self._services[target]
                svc["status"] = "healthy"
                svc["memory_percent"] = 35.0
                svc["cpu_percent"] = 15.0
                self._last_action_result = f"{target} restarted successfully. Service recovering."
                reward = 0.10
            else:
                self._last_action_result = f"{target} restarted, but this may not address the root cause."
                reward = 0.01
            self._investigation_history.append(f"Step {step}: Restarted {target}")

        elif at == "rollback_deploy":
            if not target:
                self._last_action_error = "target_service required"
                return -0.02
            if target not in self._services:
                self._last_action_error = f"Unknown service: {target}"
                return -0.02
            self._remediation_done.add("rollback_deploy")
            if target == self._scenario.root_cause_service and "rollback_deploy" in self._scenario.required_remediation:
                svc = self._services[target]
                svc["status"] = "healthy"
                svc["cpu_percent"] = 15.0
                svc["memory_percent"] = 40.0
                self._last_action_result = f"Deploy rolled back for {target}. Service recovering."
                reward = 0.15
            else:
                self._last_action_result = f"Deploy rolled back for {target}, but this may not address the root cause."
                reward = 0.01
            self._investigation_history.append(f"Step {step}: Rolled back deploy for {target}")

        elif at == "scale_service":
            if not target:
                self._last_action_error = "target_service required"
                return -0.02
            replicas = params.get("replicas", 5)
            self._remediation_done.add("scale_service")
            self._last_action_result = f"{target} scaling to {replicas} replicas."
            self._investigation_history.append(f"Step {step}: Scaled {target} to {replicas} replicas")
            reward = 0.01

        elif at == "escalate":
            self._last_action_result = "Incident escalated to senior on-call."
            self._investigation_history.append(f"Step {step}: Escalated incident")
            reward = 0.02

        elif at == "resolve_incident":
            self._incident_resolved = True
            self._done = True
            if self._root_cause_correct and self._remediation_done & set(self._scenario.required_remediation):
                self._last_action_result = "Incident resolved successfully! All checks pass."
                reward = 0.10
            elif self._root_cause_correct:
                self._last_action_result = "Incident marked resolved, but required remediation not completed."
                reward = 0.03
            else:
                self._last_action_result = "Incident marked resolved without proper root cause identification."
                reward = 0.01
            self._investigation_history.append(f"Step {step}: Resolved incident")
        else:
            self._last_action_error = f"Unknown action type: {at}"
            reward = -0.01

        return round(reward, 3)

    def _build_observation(self, reward: float, done: bool) -> IncidentObservation:
        grade = self.grade()
        return IncidentObservation(
            step_number=self._state.step_count,
            active_alerts=self._scenario.initial_alerts if self._scenario else [],
            recent_logs=self._last_logs,
            metrics=self._last_metrics,
            service_statuses=list(self._services.values()) if self._services_checked_status else [],
            last_action_result=self._last_action_result,
            last_action_error=self._last_action_error,
            investigation_history=self._investigation_history.copy(),
            incident_summary=self._scenario.incident_summary if self._scenario else "",
            done=done,
            reward=reward,
            metadata={
                "cumulative_reward": round(self._cumulative_reward, 3),
                "grade": grade["value"],
                "grade_breakdown": grade["breakdown"],
                "grade_feedback": grade["feedback"],
                "task_id": self._task_id,
            },
        )
