"""Incident Command Environment Client."""

from typing import Dict

from openenv.core import EnvClient
from openenv.core.client_types import StepResult
from openenv.core.env_server.types import State

from .models import IncidentAction, IncidentObservation


class IncidentCommandEnv(
    EnvClient[IncidentAction, IncidentObservation, State]
):
    """Client for the Incident Command Environment."""

    def _step_payload(self, action: IncidentAction) -> Dict:
        return action.model_dump()

    def _parse_result(self, payload: Dict) -> StepResult[IncidentObservation]:
        obs_data = payload.get("observation", {})
        observation = IncidentObservation(**obs_data)
        return StepResult(
            observation=observation,
            reward=payload.get("reward"),
            done=payload.get("done", False),
        )

    def _parse_state(self, payload: Dict) -> State:
        return State(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
        )
