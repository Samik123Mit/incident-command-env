"""Data models for the Incident Command Environment."""

from typing import Any, Dict, List, Optional

from openenv.core.env_server.types import Action, Observation
from pydantic import Field


class IncidentAction(Action):
    """An action the SRE agent can take during incident response."""

    action_type: str = Field(
        ...,
        description=(
            "Type of action: check_service_status, query_logs, check_metrics, "
            "identify_root_cause, restart_service, rollback_deploy, "
            "scale_service, escalate, resolve_incident"
        ),
    )
    target_service: Optional[str] = Field(
        None, description="Service to act on (e.g. 'web-api', 'order-service')"
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Additional parameters"
    )
    reasoning: Optional[str] = Field(
        None, description="Agent reasoning for this action"
    )


class AlertInfo(Action):
    """A single alert from monitoring."""
    alert_id: str = ""
    severity: str = ""
    service: str = ""
    title: str = ""
    message: str = ""
    timestamp: str = ""
    is_firing: bool = True


class LogEntryInfo(Action):
    """A single log line."""
    timestamp: str = ""
    service: str = ""
    level: str = ""
    message: str = ""


class MetricPointInfo(Action):
    """A single metric data point."""
    timestamp: str = ""
    service: str = ""
    metric_name: str = ""
    value: float = 0.0
    unit: str = ""


class ServiceStatusInfo(Action):
    """Status of a single service."""
    name: str = ""
    status: str = ""
    uptime_seconds: int = 0
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    replicas_running: int = 0
    replicas_desired: int = 0
    last_deploy: str = ""
    last_deploy_sha: str = ""


class IncidentObservation(Observation):
    """What the agent observes at each step."""

    step_number: int = Field(default=0, description="Current step in the episode")
    active_alerts: List[Dict[str, Any]] = Field(
        default_factory=list, description="Currently firing alerts"
    )
    recent_logs: List[Dict[str, Any]] = Field(
        default_factory=list, description="Log entries from last query"
    )
    metrics: List[Dict[str, Any]] = Field(
        default_factory=list, description="Metrics from last query"
    )
    service_statuses: List[Dict[str, Any]] = Field(
        default_factory=list, description="Service health overview"
    )
    last_action_result: Optional[str] = Field(
        None, description="Result of the last action taken"
    )
    last_action_error: Optional[str] = Field(
        None, description="Error from the last action"
    )
    investigation_history: List[str] = Field(
        default_factory=list, description="Summary of actions taken"
    )
    incident_summary: str = Field(
        default="", description="Incident description from pager"
    )
