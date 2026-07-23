#!/bin/sh
# AuthorizedKeysCommand for sshd
# Queries PostgreSQL for registered SSH public keys.
#
# OpenSSH clears env for this command, and sshd may clear PID 1 environ.
# Credentials are written to /etc/git-auth.env at container start (see docker-compose).

export PATH="/usr/bin:/usr/local/bin:/bin:/usr/sbin:/sbin"

if [ -r /etc/git-auth.env ]; then
  # shellcheck disable=SC1091
  . /etc/git-auth.env
fi

export PGHOST="${POSTGRES_HOST:-db}"
export PGUSER="${POSTGRES_USER:-agentespacio}"
export PGPASSWORD="${POSTGRES_PASSWORD:-agentespacio}"
export PGDATABASE="${POSTGRES_DB:-agentespacio_db}"

/usr/bin/psql -t -A -c "SELECT public_key FROM repo_ssh_keys;" 2>/tmp/ssh-auth.err || true
