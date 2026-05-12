# Agent Espacio Scripts

Utility scripts for setup and maintenance.

## create_admin.py

Creates the first admin user when setting up a fresh Agent Espacio installation.

### Usage

```bash
# After starting the containers and running migrations
docker compose exec -it agentespacio_api python scripts/create_admin.py
```

### When to use

- **First-time setup**: When installing Agent Espacio on a fresh VPS
- **After database reset**: If you've reset the database and need to recreate the admin

### What it does

1. Checks that no users exist in the database (safety check)
2. Prompts for admin email and password
3. Creates the first admin user with `admin` role
4. Auto-confirms the account (no email confirmation needed)

### Example

```bash
$ docker compose exec -it agentespacio_api python scripts/create_admin.py
============================================================
Agent Espacio - Create First Admin User
============================================================

Admin email: admin@example.com
Admin password (min 8 chars): ********
Confirm password: ********

============================================================
SUCCESS! Admin user created.
============================================================
Email: admin@example.com
Role: admin

You can now login at:
  http://YOUR_VPS_IP:8000/docs

Or use the API:
  POST /auth/login

============================================================
```

### After creation

Once the admin is created, you can:

1. **Login via API**: `POST /auth/login` with email and password
2. **Get a token**: Use the returned token in the `Authorization: Bearer <token>` header
3. **Create more users**: `POST /users` (admin only)
4. **Create API keys**: `POST /api-keys` for your AI agents

## Future Scripts

- `backup.py` - Database backup utility
- `restore.py` - Database restore utility
- `reset_password.py` - CLI password reset (alternative to API)
