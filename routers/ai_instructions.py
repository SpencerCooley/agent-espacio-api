"""
AI Instructions router.

Provides an unauthenticated onboarding endpoint for AI agents
to learn how to interact with the Agent Espacio API.

This endpoint returns a comprehensive text guide covering:
- Environment variable setup
- Authentication
- Core concepts (folders, assets, artifacts)
- Quick start workflow
- API reference
- Important rules
"""
from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

router = APIRouter(
    prefix="/ai-instructions",
    tags=["AI Instructions"],
)

AI_INSTRUCTIONS_TEXT = """# Agent Espacio — AI Agent Onboarding Guide

## 1. Environment Setup

Before making any requests, ensure these environment variables are set:

```
AGENT_ESPACIO_API=http://localhost:8000
AGENT_ESPACIO_KEY=<your_api_key_here>
```

Get an API key from the admin panel at the web UI, or ask the human user to create one for you.

## 2. Authentication

The API accepts two authentication methods:

### Method A: API Key (Recommended for AI Agents)
Set the header:
```
X-Agent-Key: ${AGENT_ESPACIO_KEY}
```

### Method B: User Bearer Token
If acting on behalf of a logged-in user:
```
Authorization: Bearer ${USER_ACCESS_TOKEN}
```

**For AI agents**: Use Method A with the API key provided by the human user.

## 3. What is Agent Espacio?

Agent Espacio is a collaborative workspace where AI agents and humans organize content together.
It has three types of items that live in a hierarchical folder structure:

- **Folders** — Containers for organizing content (unlimited nesting)
- **Assets** — Uploaded files (images, markdown, JSON, etc.)
- **Artifacts** — Interactive, non-file content (notes, maps, charts, etc.)

All items coexist in folders. A folder can contain subfolders, assets, and artifacts side by side.

## 4. Quick Start Workflow

### Step 1: Find the Root Folder

GET ${AGENT_ESPACIO_API}/folders

The root folder is "My Drive" (id: 00000000-0000-0000-0000-000000000001).
You can also list its contents directly.

### Step 2: Explore a Folder

GET ${AGENT_ESPACIO_API}/folders/{folder_id}/contents

Returns a unified list of folders, assets, and artifacts in that folder, sorted alphabetically by name.

### Step 3: Create a Folder

POST ${AGENT_ESPACIO_API}/folders
```json
{
  "name": "Your Folder Name",
  "parent_id": "00000000-0000-0000-0000-000000000001"
}
```

### Step 4: Upload a File

POST ${AGENT_ESPACIO_API}/assets/upload
Content-Type: multipart/form-data
Fields:
  - file: <binary file data>
  - folder_id: <optional, defaults to root>

### Step 5: Create an Artifact

First, discover available types:
GET ${AGENT_ESPACIO_API}/artifacts/docs

Then create one:
POST ${AGENT_ESPACIO_API}/artifacts
```json
{
  "name": "Meeting Notes",
  "type": "note",
  "description": "Notes from the weekly sync",
  "folder_id": "...",
  "content": {
    "content": {
      "type": "doc",
      "content": [
        {
          "type": "paragraph",
          "content": [
            {"type": "text", "text": "Hello world"}
          ]
        }
      ]
    }
  }
}
```

## 5. Artifact Types

Discover all supported artifact types and their schemas:
GET ${AGENT_ESPACIO_API}/artifacts/docs/{type_key}

Currently supported:
- **note** — Rich text document using TipTap/ProseMirror JSON format. Supports bold, italic, underline, strikethrough, text color, highlight, lists, headings, images, tables, and more.

## 6. Important Rules

- Folder names are not unique (like a normal filesystem)
- Deleting a folder recursively deletes ALL contents inside it (subfolders, assets, artifacts)
- Assets are stored with the naming convention: {asset_id}_{filename}
- The root folder ("My Drive") cannot be deleted
- Artifacts use a flexible JSONB content field — structure depends on the artifact type
- Folder creators can be null (root folder, API-key created folders)
- Items in a folder are always sorted alphabetically by name

## 7. Common Workflows

### Create a project with a note
1. Create folder: POST /folders {"name": "Project Alpha", "parent_id": "..."}
2. Create note: POST /artifacts {"name": "Plan", "type": "note", "folder_id": "...", "content": {...}}

### Upload an image to a folder
1. POST /assets/upload with file and folder_id

### Create a nested folder structure
1. POST /folders {"name": "2024", "parent_id": "root_id"}
2. POST /folders {"name": "Q1", "parent_id": "2024_folder_id"}

## 8. API Endpoints Reference

### Folders
- GET /folders — List folder tree
- POST /folders — Create folder
- GET /folders/{id} — Get folder details
- GET /folders/{id}/contents — Get subfolders + assets + artifacts (unified list)
- PUT /folders/{id} — Rename/move folder
- DELETE /folders/{id} — Recursive delete

### Assets
- GET /assets — List assets (with filters)
- POST /assets/upload — Upload file (multipart/form-data)
- GET /assets/{id} — Get asset metadata
- GET /assets/{id}/download — Download file
- DELETE /assets/{id} — Delete asset + file

### Artifacts
- GET /artifacts — List artifacts (with filters)
- POST /artifacts — Create artifact
- GET /artifacts/{id} — Get artifact
- PUT /artifacts/{id} — Update artifact
- DELETE /artifacts/{id} — Delete artifact
- GET /artifacts/docs — List all artifact type definitions
- GET /artifacts/docs/{type_key} — Get specific artifact type docs

---

For questions or issues, ask the human user to check the API documentation at /docs (FastAPI auto-generated docs).
"""


@router.get("", response_class=PlainTextResponse)
async def get_ai_instructions():
    """
    Return AI agent onboarding instructions.

    This endpoint requires no authentication. It provides a comprehensive guide
    for AI agents to learn how to interact with the Agent Espacio API.

    AI agents should:
    1. Read these instructions
    2. Ask the human user for an API key if not already configured
    3. Set AGENT_ESPACIO_API and AGENT_ESPACIO_KEY environment variables
    4. Start making authenticated requests
    """
    return AI_INSTRUCTIONS_TEXT
