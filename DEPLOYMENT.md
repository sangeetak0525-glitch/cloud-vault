# CloudVault Hosting Guide

This repository is ready for hosting. It includes:

- `backend/Dockerfile` for container deployment.
- `docker-compose.yml` for local development.
- `render.yaml` for Render.com deployment.
- A FastAPI backend that stores uploads in `uploads/` and uses SQLite by default.

## Why Render is the easiest path

Render is recommended because your repo already contains a `render.yaml` and the backend is containerized. That means you can get a public URL quickly, with minimal setup.

> ✅ Recommended: use Render for the fastest deployment experience.

## Step 1 — Prepare Render deployment

1. Sign in to https://render.com and connect your Git repository.
2. Create a new **Web Service**.
3. Select **Docker**.
4. Set the `Dockerfile Path` to:
   - `backend/Dockerfile`
5. Configure the service environment variables.

### Required Render environment variables

- `DATABASE_URL`: `sqlite:///./cloudvault.db` (demo only)
- `DEFAULT_ADMIN_EMAIL`: `admin@cloudvault.io`
- `DEFAULT_ADMIN_PASSWORD`: `admin`
- `ADMIN_SECRET`: `CLOUDVAULT_ADMIN_2024`
- `SECRET_KEY`: `supersecret`
- `APP_URL`: `https://<your-render-service>.onrender.com`

### Strong security warning

These defaults are insecure and should never be used in production:

- `DEFAULT_ADMIN_PASSWORD`: `admin`
- `ADMIN_SECRET`: `CLOUDVAULT_ADMIN_2024`
- `SECRET_KEY`: `supersecret`

> ⚠️ Change all of these in Render’s Environment settings before you deploy.

## Step 2 — Make your app persistent on Render

Render service storage is ephemeral. That means:

- `cloudvault.db` will not survive a redeploy.
- uploaded files in `uploads/` can disappear after a restart or deploy.

### Recommended persistence setup

For a durable Render deployment:

1. Add a Render Persistent Disk.
2. Mount it to a path such as `/data`.
3. Update Render environment variables to use that disk path.

Example values:

- `DATABASE_URL`: `sqlite:////data/cloudvault.db`
- `UPLOADS_DIR` (not required by code, but useful for your own reference): `/data/uploads`

Then configure the disk mount to keep `/data` persistent.

> 💡 On Render, the free starter service can still run the app, but the disk is best for data safety.

## Step 3 — Update `APP_URL`

Make sure `APP_URL` matches your live Render service URL. The app uses this to generate public share links.

Example:

- `APP_URL`: `https://cloudvault-yourname.onrender.com`

## Step 4 — Deploy and verify

1. Save the Render service.
2. Deploy the service.
3. Visit the public URL from Render.
4. Confirm the frontend loads and the login/register flow works.

## What to do if you want production-safe hosting

For a stronger production deployment, use a managed external database instead of SQLite.

- Add PostgreSQL or MySQL on Render or another provider.
- Set `DATABASE_URL` to the managed database URL.
- Keep `SECRET_KEY` and `ADMIN_SECRET` secret.
- Keep uploaded files on a persistent disk or external object storage.

## Local development with Docker Compose

To run locally:

```bash
docker-compose up --build
```

Then open:

- `http://localhost:8000`

The local `docker-compose.yml` mounts:

- `./cloudvault.db` → `/app/cloudvault.db`
- `./uploads` → `/app/uploads`

## Quick checklist before public launch

- [ ] Replace default passwords and secrets
- [ ] Set `APP_URL` to the real public URL
- [ ] Add Render disk if you want persistent uploads and database storage
- [ ] Prefer a managed DB for production workloads
- [ ] Keep sensitive values out of source control

## Summary

This project is already in great shape for hosting. Render is the fastest route because your repo already includes `render.yaml`, a Dockerfile, and a working backend.

The most important step before hosting is to replace weak default credentials and secure your persistent storage. Once deployed, your site can be shared on any device via the Render public URL.
