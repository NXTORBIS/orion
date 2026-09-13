"""API gateway and product entry points (project brief §31–32).

``build_system`` assembles backends, tools, retriever, memory and the orchestrator from a YAML
config; ``server`` exposes them over HTTP (OpenAI-compatible chat endpoint plus memory and
trace endpoints) and serves the chat page. Everything talks to ORION's own backends only.
"""
