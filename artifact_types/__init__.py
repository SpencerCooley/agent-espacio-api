"""
Artifact types package.

Contains the artifact type registry and helpers for looking up
definitions used by AI agents and documentation.
"""

from artifact_types.registry import ARTIFACT_TYPES, get_artifact_type, list_artifact_types

__all__ = ["ARTIFACT_TYPES", "get_artifact_type", "list_artifact_types"]
