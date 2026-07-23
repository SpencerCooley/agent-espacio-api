# Agent Espacio API - Self-hosted Collaborative Workspace

Agent Espacio is a self-hosted, self-contained Google Drive-like interface that enables seamless collaboration between AI agents and humans. It provides a workspace where AI agents can create and modify artifacts (maps, data visualizations, documents) via API, while humans interact with the same content through a web interface.

## Features

- 🔐 **Simple Authentication**: Bearer token auth for users, API keys for AI agents
- 👥 **User Management**: Admin-controlled user creation and password reset
- 🤖 **AI Agent Support**: Stripe-style API keys for agent authentication
- 📦 **Self-contained**: No external dependencies (email, cloud storage, etc.)
- 🐳 **Dockerized**: Easy deployment on any VPS

## Quick Start

### Prerequisites

- Docker and Docker Compose
- A VPS with port 8000 open (or any port you configure)

### Installation

1. **Clone and configure:**
   ```bash
   git clone https://github.com/yourusername/agentespacio-api.git
   cd agentespacio-api
   cp .env.example .env
   # Edit .env if needed (defaults work for development)
   ```

2. **Start services:**
   ```bash
   docker compose up -d
   ```

3. **Run database migrations:**
   ```bash
   docker compose exec api alembic revision --autogenerate -m "initial_schema"
   docker compose exec api alembic upgrade head
   ```

4. **Create first admin user:**
   ```bash
   docker compose exec -it api python scripts/create_admin.py
   ```

5. **Access the API:**
   - API docs: http://localhost:8000/docs
   - Health check: http://localhost:8000/health

### Creating API Keys for AI Agents

Once logged in as admin:

```bash
# Get a token first
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "yourpassword"}'

# Create an API key
curl -X POST http://localhost:8000/api-keys \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "laptop-main"}'
  
# Response includes the key (shown only once!):
# {"id": 1, "name": "laptop-main", "key": "agent-esp-a3f7b2d8...", ...}
```

Your AI agent then uses the key:
```bash
curl http://localhost:8000/health \
  -H "X-Agent-Key: agent-esp-a3f7b2d8..."
```

## API Endpoints

### Authentication
- `POST /auth/login` - Login with email/password, receive bearer token
- `POST /auth/logout` - Invalidate current token
- `GET /auth/validate` - Check if token is valid

### Users (Admin only)
- `GET /users/me` - Get current user info
- `GET /users` - List all users
- `POST /users` - Create new user
- `PUT /users/{id}` - Update user
- `DELETE /users/{id}` - Delete user
- `POST /users/{id}/reset-password` - Reset user password

### API Keys (Admin only)
- `GET /api-keys` - List all API keys
- `POST /api-keys` - Create new API key
- `DELETE /api-keys/{id}` - Revoke API key
- `POST /api-keys/{id}/activate` - Reactivate revoked key

### Folders
- `GET /folders` - List folder tree
- `POST /folders` - Create folder
- `GET /folders/{id}` - Get folder details
- `GET /folders/{id}/contents` - Get subfolders + assets + artifacts
- `GET /folders/{id}/search?q=term` - Search within folder + descendants
- `PUT /folders/{id}` - Rename/move folder
- `DELETE /folders/{id}` - Recursive delete

### Assets
- `GET /assets` - List assets
- `POST /assets/upload` - Upload file (multipart/form-data)
- `GET /assets/{id}` - Get asset metadata
- `GET /assets/{id}/download` - Download file
- `DELETE /assets/{id}` - Delete asset

### Artifacts
- `GET /artifacts` - List artifacts
- `POST /artifacts` - Create artifact
- `GET /artifacts/{id}` - Get artifact
- `PUT /artifacts/{id}` - Update artifact
- `DELETE /artifacts/{id}` - Delete artifact
- `GET /artifacts/docs` - List artifact type definitions
- `GET /artifacts/docs/{type_key}` - Get specific type docs

### Repositories (Repo Artifacts)
- `GET /artifacts/{id}/repo` - Repo metadata (commits, files, publish config)
- `GET /artifacts/{id}/repo/tree` - File tree
- `GET /artifacts/{id}/repo/files/{path}` - Raw file contents
- `GET /artifacts/{id}/repo/commits` - Commit history
- `GET /artifacts/{id}/publish` - Get publish settings
- `PUT /artifacts/{id}/publish` - Update publish settings
- `DELETE /artifacts/{id}/publish` - Disable publishing
- `POST /artifacts/{id}/deploy` - Trigger manual deploy
- `GET /artifacts/{id}/deploy/status` - Get deploy status

