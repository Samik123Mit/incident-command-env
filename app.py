"""FastAPI application for the Incident Command Environment."""

try:
    from openenv.core.env_server.http_server import create_app
except Exception as e:
    raise ImportError(
        "openenv is required. Install with: uv sync"
    ) from e

try:
    from ..models import IncidentAction, IncidentObservation
    from .incident_command_environment import IncidentCommandEnvironment
except (ImportError, ModuleNotFoundError):
    from models import IncidentAction, IncidentObservation
    from server.incident_command_environment import IncidentCommandEnvironment


app = create_app(
    IncidentCommandEnvironment,
    IncidentAction,
    IncidentObservation,
    env_name="incident_command_env",
    max_concurrent_envs=1,
)


def main(host: str = "0.0.0.0", port: int = 8000):
    """Entry point for running the server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
