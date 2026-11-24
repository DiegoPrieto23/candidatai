"""CandidatAI."""

from importlib.metadata import version

# La de `pyproject.toml`: la API y el servidor MCP la leen de aquí para no escribirla a mano.
VERSION = version("candidatai")
