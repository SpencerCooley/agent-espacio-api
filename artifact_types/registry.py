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
        "description": "A rich text note with inline formatting, images, tables, and embedded content.",
        "ai_instructions": (
            "Use this artifact to create structured text documents. "
            "The content follows the TipTap/ProseMirror document format: a JSON object with "
            "a 'type': 'doc' root containing an array of 'content' nodes.\n\n"
            "TOP-LEVEL STRUCTURE:\n"
            "{\n"
            '  "type": "doc",\n'
            '  "content": [...nodes...],\n'
            '  "linked_asset_ids": ["uuid-1", "uuid-2"]  // optional, auto-managed\n'
            "}\n\n"
            "NODE TYPES:\n"
            "  - paragraph: Text paragraph. Optional attrs: { textAlign: 'left'|'center'|'right'|'justify' }\n"
            "  - heading: Section heading. attrs: { level: 1|2|3, textAlign: ... }\n"
            "  - bulletList: Unordered list. Contains listItem children.\n"
            "  - orderedList: Ordered list. Contains listItem children.\n"
            "  - taskList: Checklist/task list. Contains taskItem children. Uses checkbox-style toggles.\n"
            "  - taskItem: A single checklist item. attrs: { checked: true|false }. Contains paragraph children. Nested lists supported.\n"
            "  - listItem: A single list item. Contains paragraph children.\n"
            "  - codeBlock: Preformatted code block. Optional attrs: { language: '...' }.\n"
            "  - blockquote: Blockquote style.\n"
            "  - horizontalRule: Thematic break (<hr>). No content, no attrs.\n"
            "  - image: Embedded image. attrs: { src: '/assets/{id}/download', "
            "'data-asset-id': '{uuid}', alt: '...', 'data-thumb-size': 512, textAlign: 'left'|'center'|'right' }\n"
            "  - table: Table. Contains tableRow children.\n"
            "  - tableRow: Table row. Contains tableCell or tableHeader children.\n"
            "  - tableCell: Standard table cell. Contains paragraph children.\n"
            "  - tableHeader: Header cell. Contains paragraph children.\n\n"
            "TEXT MARKS (inline formatting):\n"
            "  - bold: **bold text**\n"
            "  - italic: *italic text*\n"
            "  - underline: <u>underlined text</u>\n"
            "  - strike: ~~strikethrough text~~\n"
            "  - link: Hyperlink. attrs: { href: '...', target: '_blank' }\n"
            "  - code: Inline code.\n"
            "  - textStyle: Text color. attrs: { color: '#rrggbb' }. Use to set foreground color of text.\n"
            "  - highlight: Text highlight / background color. attrs: { color: '#rrggbb' }. Use to highlight text with a background color.\n\n"
            "IMAGE USAGE:\n"
            "  Images must first be uploaded as assets (POST /assets/upload). "
            "After upload, embed them in the note by adding an image node with "
            "'data-asset-id' set to the asset's UUID. The 'src' should use the "
            "download URL: /assets/{assetId}/download?thumb=512. "
            "Images support textAlignment via the 'textAlign' attribute.\n\n"
            "LINKED ASSET IDS:\n"
            "  The editor automatically populates 'linked_asset_ids' at the top level of "
            "the doc by scanning for all image nodes with 'data-asset-id'. "
            "This list must be kept in sync with the images in the document. "
            "When creating a note via API, include 'linked_asset_ids' in the content JSON "
            "or it will be auto-populated from image nodes. "
            "The backend updates each asset's file_meta.linked_artifact_ids bidirectionally.\n\n"
            "TABLES:\n"
            "  Tables are built as: table > tableRow > tableCell/tableHeader > paragraph > text. "
            "The first row is typically tableHeader for column headers. "
            "Tables support insert/delete rows and columns.\n\n"
            "WHEN CREATING A NOTE VIA API:\n"
            "  POST /artifacts with body:\n"
            '  { "name": "...", "type": "note", "folder_id": "...",\n'
            '    "content": { "type": "doc", "content": [...], "linked_asset_ids": [...] } }\n\n'
            "WHEN UPDATING:\n"
            "  PUT /artifacts/{id} with partial content. "
            "The editor uses auto-save (1.5s debounce) so batch changes before saving."
        ),
        "content_schema": {
            "type": "object",
            "required": ["content"],
            "properties": {
                "content": {
                    "type": "object",
                    "required": ["type"],
                    "properties": {
                        "type": {"const": "doc"},
                        "linked_asset_ids": {
                            "type": "array",
                            "items": {"type": "string", "format": "uuid"},
                            "description": "UUIDs of assets used in this note (auto-managed)"
                        },
                        "content": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["type"],
                                "properties": {
                                    "type": {
                                        "type": "string",
                                        "enum": [
                                            "paragraph", "heading", "bulletList", "orderedList",
                                            "taskList", "taskItem",
                                            "listItem", "codeBlock", "blockquote",
                                            "horizontalRule", "image",
                                            "table", "tableRow", "tableCell", "tableHeader"
                                        ]
                                    },
                                    "attrs": {
                                        "type": "object",
                                        "description": "Node attributes vary by type. "
                                        "heading: {level: 1|2|3, textAlign?}. "
                                        "paragraph: {textAlign?}. "
                                        "image: {src, 'data-asset-id', alt?, 'data-thumb-size'?, textAlign?}. "
                                        "codeBlock: {language?}."
                                    },
                                    "content": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "required": ["type"],
                                            "properties": {
                                                "type": {
                                                    "type": "string",
                                                    "enum": [
                                                        "text", "paragraph", "heading",
                                                        "bulletList", "orderedList",
                                                        "taskList", "taskItem", "listItem",
                                                        "tableRow", "tableCell", "tableHeader"
                                                    ]
                                                },
                                                "text": {"type": "string", "description": "Text content (text nodes only)"},
                                                "marks": {
                                                    "type": "array",
                                                    "items": {
                                                        "type": "object",
                                                        "required": ["type"],
                                                        "properties": {
                                                            "type": {
                                                                "type": "string",
                                                                "enum": ["bold", "italic", "underline", "strike", "link", "code", "textStyle", "highlight"]
                                                            },
                                                            "attrs": {
                                                                "type": "object",
                                                                "description": "Mark attributes, e.g. {href: '...'} for links"
                                                            }
                                                        }
                                                    }
                                                },
                                                "attrs": {
                                                    "type": "object",
                                                    "description": "Attributes for nested nodes"
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
                        "type": "image",
                        "attrs": {
                            "src": "/assets/a1b2c3d4/download?thumb=512",
                            "data-asset-id": "a1b2c3d4-...",
                            "alt": "Architecture diagram",
                            "data-thumb-size": 512,
                            "textAlign": "center"
                        }
                    },
                    {
                        "type": "heading",
                        "attrs": {"level": 1, "textAlign": "left"},
                        "content": [{"type": "text", "text": "Project Notes"}]
                    },
                    {
                        "type": "paragraph",
                        "attrs": {"textAlign": "left"},
                        "content": [
                            {"type": "text", "text": "Meeting with the team on "},
                            {"type": "text", "text": "Monday", "marks": [{"type": "bold"}]},
                            {"type": "text", "text": ". Review the "},
                            {"type": "text", "text": "design mockups", "marks": [{"type": "link", "attrs": {"href": "https://figma.com/file/xyz"}}]},
                            {"type": "text", "text": "."}
                        ]
                    },
                    {
                        "type": "paragraph",
                        "attrs": {"textAlign": "left"},
                        "content": [
                            {"type": "text", "text": "Important: "},
                            {"type": "text", "text": "deadline approaching", "marks": [{"type": "highlight", "attrs": {"color": "#ffeb3b"}}]},
                            {"type": "text", "text": ". Use "},
                            {"type": "text", "text": "red text", "marks": [{"type": "textStyle", "attrs": {"color": "#e53935"}}]},
                            {"type": "text", "text": " for warnings."}
                        ]
                    },
                    {
                        "type": "heading",
                        "attrs": {"level": 2},
                        "content": [{"type": "text", "text": "Action Items"}]
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
                                        "content": [{"type": "text", "text": "Deploy staging environment", "marks": [{"type": "strike"}]}]
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        "type": "paragraph",
                        "attrs": {"textAlign": "center"},
                        "content": [{"type": "text", "text": "Progress Overview", "marks": [{"type": "bold"}, {"type": "underline"}]}]
                    },
                    {
                        "type": "table",
                        "content": [
                            {
                                "type": "tableRow",
                                "content": [
                                    {
                                        "type": "tableHeader",
                                        "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Task"}]}]
                                    },
                                    {
                                        "type": "tableHeader",
                                        "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Status"}]}]
                                    },
                                    {
                                        "type": "tableHeader",
                                        "content": [{"type": "paragraph", "content": [{"type": "text", "text": "ETA"}]}]
                                    }
                                ]
                            },
                            {
                                "type": "tableRow",
                                "content": [
                                    {
                                        "type": "tableCell",
                                        "content": [{"type": "paragraph", "content": [{"type": "text", "text": "API contract"}]}]
                                    },
                                    {
                                        "type": "tableCell",
                                        "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Done", "marks": [{"type": "bold"}]}]}]
                                    },
                                    {
                                        "type": "tableCell",
                                        "content": [{"type": "paragraph", "content": [{"type": "text", "text": "June 5"}]}]
                                    }
                                ]
                            },
                            {
                                "type": "tableRow",
                                "content": [
                                    {
                                        "type": "tableCell",
                                        "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Staging deploy"}]}]
                                    },
                                    {
                                        "type": "tableCell",
                                        "content": [{"type": "paragraph", "content": [{"type": "text", "text": "In progress", "marks": [{"type": "italic"}]}]}]
                                    },
                                    {
                                        "type": "tableCell",
                                        "content": [{"type": "paragraph", "content": [{"type": "text", "text": "June 7"}]}]
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        "type": "codeBlock",
                        "attrs": {"language": "python"},
                        "content": [{"type": "text", "text": "def hello():\n    print('Hello, world!')"}]
                    }
                ],
                "linked_asset_ids": ["a1b2c3d4-..."]
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
