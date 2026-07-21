#!/bin/sh
# AuthorizedKeysCommand for sshd
# Queries the PostgreSQL database for all registered SSH public keys
# Returns them one per line, which sshd validates against the presented key

# sshd clears the environment for AuthorizedKeysCommand
# We must set PATH so psql can find its own binary
export PATH="/usr/bin:/usr/local/bin:/bin:/usr/sbin:/sbin"

# Database credentials (match docker-compose.yml defaults)
HOST="${POSTGRES_HOST:-db}"
USER="${POSTGRES_USER:-agentespacio}"
DB="${POSTGRES_DB:-agentespacio_db}"
PASS="${POSTGRES_PASSWORD:-agentespacio}"

export PGPASSWORD="$PASS"

/usr/bin/psql -h "$HOST" -U "$USER" -d "$DB" -t -A -c "SELECT public_key FROM repo_ssh_keys;" 2>/dev/null | sed 's/^ *//' || true
