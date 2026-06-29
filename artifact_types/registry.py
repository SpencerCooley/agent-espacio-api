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
            "WHEN TO USE:\n"
            "  - Meeting notes, project documentation, planning docs\n"
            "  - Any content that needs rich formatting (bold, lists, tables, images)\n"
            "  - Content that references workspace assets (images, files)\n\n"
            "WHEN NOT TO USE:\n"
            "  - Raw code files (use markdown assets instead)\n"
            "  - Structured data that needs schemas (use JSON assets instead)\n"
            "  - Process workflows (use workflow artifacts instead)\n\n"
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
            "COMMON PITFALLS:\n"
            "  1. Forgetting to upload images as assets BEFORE embedding them. "
            "     The image src must be a valid asset download URL.\n"
            "  2. Using 'text' nodes without wrapping them in a 'paragraph' node. "
            "     All text content must live inside a paragraph, heading, or table cell.\n"
            "  3. Missing the 'type': 'doc' root object. The content must be a full TipTap document.\n"
            "  4. Using 'taskList' without proper 'taskItem' children. Each taskItem must have a paragraph.\n\n"
            "WHEN CREATING A NOTE VIA API:\n"
            "  POST /artifacts with body:\n"
            '  { "name": "...", "type": "note", "folder_id": "...",\n'
            '    "content": { "type": "doc", "content": [...], "linked_asset_ids": [...] } }\n\n'
            "IMPORTANT: Do NOT include a 'description' field. Notes do not have descriptions.\n\n"
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
    },
    "workflow": {
        "key": "workflow",
        "name": "Workflow",
        "description": "Visual, collaborative process builder for repeatable agentic workflows. Nodes + edges represent actions, AI steps, human approvals, and decisions.",
        "ai_instructions": (
            "Use this artifact to design and execute repeatable agentic processes. "
            "A workflow is a directed graph of nodes (steps) connected by edges (transitions).\n\n"
            "WHEN TO USE:\n"
            "  - Multi-step processes that an AI agent will execute\n"
            "  - Processes that require human approval at certain points\n"
            "  - Documenting standard operating procedures for AI execution\n"
            "  - Creating reusable recipes that can be shared across projects\n\n"
            "WHEN NOT TO USE:\n"
            "  - Simple one-off tasks (just write the instructions directly)\n"
            "  - Complex branching logic with many conditions (use code/scripts)\n"
            "  - Real-time collaborative editing (use note artifacts instead)\n\n"
            "TOP-LEVEL STRUCTURE:\n"
            "{\n"
            '  "nodes": [...],\n'
            '  "edges": [...],\n'
            '  "viewport": { "x": 0, "y": 0, "zoom": 1 },  // optional, canvas pan/zoom state\n'
            '  "linked_workflow_ids": ["uuid-1"],  // optional, referenced sub-workflows\n'
            '  "linked_item_ids": ["uuid-2"]      // optional, linked folders/assets/artifacts\n'
            "}\n\n"
            "NODE STRUCTURE:\n"
            "Each node has:\n"
            "  - id: unique string (e.g., 'node-1')\n"
            "  - type: one of the node types below\n"
            "  - position: { x: number, y: number } for canvas layout\n"
            "  - data: { title, description?, prompt?, code?, parameters?, linked_item_id?, linked_item_type? }\n\n"
            "NODE TYPES:\n"
            "  - action: Regular process step. Title + description + optional code.\n"
            "  - ai_action: AI-generated step. Has a 'prompt' field for the AI prompt template.\n"
            "               Parameters may include model, temperature, output format, etc.\n"
            "  - human_in_loop: Pause for human review/approval. Parameters may include approval_required.\n"
            "  - espacio_action: Native Agent Espacio action. Parameters must include 'action' key:\n"
            "                    create_folder, create_artifact, upload_asset, update_artifact, share_folder, share_asset\n"
            "  - decision: Branching logic. Parameters must include 'conditions' array:\n"
            "              [{ label: 'Yes', target: 'node-id' }, { label: 'No', target: 'node-id' }]\n"
            "  - code: Small executable script. Has a 'code' field with the script text.\n"
            "  - data_reference: Link to existing workspace item. Has linked_item_id + linked_item_type.\n"
            "  - workflow_reference: Reference to another workflow. Has linked_item_id (the workflow ID).\n"
            "  - readme: Documentation node with no connection handles. Provides context for the workflow.\n"
            "           Has a 'description' field (supports multi-line text). No code, no parameters.\n"
            "           Used for prerequisites, explanations, and notes. Not executable.\n\n"
            "EDGE STRUCTURE:\n"
            "Each edge has:\n"
            "  - id: unique string (e.g., 'edge-1')\n"
            "  - source: source node id\n"
            "  - target: target node id\n"
            "  - label?: optional text label (e.g., 'Yes', 'No', 'Next')\n"
            "  - sourceHandle?: optional handle identifier for decision branches\n\n"
            "AI EXECUTION GUIDE:\n"
            "1. Read all 'readme' nodes first to understand prerequisites and context.\n"
            "2. Find the start node(s) — nodes with no incoming edges.\n"
            "3. Execute each node sequentially following edge directions.\n"
            "4. For 'ai_action' nodes: read the prompt template, substitute parameters, execute.\n"
            "5. For 'human_in_loop' nodes: pause execution and wait for human signal.\n"
            "6. For 'decision' nodes: evaluate conditions and follow the matching branch edge.\n"
            "7. For 'espacio_action' nodes: call the Agent Espacio API directly.\n"
            "8. For 'code' nodes: execute the script in a safe environment.\n"
            "9. For 'workflow_reference' nodes: recursively execute the referenced workflow.\n"
            "10. Skip 'readme' nodes during execution — they are documentation only.\n"
            "11. Continue until reaching a node with no outgoing edges (terminal).\n\n"
            "COMMON PITFALLS:\n"
            "  1. Uploading files to the wrong folder. Always check the folder roles in the workflow:\n"
            "     - stills/ = original images, animated/ = generated videos, parent/ = final output\n"
            "  2. Not reading readme nodes before execution. They contain prerequisites.\n"
            "  3. Forgetting to handle 'human_in_loop' nodes — you must wait for human confirmation.\n"
            "  4. Using decision nodes without proper sourceHandle values on edges.\n"
            "  5. Creating duplicate asset IDs when uploading files. Always check if the file exists first.\n"
            "  6. Not cleaning up temp files after execution. Always delete /tmp/ workspace after completion.\n"
            "  7. Using 'workflow_reference' without verifying the referenced workflow exists.\n\n"
            "NODE TYPE DETAILS:\n"
            "  - espacio_action: The 'action' parameter must be one of:\n"
            "      create_folder, create_artifact, upload_asset, update_artifact, share_folder, share_asset\n"
            "    Each action requires specific additional parameters.\n"
            "  - decision: The 'conditions' array defines branches. Each condition has:\n"
            "      { label: 'Yes', target: 'node-id', criteria: 'width > height' }\n"
            "    The edge from a decision node should have sourceHandle matching the label.\n"
            "  - readme: No connection handles, no edges. Place at the top of the workflow for context.\n"
            "    Use for: prerequisites, expected inputs, expected outputs, troubleshooting notes.\n\n"
            "WHEN CREATING A WORKFLOW VIA API:\n"
            "  POST /artifacts with body:\n"
            '  { "name": "...", "type": "workflow", "folder_id": "...",\n'
            '    "content": { "nodes": [...], "edges": [...] } }\n\n'
            "WHEN UPDATING:\n"
            "  PUT /artifacts/{id} with the full updated content.\n"
            "  The editor auto-saves (1.5s debounce) so batch changes before saving.\n\n"
            "SHARING WORKFLOWS:\n"
            "  Workflows can be made public via is_public=true. This generates a public_magic_id\n"
            "  that allows anyone to view the workflow without authentication.\n"
            "  Public workflows are read-only."
        ),
        "content_schema": {
            "type": "object",
            "required": ["nodes", "edges"],
            "properties": {
                "nodes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["id", "type", "position", "data"],
                        "properties": {
                            "id": {"type": "string", "description": "Unique node identifier"},
                            "type": {
                                "type": "string",
                                "enum": ["action", "ai_action", "human_in_loop", "espacio_action", "decision", "code", "data_reference", "workflow_reference", "readme"],
                                "description": "Node type"
                            },
                            "position": {
                                "type": "object",
                                "required": ["x", "y"],
                                "properties": {
                                    "x": {"type": "number"},
                                    "y": {"type": "number"}
                                }
                            },
                            "data": {
                                "type": "object",
                                "required": ["title"],
                                "properties": {
                                    "title": {"type": "string", "description": "Node display title"},
                                    "description": {"type": "string", "description": "Optional detailed description"},
                                    "prompt": {"type": "string", "description": "AI prompt template (for ai_action nodes)"},
                                    "code": {"type": "string", "description": "Script code (for code nodes)"},
                                    "linked_item_id": {"type": "string", "format": "uuid", "description": "Linked workspace item ID"},
                                    "linked_item_type": {"type": "string", "enum": ["folder", "asset", "artifact"], "description": "Type of linked item"},
                                    "parameters": {
                                        "type": "object",
                                        "description": "Type-specific configuration parameters"
                                    }
                                }
                            }
                        }
                    }
                },
                "edges": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["id", "source", "target"],
                        "properties": {
                            "id": {"type": "string", "description": "Unique edge identifier"},
                            "source": {"type": "string", "description": "Source node ID"},
                            "target": {"type": "string", "description": "Target node ID"},
                            "label": {"type": "string", "description": "Optional edge label text"},
                            "sourceHandle": {"type": "string", "description": "Optional source handle for decision branches"}
                        }
                    }
                },
                "viewport": {
                    "type": "object",
                    "required": ["x", "y", "zoom"],
                    "properties": {
                        "x": {"type": "number", "description": "Canvas pan X offset"},
                        "y": {"type": "number", "description": "Canvas pan Y offset"},
                        "zoom": {"type": "number", "description": "Canvas zoom level (1 = 100%)"}
                    },
                    "description": "Saved canvas pan/zoom state for consistent viewing"
                },
                "linked_workflow_ids": {
                    "type": "array",
                    "items": {"type": "string", "format": "uuid"},
                    "description": "UUIDs of referenced sub-workflows"
                },
                "linked_item_ids": {
                    "type": "array",
                    "items": {"type": "string", "format": "uuid"},
                    "description": "UUIDs of linked workspace items"
                },
                "is_public": {
                    "type": "boolean",
                    "default": False,
                    "description": "Whether this workflow is publicly viewable"
                },
                "public_magic_id": {
                    "type": "string",
                    "format": "uuid",
                    "description": "Auto-generated public access token (set when is_public=true)"
                }
            }
        },
        "example_content": {
            "content": {
                "viewport": {"x": 0, "y": 0, "zoom": 1},
                "nodes": [
                    {
                        "id": "node-readme",
                        "type": "readme",
                        "position": {"x": 100, "y": -50},
                        "data": {
                            "title": "Readme",
                            "description": "This workflow generates ad variations from product photos.\\n\\nPrerequisites:\\n- Product photos in the workspace\\n- REPLICATE_API_TOKEN set\\n\\nOutput: 5 AI-generated variations in the variations/ folder",
                            "parameters": {}
                        }
                    },
                    {
                        "id": "node-1",
                        "type": "action",
                        "position": {"x": 100, "y": 100},
                        "data": {
                            "title": "Upload Product Photos",
                            "description": "Upload raw product photos to the workspace",
                            "parameters": {}
                        }
                    },
                    {
                        "id": "node-2",
                        "type": "ai_action",
                        "position": {"x": 350, "y": 100},
                        "data": {
                            "title": "Generate Variations",
                            "description": "Use AI to generate ad variations",
                            "prompt": "Generate 5 lifestyle variations of the product photo with different backgrounds and lighting.",
                            "parameters": {
                                "model": "wan-video/wan-2.7-i2v",
                                "num_variations": 5
                            }
                        }
                    },
                    {
                        "id": "node-3",
                        "type": "human_in_loop",
                        "position": {"x": 600, "y": 100},
                        "data": {
                            "title": "Review & Approve",
                            "description": "Human reviews the generated variations",
                            "parameters": {
                                "approval_required": True
                            }
                        }
                    },
                    {
                        "id": "node-4",
                        "type": "espacio_action",
                        "position": {"x": 850, "y": 100},
                        "data": {
                            "title": "Create Public Gallery",
                            "description": "Create a folder and share the approved images",
                            "parameters": {
                                "action": "create_folder",
                                "folder_name": "Approved Ad Variations"
                            }
                        }
                    }
                ],
                "edges": [
                    {
                        "id": "edge-1",
                        "source": "node-1",
                        "target": "node-2",
                        "label": "photos uploaded"
                    },
                    {
                        "id": "edge-2",
                        "source": "node-2",
                        "target": "node-3",
                        "label": "variations generated"
                    },
                    {
                        "id": "edge-3",
                        "source": "node-3",
                        "target": "node-4",
                        "label": "approved"
                    }
                ]
            }
        },
        "icon": "account_tree",
        "category": "orchestration"
    },
    "map": {
        "key": "map",
        "name": "Map",
        "description": "An interactive geospatial map with positionable viewport, zoom, and deck.gl data visualization support.",
        "ai_instructions": (
            "Use this artifact to create and save interactive maps. "
            "The map stores viewport state (center lat/lng, zoom, pitch, bearing, and bounds) so that "
            "when a human opens it later, the map is exactly where they left it.\n\n"
            "WHEN TO USE:\n"
            "  - Geospatial data visualization (points, polygons, heatmaps)\n"
            "  - Location-based project planning or documentation\n"
            "  - Creating map-based reports or dashboards\n\n"
            "WHEN NOT TO USE:\n"
            "  - Static images of maps (use image assets instead)\n"
            "  - Tabular location data without spatial visualization (use note or JSON asset)\n\n"
            "TOP-LEVEL STRUCTURE:\n"
            "{\n"
            '  "viewport": {\n'
            '    "latitude": 20.0,      // Center latitude (-90 to 90)\n'
            '    "longitude": 0.0,     // Center longitude (-180 to 180)\n'
            '    "zoom": 2.0,          // Zoom level (0 = world, 20 = building)\n'
            '    "pitch": 0.0,         // Tilt angle in degrees (0 = top-down)\n'
            '    "bearing": 0.0,       // Rotation in degrees (0 = north up)\n'
            '    "bounds": {\n'
            '      "north": 85.0,      // Bounding box north latitude\n'
            '      "south": -85.0,     // Bounding box south latitude\n'
            '      "east": 180.0,      // Bounding box east longitude\n'
            '      "west": -180.0      // Bounding box west longitude\n'
            '    }\n'
            '  },\n'
            '  "style": "carto-voyager",      // Map tile style (carto-voyager, osm, dark-matter, google-satellite)\n'
            '  "layers": [],                  // Array of deck.gl layers (optional, future feature)\n'
            '  "geojson": {                   // GeoJSON FeatureCollection for user-drawn geometries\n'
            '    "type": "FeatureCollection",\n'
            '    "features": [                  // Array of Point, LineString, MultiLineString, Polygon, MultiPolygon features\n'
            '      {\n'
            '        "type": "Feature",\n'
            '        "id": "feat-123",\n'
            '        "geometry": { "type": "Point", "coordinates": [lng, lat] },\n'
            '        "properties": {\n'
            '          "name": "Waypoint 1",\n'
            '          "description": "Landing zone",\n'
            '          "style": { "color": "#1976d2", "fillOpacity": 0.3, "strokeWidth": 2 },\n'
            '          "associations": [\n'
            '            { "type": "artifact", "id": "uuid", "name": "Flight Plan", "kind": "note" }\n'
            '          ],\n'
            '          "metadata": { "altitude": "100m", "restricted": true }\n'
            '        }\n'
            '      }\n'
            '    ]\n'
            '  }\n'
            "}\n\n"
            "VIEWPORT FIELDS:\n"
            "  - latitude: Center latitude of the map view\n"
            "  - longitude: Center longitude of the map view\n"
            "  - zoom: Zoom level (0 = world, 10 = city, 15 = street, 20 = building)\n"
            "  - pitch: Camera tilt in degrees (0 = straight down, 60 = oblique)\n"
            "  - bearing: Camera rotation in degrees (0 = north at top)\n"
            "  - bounds: Geographic bounding box (north, south, east, west) as float values\n\n"
            "FEATURE PROPERTIES:\n"
            "  - name: Display name for the geometry (e.g., 'Waypoint 1', 'Prohibited Area')\n"
            "  - description: Optional description text\n"
            "  - style.color: Hex color string for the feature\n"
            "  - style.fillOpacity: Fill opacity (0-1) for polygons\n"
            "  - style.strokeWidth: Line width in pixels\n"
            "  - associations: Array of linked workspace items (artifacts/assets)\n"
            "  - metadata: Arbitrary JSON object for custom data\n\n"
            "WHEN CREATING A MAP VIA API:\n"
            "  POST /artifacts with body:\n"
            '  { "name": "San Francisco", "type": "map", "folder_id": "...",\n'
            '    "content": { "viewport": {...}, "style": "carto-voyager", "geojson": { "type": "FeatureCollection", "features": [] } } }\n\n'
            "WHEN UPDATING:\n"
            "  PUT /artifacts/{id} with updated viewport or geojson. The UI auto-saves viewport changes (1.5s debounce).\n\n"
            "GEOJSON DRAWING:\n"
            "  The UI supports drawing Point, LineString, and Polygon features directly on the map.\n"
            "  Features are stored in the geojson field as a standard GeoJSON FeatureCollection.\n"
            "  Each feature has: { type: 'Feature', geometry: { type, coordinates }, properties: { name, style, associations, metadata } }\n\n"
            "COMMON PITFALLS:\n"
            "  1. Forgetting bounds. The bounds field is essential for quick zoom-to-fit operations.\n"
            "  2. Latitude/longitude outside valid ranges. Latitude must be -90 to 90, longitude -180 to 180.\n"
            "  3. Using zoom values outside 0-20. The map supports 0-20, but most tiles max at 18-19.\n"
            "  4. GeoJSON features must use [longitude, latitude] coordinate order (not lat,lng).\n"
            "  5. Associations are loose references. The linked item may be deleted independently.\n"
        ),
        "content_schema": {
            "type": "object",
            "required": ["viewport"],
            "properties": {
                "viewport": {
                    "type": "object",
                    "required": ["latitude", "longitude", "zoom", "pitch", "bearing", "bounds"],
                    "properties": {
                        "latitude": {
                            "type": "number",
                            "minimum": -90,
                            "maximum": 90,
                            "description": "Center latitude of the map view"
                        },
                        "longitude": {
                            "type": "number",
                            "minimum": -180,
                            "maximum": 180,
                            "description": "Center longitude of the map view"
                        },
                        "zoom": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 20,
                            "description": "Zoom level (0 = world, 20 = building)"
                        },
                        "pitch": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 85,
                            "description": "Camera tilt in degrees (0 = top-down)"
                        },
                        "bearing": {
                            "type": "number",
                            "minimum": -180,
                            "maximum": 180,
                            "description": "Camera rotation in degrees (0 = north up)"
                        },
                        "bounds": {
                            "type": "object",
                            "required": ["north", "south", "east", "west"],
                            "properties": {
                                "north": {"type": "number", "description": "North bounding latitude"},
                                "south": {"type": "number", "description": "South bounding latitude"},
                                "east": {"type": "number", "description": "East bounding longitude"},
                                "west": {"type": "number", "description": "West bounding longitude"}
                            }
                        }
                    }
                },
                "style": {
                    "type": "string",
                    "enum": ["carto-voyager", "osm", "dark-matter", "google-satellite"],
                    "default": "carto-voyager",
                    "description": "Map tile style"
                },
                "layers": {
                    "type": "array",
                    "description": "deck.gl layers for data visualization (future feature)",
                    "items": {"type": "object"}
                },
                "geojson": {
                    "type": "object",
                    "description": "GeoJSON FeatureCollection with user-drawn geometries (points, lines, polygons)",
                    "properties": {
                        "type": {"const": "FeatureCollection"},
                        "features": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "type": {"const": "Feature"},
                                    "geometry": {
                                        "type": "object",
                                        "properties": {
                                            "type": {"type": "string", "enum": ["Point", "LineString", "MultiLineString", "Polygon", "MultiPolygon"]}
                                        }
                                    },
                                    "properties": {
                                        "type": "object",
                                        "properties": {
                                            "name": {"type": "string", "description": "Display name for the geometry"},
                                            "description": {"type": "string", "description": "Optional description text"},
                                            "style": {
                                                "type": "object",
                                                "properties": {
                                                    "color": {"type": "string", "description": "Hex color string"},
                                                    "fillOpacity": {"type": "number", "minimum": 0, "maximum": 1, "description": "Fill opacity for polygons"},
                                                    "strokeWidth": {"type": "number", "minimum": 1, "description": "Line width in pixels"}
                                                }
                                            },
                                            "associations": {
                                                "type": "array",
                                                "description": "Linked workspace items",
                                                "items": {
                                                    "type": "object",
                                                    "properties": {
                                                        "type": {"type": "string", "enum": ["artifact", "asset"]},
                                                        "id": {"type": "string", "description": "UUID of the linked item"},
                                                        "name": {"type": "string", "description": "Display name of the linked item"},
                                                        "kind": {"type": "string", "description": "Artifact type or asset MIME type"}
                                                    }
                                                }
                                            },
                                            "metadata": {
                                                "type": "object",
                                                "description": "Arbitrary JSON metadata"
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
                "viewport": {
                    "latitude": 20.0,
                    "longitude": 0.0,
                    "zoom": 2.0,
                    "pitch": 0.0,
                    "bearing": 0.0,
                    "bounds": {
                        "north": 85.0,
                        "south": -85.0,
                        "east": 180.0,
                        "west": -180.0
                    }
                },
                "style": "carto-voyager",
                "layers": [],
                "geojson": {
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "id": "feat-123",
                            "geometry": {
                                "type": "Point",
                                "coordinates": [-0.3763, 39.4699]
                            },
                            "properties": {
                                "name": "Waypoint 1",
                                "description": "Landing zone",
                                "style": {"color": "#1976d2"},
                                "associations": [],
                                "metadata": {"altitude": "100m", "restricted": True}
                            }
                        }
                    ]
                }
            }
        },
        "icon": "map",
        "category": "geography"
    },
    "gallery": {
        "key": "gallery",
        "name": "Gallery",
        "description": "A curated collection of image assets with captions, drag-and-drop reordering, and multiple public layout modes.",
        "ai_instructions": (
            "Use this artifact to create curated image collections (galleries). "
            "Galleries reference existing image assets and allow captions per image, "
            "reordering, and choosing a public presentation layout.\n\n"
            "WHEN TO USE:\n"
            "  - Photo albums, portfolios, product showcases\n"
            "  - Any curated collection of existing workspace images\n"
            "  - Collections that need a specific public presentation style\n\n"
            "WHEN NOT TO USE:\n"
            "  - A single image (use an image asset instead)\n"
            "  - Unstructured image dumps (use a folder instead)\n"
            "  - Images with heavy annotation needs (use note artifacts for inline commentary)\n\n"
            "TOP-LEVEL STRUCTURE:\n"
            "{\n"
            '  "layout": "default",   // Public presentation: default | carousel | masonry\n'
            '  "items": [             // Ordered array of gallery images\n'
            '    { "asset_id": "uuid", "caption": "optional text" }\n'
            '  ],\n'
            '  "linked_asset_ids": ["uuid"]  // Auto-managed, mirrors all asset_id values\n'
            "}\n\n"
            "LAYOUT MODES:\n"
            "  - default: Responsive grid of images with captions below each.\n"
            "  - carousel: Single large image with prev/next navigation and a thumbnail reel.\n"
            "  - masonry: Pinterest-style column layout with lightbox modal on click.\n\n"
            "ITEMS:\n"
            "  Each item references an existing image asset by UUID. The caption is optional.\n"
            "  Items are ordered by their position in the array. Reordering changes the array order.\n\n"
            "LINKED ASSET IDS:\n"
            "  The editor automatically populates 'linked_asset_ids' at the top level by scanning\n"
            "  all item.asset_id values. This list must be kept in sync with the items array.\n"
            "  The backend updates each asset's file_meta.linked_artifact_ids bidirectionally.\n\n"
            "UPLOADING NEW IMAGES:\n"
            "  New images can be uploaded directly from the gallery editor. They are saved as\n"
            "  assets in the same folder as the gallery artifact. After upload, they are\n"
            "  automatically appended to the gallery items array.\n\n"
            "ADDING EXISTING IMAGES:\n"
            "  Use the asset picker to search and select existing image assets from anywhere\n"
            "  in the workspace. The asset's UUID is added to the items array.\n\n"
            "WHEN CREATING A GALLERY VIA API:\n"
            "  POST /artifacts with body:\n"
            '  { "name": "Summer Photos", "type": "gallery", "folder_id": "...",\n'
            '    "description": "A collection of summer vacation photos.",\n'
            '    "content": { "layout": "default", "items": [], "linked_asset_ids": [] } }\n\n'
            "WHEN UPDATING:\n"
            "  PUT /artifacts/{id} with partial content. The editor auto-saves (1.5s debounce).\n\n"
            "COMMON PITFALLS:\n"
            "  1. Forgetting to include 'linked_asset_ids' — it should always match item.asset_ids.\n"
            "  2. Referencing a deleted asset. If an asset is deleted, its item becomes a broken link.\n"
            "  3. Using non-image assets. Only image assets (mime_type starts with 'image/') render correctly.\n"
            "  4. Uploading images to the wrong folder. Gallery uploads go to the gallery's folder_id."
        ),
        "content_schema": {
            "type": "object",
            "required": ["layout", "items"],
            "properties": {
                "layout": {
                    "type": "string",
                    "enum": ["default", "carousel", "masonry"],
                    "default": "default",
                    "description": "Public presentation layout for the gallery"
                },
                "items": {
                    "type": "array",
                    "description": "Ordered array of gallery images",
                    "items": {
                        "type": "object",
                        "required": ["asset_id"],
                        "properties": {
                            "asset_id": {
                                "type": "string",
                                "format": "uuid",
                                "description": "UUID of the referenced image asset"
                            },
                            "caption": {
                                "type": "string",
                                "description": "Optional caption text for this image"
                            }
                        }
                    }
                },
                "linked_asset_ids": {
                    "type": "array",
                    "items": {"type": "string", "format": "uuid"},
                    "description": "UUIDs of all assets referenced in items (auto-managed)"
                }
            }
        },
        "example_content": {
            "content": {
                "layout": "masonry",
                "items": [
                    {
                        "asset_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                        "caption": "Sunset over the ocean"
                    },
                    {
                        "asset_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
                        "caption": "Mountain trail at dawn"
                    },
                    {
                        "asset_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
                        "caption": "City skyline at night"
                    }
                ],
                "linked_asset_ids": [
                    "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    "b2c3d4e5-f6a7-8901-bcde-f12345678901",
                    "c3d4e5f6-a7b8-9012-cdef-123456789012"
                ]
            }
        },
        "icon": "photo_library",
        "category": "media"
    },
    "composer": {
        "key": "composer",
        "name": "Composition",
        "description": "A curated story or collection of artifacts arranged in order. Like a blog post made of other artifacts.",
        "ai_instructions": (
            "Use this artifact to create curated stories, blog posts, or collections that combine multiple artifacts into a single narrative.\n\n"
            "WHEN TO USE:\n"
            "  - Writing a travel story that includes notes, maps, and photo galleries\n"
            "  - Creating a project report with workflows, notes, and data visualizations\n"
            "  - Building a portfolio that showcases different artifact types together\n"
            "  - Any content that tells a story across multiple artifact types\n\n"
            "WHEN NOT TO USE:\n"
            "  - Simple single-artifact content (use the artifact's own type directly)\n"
            "  - Folder organization (use folders for that)\n"
            "  - Linking to another composition (use a note with a hyperlink instead)\n\n"
            "TOP-LEVEL STRUCTURE:\n"
            "{\n"
            '  "sections": [\n'
            '    { "artifact_id": "uuid", "caption": "optional text" }\n'
            '  ]\n'
            "}\n\n"
            "SECTIONS:\n"
            "  Each section references an existing artifact by UUID. The caption is optional text displayed under the rendered section.\n"
            "  Sections are rendered in order. Each artifact type has its own composer view:\n"
            "    - note: Full content rendered inline\n"
            "    - map: Static map thumbnail with bounding box, non-interactive, 'View full map' button\n"
            "    - gallery: 3 image thumbnails with count badge, 'View gallery' button\n"
            "    - workflow: Graph preview (pan-only, no interaction), 'View workflow' button\n\n"
            "IMPORTANT RULES:\n"
            "  1. A composition CANNOT reference another composition. The API will reject nested composers.\n"
            "  2. If a referenced artifact is deleted, the section shows a placeholder.\n"
            "  3. Sub-artifacts referenced by a public composition are visible within that composition even if not individually public.\n\n"
            "WHEN CREATING A COMPOSITION VIA API:\n"
            '  POST /artifacts with body:\n'
            '  { "name": "My Story", "type": "composer", "folder_id": "...",\n'
            '    "content": { "sections": [{ "artifact_id": "...", "caption": "A beautiful day" }] } }\n\n'
            "WHEN UPDATING:\n"
            "  PUT /artifacts/{id} with updated sections array.\n"
            "  The editor auto-saves (1.5s debounce)."
        ),
        "content_schema": {
            "type": "object",
            "required": ["sections"],
            "properties": {
                "sections": {
                    "type": "array",
                    "description": "Ordered array of artifact references",
                    "items": {
                        "type": "object",
                        "required": ["artifact_id"],
                        "properties": {
                            "artifact_id": {
                                "type": "string",
                                "format": "uuid",
                                "description": "UUID of the referenced artifact (cannot be another composer)"
                            },
                            "caption": {
                                "type": "string",
                                "description": "Optional text displayed under this section"
                            }
                        }
                    }
                }
            }
        },
        "example_content": {
            "content": {
                "sections": [
                    {
                        "artifact_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                        "caption": "Arrival in Antigua"
                    },
                    {
                        "artifact_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
                        "caption": "Best hidden hiking spots"
                    },
                    {
                        "artifact_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
                        "caption": "Our hotel by the lake"
                    }
                ]
            }
        },
        "icon": "auto_awesome_mosaic",
        "category": "publishing"
    }
}


def get_artifact_type(key: str) -> dict[str, Any] | None:
    """Get a single artifact type definition by key."""
    return ARTIFACT_TYPES.get(key)


def list_artifact_types() -> list[dict[str, Any]]:
    """List all artifact type definitions."""
    return list(ARTIFACT_TYPES.values())
