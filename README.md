# Zun Synthesis Academy

## Local setup (PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Create the first administrator. This command prompts for the email and password and stores only a PBKDF2 password hash:

```powershell
python -m app.create_admin
```

Set a private JWT secret for the server process, then start FastAPI:

```powershell
$env:JWT_SECRET = (py -c "import secrets; print(secrets.token_urlsafe(48))")
uvicorn app.main:app --reload
```

The generated JWT secret is specific to that PowerShell process. Set it again when starting a new process, or configure a persistent secret in your deployment environment. Set `DATABASE_URL` to a PostgreSQL SQLAlchemy URL such as `postgresql+psycopg://user:password@host/database` to use PostgreSQL instead of the default SQLite database.

The site is at `http://127.0.0.1:8000`; interactive API documentation is at `http://127.0.0.1:8000/docs`. Log in with `POST /api/admin/login` using JSON `{ "email": "...", "password": "..." }`, then use the returned bearer token for `/api/admin/content` and `/api/admin/analytics` endpoints.

The course dashboard is available at `http://127.0.0.1:8000/admin`. It supports course creation, edits, lifecycle status changes, learner progress tracking, certificate issuance at 100% completion, analytics, and financial aid approval/rejection. Learner accounts can be created through the site's Join Now form or `POST /api/students/register`. Course enrollment requires a learner token. Paid course enrollment uses a mock confirmation only; it is not a payment processor and stores no card details.

### Admin roles, course media, and production configuration

The first administrator created by `python -m app.create_admin` is the Super Admin. On an existing database, startup promotes the first admin only when no Super Admin exists. Only that role can open **Manage admins** or use `GET/POST /api/admin/users` and `PATCH /api/admin/users/{id}`; staff admins can manage courses and review learners but cannot create or disable admin accounts. Admin passwords must be at least 12 characters, and the final active Super Admin cannot be disabled. Existing database installations receive additive columns for these roles and course pricing fields at startup.

The course editor supports basic rich text, links, uploaded images, and YouTube/Vimeo embeds. Course HTML is sanitized on write and read; the sanitizer uses an allowlist to remove unsafe markup and attributes ([nh3 documentation](https://nh3.readthedocs.io/en/stable/index.html)). Image uploads are re-encoded as WebP and saved under `MEDIA_UPLOAD_DIR` (default `app/static/uploads`), served at `/uploads/`. Configure this variable to a persistent volume in production. Allowed upload formats are JPEG, PNG, and WebP, with an 8 MB upload limit. Course prices are integer minor units in the API and entered in major units in the dashboard; `price_cents` remains the effective enrollment price for compatibility, while regular and offer prices are separately available in course responses.

For a public deployment, configure `JWT_SECRET` with a persistent random secret of at least 32 characters, set `DATABASE_URL` to PostgreSQL, set `ALLOWED_HOSTS` to comma-separated public hostnames (for example `academy.example.com,www.academy.example.com`), and set `MEDIA_UPLOAD_DIR` to persistent storage. Set `FORCE_HTTPS=true` when the app directly receives HTTPS or your reverse proxy forwards the original HTTPS scheme correctly. Terminate TLS at the edge, restrict database access, and keep the JWT secret and database credentials in the hosting provider's secret manager. The API is same-origin with the site and does not enable permissive cross-origin access.

Course image upload endpoint: authenticated `POST /api/admin/media/images` using multipart field `file`. The editor's formatted descriptions allow safe links, images, and YouTube/Vimeo iframe embeds; arbitrary scripts, event handlers, and third-party iframe hosts are stripped.

Course APIs include public `GET /api/courses`, admin `GET/POST /api/admin/courses`, `PUT/PATCH/DELETE /api/admin/courses/{id}`, learner `POST /api/courses/{id}/enroll`, and learner `POST /api/courses/{id}/financial-aid`. Admin review uses `GET /api/admin/financial-aid` and `PATCH /api/admin/financial-aid/{id}` with `status` set to `approved` or `rejected`. Learners read `/api/students/me/dashboard`; administrators set progress with `PATCH /api/admin/enrollments/{id}/progress`. Certificates are issued at 100%, verifiable at `/api/certificates/{code}`, and downloadable from the authenticated student dashboard. Mock invoice history and pending mock checkouts are also available in the dashboard.

Content is stored as JSON payloads by kind (`program`, `stat`, or other content types). Program payloads support `title`, `description`, `icon`, `accent`, `image_url`, `image_alt`, `video_url`, and `external_links`. Stat payloads support `value` and `label`. The public page reads program and stat content from the API and retains its original hand-authored markup if the API cannot be reached.

Visit analytics stores only the page path and server timestamp. It does not store visitor IP addresses, cookies, user agents, or account identifiers. Administrators can read rolling hourly/daily aggregates and recent page paths from `GET /api/admin/analytics`.
