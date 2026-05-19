# Deploying CloudVault Backend (Docker)

This document explains how to build and run the CloudVault backend using Docker.

Prerequisites
- Docker and Docker Compose installed.

Quick start (development)

1. Build and run services with Docker Compose:

```bash
docker-compose up --build
```

2. The backend will be available at `http://localhost:8000`.

Environment variables (examples)
- `DEFAULT_ADMIN_EMAIL` — default seeded admin email (default: `admin@cloudvault.io`)
- `DEFAULT_ADMIN_PASSWORD` — default seeded admin password (default: `admin`)
- `ADMIN_SECRET` — secret required to register additional admin accounts
- `SECRET_KEY` — JWT secret
- `APP_URL` — public URL used to build share links

Production notes
- For production, use a managed database (MySQL/Postgres) and set `DATABASE_URL`.
- Use a reverse proxy (Nginx) or a platform like Render, Railway, or Fly.io for TLS and scaling.
