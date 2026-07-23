#!/bin/sh
# AuthorizedKeysCommand for sshd
# Queries PostgreSQL for registered SSH public keys.
#
# OpenSSH clears the environment for AuthorizedKeysCommand.
# Container env from docker-compose still lives on PID 1 — read it from there.

export PATH="/usr/bin:/usr/local/bin:/bin:/usr/sbin:/sbin"

if [ -r /proc/1/environ ]; then
  while IFS= read -r -d '' line; do
    case "$line" in
      POSTGRES_*) export "$line" ;;
    esac
  done < /proc/1/environ
fi

export PGHOST="${POSTGRES_HOST:-db}"
export PGUSER="${POSTGRES_USER:-agentespacio}"
export PGPASSWORD="${POSTGRES_PASSWORD:-agentespacio}"
export PGDATABASE="${POSTGRES_DB:-agentespacio_db}"

/usr/bin/psql -t -A -c "SELECT public_key FROM repo_ssh_keys;" 2>/tmp/ssh-auth.err || true
