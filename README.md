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

## Next Steps

This is the **auth foundation**. Future phases will add:

- 📁 Folder/file management system
- 🎨 Artifact types (maps, charts, documents)
- 🔄 Real-time collaboration
- 🌐 React frontend

## License

MIT
