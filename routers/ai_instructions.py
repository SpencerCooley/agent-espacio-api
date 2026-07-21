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

### Step 2b: Search Within a Folder (Better for Finding Things)

Instead of recursively listing every subfolder to find an item, use the search endpoint:

GET ${AGENT_ESPACIO_API}/folders/{folder_id}/search?q=search-term

This searches **folder names, asset names, and artifact names** within the specified folder AND all its subfolders, using case-insensitive partial matching. Results are returned as a unified list (same shape as /contents) sorted alphabetically.

**When to use search vs. listing:**
- Use `/search` when you know (or roughly know) the name of what you're looking for.
- Use `/contents` when you need to see everything in a specific folder.
- **Example**: If the user says "find my note about LLM training", search with `q=llm train` rather than listing every subfolder.

**Public folders also support search** (no auth required):
GET ${AGENT_ESPACIO_API}/public/search/{folder_magic_id}?q=search-term

Use this when a folder is publicly shared and you need to find items within it without authentication. Only publicly accessible items are returned.

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
- **workflow** — Visual process builder with directed graphs of nodes (actions, AI steps, human approvals, decisions, code, data references).
- **map** — Interactive geospatial map with viewport state, GeoJSON features (points, lines, polygons), and linked workspace items.
- **gallery** — Curated image collection with captions, drag-and-drop reordering, and multiple public layout modes (grid, carousel, masonry).
- **composer** — Curated story or collection that combines multiple artifacts in order. Like a blog post made of other artifacts. Cannot nest other composers.
- **repo** — Git repository for storing code, pages, and projects. Push files from your local machine via SSH and browse them in the Espacio UI. Supports build/serve pipeline for static sites (Phase 2).

## 6. Creating Themes

Themes define the visual appearance of the workspace. They are stored in the database and drive both the admin panel and public page styling. Each theme has a `light_definition` and `dark_definition` containing full MUI theme configurations (palette, typography, component overrides).

### Discover Existing Themes

The best way to learn is to look at what already exists:

```
GET ${AGENT_ESPACIO_API}/themes
GET ${AGENT_ESPACIO_API}/themes/{theme_id}
```

Study the JSON structure of existing themes — especially their `light_definition` and `dark_definition` objects.

### Create a New Theme

```
POST ${AGENT_ESPACIO_API}/themes
X-Agent-Key: ${AGENT_ESPACIO_KEY}
Content-Type: application/json
```

```json
{
  "name": "Your Theme Name",
  "light_definition": {
    "palette": { "mode": "light", "primary": {...}, "background": {...} },
    "typography": { "fontFamily": "...", "h1": {...} },
    "components": { "MuiButton": {...}, "MuiCard": {...} }
  },
  "dark_definition": {
    "palette": { "mode": "dark", "primary": {...}, "background": {...} },
    "typography": { "fontFamily": "...", "h1": {...} },
    "components": { "MuiButton": {...}, "MuiCard": {...} }
  }
}
```

### What Makes a Good Theme

- **Consistent palette** — Define `primary`, `secondary`, `background`, `text`, and feedback colors (`error`, `warning`, `success`, `info`)
- **Typography matters** — Choose a distinctive `fontFamily`. Use `letterSpacing`, `fontWeight`, and `lineHeight` to create character. Headers should feel intentional.
- **Component overrides** — The magic is in `components.MuiButton`, `MuiCard`, `MuiTextField`, `MuiChip`, `MuiPaper`, `MuiAppBar`, `MuiDialog`, `MuiTooltip`, `MuiAvatar`, `MuiDivider`, `MuiListItem`, `MuiSwitch`, `MuiSlider`. These control how every UI element looks and behaves.
- **Animations & micro-interactions** — Use `transition` with custom `cubic-bezier` easing curves. Buttons that lift, cards that glow, inputs that pulse — these create personality.
- **Always create BOTH light and dark** — Every theme must have a meaningful `light_definition` and `dark_definition`. Do not copy the dark palette into the light slot. Light mode should use light backgrounds, dark text, and softer shadows. Dark mode should use dark backgrounds, light text, and neon/glow effects.
- **Reference MUI's theme structure** — The JSON mirrors Material-UI's `ThemeOptions` object. Any valid MUI theme property works inside `light_definition` and `dark_definition`.

### Update or Delete Themes

```
PUT    ${AGENT_ESPACIO_API}/themes/{theme_id}
DELETE ${AGENT_ESPACIO_API}/themes/{theme_id}
```

## 7. Important Rules

- Folder names are not unique (like a normal filesystem)
- Deleting a folder recursively deletes ALL contents inside it (subfolders, assets, artifacts)
- Assets are stored with the naming convention: {asset_id}_{filename}
- The root folder ("My Drive") cannot be deleted
- Artifacts use a flexible JSONB content field — structure depends on the artifact type
- Folder creators can be null (root folder, API-key created folders)
- Items in a folder are always sorted alphabetically by name
- **Prefer search over recursive listing** — When looking for a specific item, use `GET /folders/{id}/search?q=...` instead of walking the folder tree

## 8. Common Workflows

### Create a project with a note
1. Create folder: POST /folders {"name": "Project Alpha", "parent_id": "..."}
2. Create note: POST /artifacts {"name": "Plan", "type": "note", "folder_id": "...", "content": {...}}

### Upload an image to a folder
1. POST /assets/upload with file and folder_id

### Create a nested folder structure
1. POST /folders {"name": "2024", "parent_id": "root_id"}
2. POST /folders {"name": "Q1", "parent_id": "2024_folder_id"}

### Find an item without knowing its exact location
1. Start from root: GET /folders (to get root id)
2. Search: GET /folders/{root_id}/search?q=training+notes
3. Results will include the item with its folder context

### Search a public folder for publicly shared content
1. Get the folder's public_magic_id from its metadata
2. Search: GET /public/search/{public_magic_id}?q=search-term
3. No authentication needed — only public items are returned

## 9. API Endpoints Reference

### Folders
- GET /folders — List folder tree
- POST /folders — Create folder
- GET /folders/{id} — Get folder details
- GET /folders/{id}/contents — Get subfolders + assets + artifacts (unified list)
- GET /folders/{id}/search?q=term — Search names across folder + all descendants
- PUT /folders/{id} — Rename/move folder
- DELETE /folders/{id} — Recursive delete

### Public (No Authentication Required)
- GET /public/view/{magic_id} — View a public folder, asset, or artifact
- GET /public/assets/{magic_id}/download — Download a public asset
- GET /public/search/{magic_id}?q=term — Search within a public folder + descendants

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

### Themes
- GET /themes — List all themes (public, no auth)
- GET /themes/{id} — Get a single theme (public, no auth)
- POST /themes — Create theme (auth required)
- PUT /themes/{id} — Update theme (auth required)
- DELETE /themes/{id} — Delete theme (auth required)

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
