# Deploying to Vercel

Vercel runs the app as a serverless Python function. Two things matter:

1. **The database must be external.** Vercel's file system is temporary, so use PostgreSQL (free options: Neon, Supabase, or Neon through the Vercel Marketplace).
2. **Static files and the trained model are committed to the repo** (`staticfiles/`, `risk/artifacts/`). Vercel does not run a build step for this project.

## Steps

### 1. Create the PostgreSQL database
Create a free project at https://neon.tech (or Supabase). Copy the connection string. It looks like
`postgresql://user:password@host/dbname?sslmode=require`

### 2. Put the folder on GitHub
```bash
cd mrrh-risk-system
git init && git add . && git commit -m "MRRH risk prototype"
# create an empty repository on github.com, then:
git remote add origin https://github.com/<you>/mrrh-risk-system.git
git push -u origin main
```
Check that `staticfiles/` and `risk/artifacts/model.npz` are in the commit. Do not commit `.env`.

### 3. Import the project in Vercel
Vercel dashboard > **Add New > Project** > pick the repository. Framework preset: **Other**. Leave build and output settings empty.

### 4. Set environment variables (Project > Settings > Environment Variables)

| Name | Value |
|---|---|
| `DJANGO_SECRET_KEY` | a long random string: `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `DATABASE_URL` | the PostgreSQL connection string from step 1 |
| `DEMO_MODE` | `1` |
| `DJANGO_DEBUG` | `0` |
| `DJANGO_ALLOWED_HOSTS` | only if you use your own domain, e.g. `.vercel.app,risk.example.org` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | only for your own domain, e.g. `https://risk.example.org` |

Then click **Deploy**.

### 5. Create the tables and the first users (once, from your computer)
```bash
pip install -r requirements.txt
export DATABASE_URL='postgresql://...sslmode=require'     # Windows PowerShell: $env:DATABASE_URL='...'
python manage.py migrate
python manage.py setup_demo
python manage.py createsuperuser
```
Add healthcare workers and supervisors in `https://<your-app>.vercel.app/admin/` (tick *Staff status* for a supervisor, add workers to the group *Healthcare worker*).
To create two demo accounts instead, set `DEMO_PASSWORD` (10+ characters) and run `python manage.py setup_demo --users`.

### 6. Check it works
- `https://<your-app>.vercel.app/healthz` should return `{"status": "ok", ...}`
- Log in, make an assessment, open History and About.

### Command-line alternative
`npm i -g vercel`, then `vercel` (preview) and `vercel --prod`. Set the same variables with `vercel env add`.

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| 500 error on every page | Missing `DJANGO_SECRET_KEY`. Check the function logs in Vercel |
| `relation "..." does not exist` | You have not run `migrate` against the production `DATABASE_URL` (step 5) |
| `DisallowedHost` | Add the domain to `DJANGO_ALLOWED_HOSTS` |
| `CSRF verification failed` on a custom domain | Add `https://your-domain` to `DJANGO_CSRF_TRUSTED_ORIGINS` |
| Page has no styling | `staticfiles/` is missing from the repo. Run `DJANGO_DEBUG=1 python manage.py collectstatic --noinput`, commit and redeploy |
| `/healthz` says model-unavailable | `risk/artifacts/model.npz` and `model_meta.json` are not in the repo. Run `python ml/train.py`, commit and redeploy |
| Slow first request | Normal cold start on serverless |

## Notes
- This setup has been tested locally (tests, running server, screenshots) but not deployed from here, because deploying needs your own Vercel account. If the first deploy shows a Vercel-specific error, send me the build log.
- If `DATABASE_URL` is missing, the app falls back to a temporary SQLite file that disappears on redeploy. That is only for a quick look.
- Keep `DEMO_MODE=1`. Do not enter real patient data until ethics clearance and MRRH authorisation are in place and a locally validated model replaces this demonstration model.
- Free (Hobby) Vercel plans are meant for personal and non-commercial use.