### Public (No Authentication)
- `GET /public/view/{magic_id}` - View public folder/asset/artifact
- `GET /public/assets/{magic_id}/download` - Download public asset
- `GET /public/search/{magic_id}?q=term` - Search public folder
- `GET /public/repo/{magic_id}` - Public repo metadata
- `GET /public/repo/{magic_id}/tree` - Public file tree
- `GET /public/repo/{magic_id}/files/{path}` - Public file contents
- `GET /public/repo/{magic_id}/commits` - Public commit history

## Architecture

```
api/
├── alembic/          # Database migrations
├── controllers/      # Business logic
│   ├── auth/         # Login, logout, validation
│   ├── user/         # User CRUD operations
│   └── api_key/      # API key management
├── dependencies/     # FastAPI dependencies (auth, permissions, DB)
├── models/           # SQLAlchemy models
│   ├── user.py       # User account model
│   ├── token.py      # Bearer tokens (7-day expiry)
│   ├── api_key.py    # API keys for agents
│   └── reset_token.py # Password reset tokens
├── routers/          # API route handlers
│   ├── auth.py       # /auth/* endpoints
│   ├── users.py      # /users/* endpoints
│   └── api_keys.py   # /api-keys/* endpoints
├── types_definitions/# Pydantic schemas
├── utils/            # Password hashing, token generation
└── scripts/          # CLI utilities
```

## Authentication Methods

### Bearer Tokens (for Users)
1. Login with `POST /auth/login` to receive token
2. Include in headers: `Authorization: Bearer <token>`
3. Tokens expire after 7 days
4. Logout with `POST /auth/logout` to invalidate

### API Keys (for AI Agents)
1. Admin creates key via `POST /api-keys`
2. Key format: `agent-esp-{32-char-hex}`
3. Include in headers: `X-Agent-Key: agent-esp-...`
4. Keys are system-wide (not user-specific)
5. Soft delete (can be revoked/reactivated)

## Development

### Database Migrations

```bash
# Generate migration
docker compose exec api alembic revision --autogenerate -m "description"

# Run migration
docker compose exec api alembic upgrade head

# Downgrade
docker compose exec api alembic downgrade -1
```

### Testing

```bash
# Health check
curl http://localhost:8000/health

# Test with auth
curl http://localhost:8000/users/me \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Security Notes

- **Passwords**: Hashed with bcrypt (cost factor 12)
- **API Keys**: Only SHA-256 hash stored, full key shown once
- **Tokens**: Stored in database, expire after 7 days
- **No Email**: Password resets handled by admin (no email flow)
- **Self-hosted**: All data stays on your VPS

## Static Site Publishing (Repo Artifacts)

Repo artifacts support static site publishing for embeddable modules. This is designed for self-contained HTML/CSS/JS modules — interactive charts, slideshows, motion graphics, data visualizations — that should be embeddable in compositions or viewable publicly.

### What Works
- **Plain HTML/CSS/JS** — No build step needed. Just push files and deploy.
- **Vite** — Configure `base: './'` in `vite.config.js` for relative paths. Build output to `dist/` (or your configured output directory).
- **Any tool that generates relative paths** — The key requirement is that all internal asset references use relative paths (`./` or `../`) so they work when served from a subdirectory like `/published/{slug}/`.

### What Does NOT Work
- **Next.js static export** — Generates absolute paths (`/_next/static/...`) that cannot be served from a subdirectory. Use Vite or plain HTML instead.
- **Tools that hardcode domain roots** — Any build tool that emits absolute paths starting with `/` will break.

### Philosophy
Agent Espacio provides the hosting URL. All compute (screen recording, video editing, asset generation) happens locally on the agent's machine using tools like Playwright and FFmpeg. No processing happens on the server.

## Next Steps

- 📁 Folder/file management system (implemented)
- 🎨 Artifact types (maps, charts, documents, repos) (implemented)
- 🔄 Real-time collaboration
- 🌐 React frontend (implemented)

## License

MIT
