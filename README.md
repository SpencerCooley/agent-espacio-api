# Agent Espacio API

A self-hosted, self-contained collaborative workspace backend. AI agents and humans share the same content via API and web interface.

## What You Need

- A machine running Ubuntu (or any Linux with Docker support)
- Docker and Docker Compose

## Install Docker

If you don't have Docker yet:

See https://docs.docker.com/engine/install/ubuntu/ for the full guide.

## Quick Start (Local Development)

```bash
git clone https://github.com/SpencerCooley/agent-espacio-api.git
cd agent-espacio-api
cp .env.example .env

# The .env defaults are fine for local development.
# SECRET_KEY is already set in .env.example. Change it in production.

docker compose up 

```
The API is now running on `http://localhost:8000`.
- API documentation: `http://localhost:8000/redoc`
- Health check: `http://localhost:8000/health`

```bash
# Create the first admin user in another terminal while the containers are running
docker compose exec -it api python scripts/create_admin.py
```

Migrations run automatically on container startup. If you ever need to run them manually:

```bash
docker compose exec api alembic upgrade head
```


The best way to learn more about this system is to copy and past the entire json documentation into any LLM and just ask it questions about the system and the possible uses for a system like this. http://localhost:8000/openapi.json <--- full OAS documentation


This is everything you need to know about the development setup if you plan to do development on this platform. 


## Production Notes

The included `docker-compose.yml` is provided for convenience and local development. In production, there are two independent decisions to make: how you expose the API, and how you run the database.

### Exposing the API

**Port 8000 directly**  
The simplest path. Just run the container, expose port 8000, and point your DNS at the server. This is perfectly fine for internal tools or if you already have an external load balancer. The donside of this is that you have no ssl and it is kind of ugly to just serve your api from an ip address at port 8000. 

```bash
cp .env.example .env
# Edit .env: change SECRET_KEY to whatever you want, etc.
docker compose up -d
```

**Behind a reverse proxy (recommended for public-facing sites)**  
If you want SSL, a custom domain, or just a cleaner setup, put nginx (or Traefik, Caddy, etc.) in front. the best thing to do is just get your server running on port 8000 and then asking an ai how to setup nginx reverse proxy to server from 8000. This is a good setup below, but you need to use your own domain name. 

```nginx
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;

        # Required for WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        client_max_body_size 100M;

        proxy_read_timeout 300;
        proxy_connect_timeout 300;
        proxy_send_timeout 300;
    }
}
```

Then get a certificate with Let's Encrypt:

```bash
sudo apt-get install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

### Database

The compose file spins up a Postgres container for you. That works fine for small deployments, but in production you may prefer a managed database or a dedicated Postgres instance you control. Set `DATABASE_URL` in `.env` to point at it, and remove or disable the `db` service in your own compose override.

## API Documentation

Once the server is running, visit `/redoc` for full interactive documentation. No need to list endpoints here.

## License

MIT
