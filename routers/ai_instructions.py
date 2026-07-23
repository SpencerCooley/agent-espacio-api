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
- **repo** — Git repository for storing code, pages, and projects. Push files from your local machine via SSH and browse them in the Espacio UI. Supports static site publishing for embeddable modules.

## 6. Static Site Publishing (Repo Artifacts)

Repo artifacts can be published as static sites served from `/published/{slug}/`. This is designed for **self-contained HTML modules** — interactive charts, slideshows, motion graphics, data visualizations, or any rich content that should be embeddable in compositions or viewable publicly.

### What Works
- **Plain HTML/CSS/JS** — Single file or multi-file modules. No build step needed. Just push files and click Deploy.
- **Vite** — Configure `base: './'` in `vite.config.js` so all asset paths are relative. Build outputs to `dist/` (or your configured output directory).
- **Any build tool that generates relative paths** — The key requirement is that all internal asset references (CSS, JS, images, fonts) use relative paths (`./` or `../`) so they work when served from a subdirectory like `/published/my-slug/`.

### What Does NOT Work
- **Next.js static export** — Next.js generates absolute paths (`/_next/static/...`) that cannot be served from a subdirectory. It requires either root-level deployment or a `basePath` configuration that is not compatible with this system. Use Vite or plain HTML instead.
- **Tools that hardcode domain roots** — Any build tool that emits absolute paths starting with `/` will break. The system assumes modules are subdirectory-agnostic.

### Workflow
1. Create a repo artifact in Agent Espacio (or use an existing one)
2. Clone it locally via SSH: `git clone ssh://git@localhost:2222/repos/{artifact_id}.git`
3. Write your module (HTML, CSS, JS, or a Vite project with `base: './'`)
4. Push: `git push origin main`
5. In the Espacio UI, click the gear icon on the repo artifact, choose "Static Site", configure a slug, optionally add a build command (e.g., `npm run build`) and output directory (e.g., `dist`), then save.
6. Click "Deploy" in the header. The system clones the repo, optionally runs the build, and copies the output to `/published/{slug}/`.
7. The site is now accessible at `https://cooleylabs.com/published/{slug}/` (or your configured `PUBLIC_URL`)

### Render Modes
- **Embedded** — Renders inside an iframe with a branded navigation bar. Best for compositions. The module runs in a sandboxed iframe.
- **Direct** — Redirects visitors directly to the published URL. No Espacio UI shown. Best for standalone sharing.
- **Repository + Site Link** — Shows the normal repo view (code browser) with a "View Site" link. Best when you want visitors to see the source code first.

### Public Code Access
- By default, published static sites (embedded/direct) do NOT allow public access to the repo code or cloning.
- Toggle "Allow public code view" in settings to enable a "View Code" link that shows the repo browser.
- When enabled, anyone can view the repo via `?repo_view=true` on the public URL.
- **Clone access** is blocked unless "Allow public code view" is enabled. The system checks this before serving git clone requests over HTTP.

### Use Cases
- **Interactive data visualizations** — D3.js, Chart.js, or Three.js modules embedded in a composer story
- **Motion graphics** — CSS animations or canvas-based animations that Playwright can screen-record for Instagram Reels
- **Slideshows** — HTML-based presentations with navigation, embedded in data reports
- **Small widgets** — Interactive calculators, maps, or charts that live inside compositions
- **Prototypes** — Quick HTML/CSS/JS experiments shared as public URLs

### Key Philosophy
Agent Espacio provides the hosting URL. All compute (screen recording, video editing, asset generation) happens locally on the agent's machine using tools like Playwright and FFmpeg. No processing happens on the server.

## 8. Creating Themes

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

## 8. Important Rules

- Folder names are not unique (like a normal filesystem)
- Deleting a folder recursively deletes ALL contents inside it (subfolders, assets, artifacts)
- Assets are stored with the naming convention: {asset_id}_{filename}
- The root folder ("My Drive") cannot be deleted
- Artifacts use a flexible JSONB content field — structure depends on the artifact type
- Folder creators can be null (root folder, API-key created folders)
- Items in a folder are always sorted alphabetically by name
- **Prefer search over recursive listing** — When looking for a specific item, use `GET /folders/{id}/search?q=...` instead of walking the folder tree

## 9. Common Workflows

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

## 10. API Endpoints Reference

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

### Repositories (Repo Artifacts)
- GET /artifacts/{id}/repo — Repo metadata (commits, file count, size, publish config)
- GET /artifacts/{id}/repo/tree?path=... — File tree at HEAD
- GET /artifacts/{id}/repo/files/{path} — Raw file contents
- GET /artifacts/{id}/repo/commits — Commit history
- GET /artifacts/{id}/publish — Get publish settings
- PUT /artifacts/{id}/publish — Update publish settings (enable/disable, slug, render mode, build command, output directory, auto-deploy, allow_public_code_view)
- DELETE /artifacts/{id}/publish — Disable publishing and remove published files
- POST /artifacts/{id}/deploy — Trigger a manual deploy (runs Celery task)
- GET /artifacts/{id}/deploy/status — Get deploy status

### Public Repository Endpoints (No Auth)
- GET /public/repo/{magic_id} — Public repo metadata
- GET /public/repo/{magic_id}/tree — Public file tree
- GET /public/repo/{magic_id}/files/{path} — Public file contents
- GET /public/repo/{magic_id}/commits — Public commit history

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
