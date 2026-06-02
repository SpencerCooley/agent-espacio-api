"""
Artifact type registry.

A code-based dictionary defining all supported artifact types.
This is version-controlled and serves both AI agents and documentation.

Each artifact type defines:
- key: Machine identifier (used in the database type field)
- name: Human-readable name
- description: Short summary
- ai_instructions: Detailed guidance for AI agents on how to use this artifact
- content_schema: JSON schema describing the content structure
- example_content: A complete example of valid content
- icon: Icon identifier for the UI
- category: Broad category for grouping

To add a new artifact type, simply add a new entry to ARTIFACT_TYPES.
"""

from typing import Any

ARTIFACT_TYPES: dict[str, dict[str, Any]] = {
    "note": {
        "key": "note",
        "name": "Note",
        "description": "A rich text note with inline formatting, links, and embedded content.",
        "ai_instructions": (
            "Use this artifact to create structured text documents. "
            "The content follows the TipTap/ProseMirror document format: a JSON object with "
            "a 'type': 'doc' root containing an array of 'content' nodes. "
            "Each node has a 'type' (e.g., 'paragraph', 'heading') and optional 'content' array of text nodes. "
            "Text nodes can have 'marks' for formatting: bold, italic, link, code. "
            "Headings have 'attrs': {'level': 1|2|3}. "
            "Links have 'marks': [{'type': 'link', 'attrs': {'href': '...'}}]. "
            "When creating or editing a note, always produce valid TipTap JSON."
        ),
        "content_schema": {
            "type": "object",
            "required": ["content"],
            "properties": {
                "content": {
                    "type": "object",
                    "required": ["type", "content"],
                    "properties": {
                        "type": {"const": "doc"},
                        "content": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["type"],
                                "properties": {
                                    "type": {
                                        "type": "string",
                                        "enum": ["paragraph", "heading", "bulletList", "orderedList", "codeBlock", "blockquote"]
                                    },
                                    "attrs": {
                                        "type": "object",
                                        "description": "Node attributes, e.g. {'level': 1} for headings"
                                    },
                                    "content": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "required": ["type", "text"],
                                            "properties": {
                                                "type": {"const": "text"},
                                                "text": {"type": "string"},
                                                "marks": {
                                                    "type": "array",
                                                    "items": {
                                                        "type": "object",
                                                        "required": ["type"],
                                                        "properties": {
                                                            "type": {
                                                                "type": "string",
                                                                "enum": ["bold", "italic", "link", "code", "strike"]
                                                            },
                                                            "attrs": {
                                                                "type": "object",
                                                                "description": "Mark attributes, e.g. {'href': '...'} for links"
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "example_content": {
            "content": {
                "type": "doc",
                "content": [
                    {
                        "type": "heading",
                        "attrs": {"level": 1},
                        "content": [{"type": "text", "text": "Project Notes"}]
                    },
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "text": "Meeting with the team on "},
                            {"type": "text", "text": "Monday", "marks": [{"type": "bold"}]},
                            {"type": "text", "text": ". Check the "},
                            {
                                "type": "text",
                                "text": "design mockups",
                                "marks": [{"type": "link", "attrs": {"href": "https://figma.com/file/xyz"}}]
                            },
                            {"type": "text", "text": "."}
                        ]
                    },
                    {
                        "type": "bulletList",
                        "content": [
                            {
                                "type": "listItem",
                                "content": [
                                    {
                                        "type": "paragraph",
                                        "content": [{"type": "text", "text": "Finalize API contract"}]
                                    }
                                ]
                            },
                            {
                                "type": "listItem",
                                "content": [
                                    {
                                        "type": "paragraph",
                                        "content": [{"type": "text", "text": "Deploy staging environment"}]
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        },
        "icon": "note",
        "category": "productivity"
    }
}


def get_artifact_type(key: str) -> dict[str, Any] | None:
    """Get a single artifact type definition by key."""
    return ARTIFACT_TYPES.get(key)


def list_artifact_types() -> list[dict[str, Any]]:
    """List all artifact type definitions."""
    return list(ARTIFACT_TYPES.values())
