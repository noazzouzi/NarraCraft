"""Fresque pipeline — deterministic steps of the documentary pipeline.

Everything that is mechanical lives here: parsing, timing arithmetic, API
calls, asset sourcing, timeline building. Everything that requires judgement
lives in the Claude Code skills. See CLAUDE.md.
"""
__all__ = ["config", "project", "script_parser", "align", "timeline"]
