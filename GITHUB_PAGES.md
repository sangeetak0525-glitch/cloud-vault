# CloudVault on GitHub Pages (public URL)

GitHub Pages only hosts the **frontend** (HTML/JS). Your **backend** (login, uploads, folders) must run on a service such as [Render](https://render.com) (see `DEPLOYMENT.md`).

## Fix the 404 error

The 404 happens when GitHub serves the repo root but `index.html` lives in `frontend/`.

**Option A — Recommended (GitHub Actions)**

1. Push this repo (includes `.github/workflows/deploy-pages.yml`).
2. On GitHub: **Settings → Pages**.
3. Under **Build and deployment → Source**, choose **GitHub Actions** (not “Deploy from branch”).
4. After the workflow runs, open:  
   `https://sangeetak0525-glitch.github.io/cloud-vault/`

**Option B — Deploy from branch**

1. **Settings → Pages**.
2. **Source**: Deploy from branch `main`.
3. **Folder**: `/frontend` (not `/` root).
4. Save and wait 1–2 minutes, then open the same URL.

**Option C — Root redirect**

If you keep publishing from `/` (root), use the root `index.html` in this repo (redirects to `frontend/index.html`).

---

## Make the site public

1. **Repository visibility**: **Settings → General → Danger zone** — set the repo to **Public**. Private repos need GitHub Pro for public Pages.
2. **Pages**: Once deployed, the Pages URL is **public on the internet** (anyone with the link can open the UI).
3. **Backend**: Deploy on Render and use a public Render URL; set that URL in `frontend/config.js` (see below).

---

## Connect frontend to your API

Edit `frontend/config.js` and set your live backend URL:

```javascript
window.CLOUDVAULT_API_URL = 'https://YOUR-SERVICE.onrender.com';
```

Redeploy Pages (push to `main` or re-run the Actions workflow).

On Render, set environment variable:

- `APP_URL` = your Render URL (for share links)

---

## URLs you have

| What | URL |
|------|-----|
| GitHub Pages (UI) | `https://sangeetak0525-glitch.github.io/cloud-vault/` |
| Vercel (if frontend only) | Check Vercel dashboard — also needs `config.js` API URL |
| Backend (API) | Your Render web service URL |

---

## Quick checklist

- [ ] Repo is **Public**
- [ ] Pages source is **GitHub Actions** or folder **`/frontend`**
- [ ] Backend deployed on Render (or similar)
- [ ] `frontend/config.js` has the Render API URL
- [ ] `APP_URL` on Render matches the Render URL

After that, open the GitHub Pages URL in any browser; sign up / sign in will talk to your Render backend.
