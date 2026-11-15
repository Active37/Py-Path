# PyPath

**Your path to becoming a developer.**

PyPath is a responsive Django learning platform for people learning Python and web development. It combines guided lessons, practice, progress tracking, and an AI programming tutor in one app.

## Features

- **Guided courses:** 140+ lessons across Python, Java, object-oriented Python, JavaScript, and HTML/CSS.
- **Java OOP path:** 36 lessons from first program and types through polymorphism, design patterns, concurrency, and an object-oriented capstone.
- **Practice and review:** lesson examples and exercises, saved private lesson-specific active-recall checks, track quizzes, hints, bookmarks, and notes.
- **AI tutor:** lesson-aware programming help powered by an OpenAI-compatible chat-completions API, including Gemini.
- **Progress tracking:** completed lessons, daily goals, streaks, XP, badges, and an activity calendar.
- **Projects and careers:** guided project milestones, assignments, study groups, community discussions, and career practice.
- **Certificates:** earn a certificate by completing a course and passing its final assessment.
- **Browser playground:** preview HTML, CSS, and JavaScript in a sandboxed iframe.
- **Installable web app:** install PyPath from supported browsers; the cached app shell and offline page are available without a connection.

Learner Python and Java code is **not** executed on the Django server. Server-side code execution is available only when an isolated, authenticated Judge0-compatible service is configured. The browser playground is for HTML, CSS, and JavaScript only; saved playground projects stay in browser storage.

## Technology

- Python 3.12+
- Django 5.2
- PostgreSQL (Neon-supported)
- WhiteNoise for static files
- Gemini or another OpenAI-compatible chat-completions provider
- Render Blueprint for optional web hosting

The app is rendered by Django; it does not have a separate React frontend or an `npm run build` step. The npm manifest is for Neon configuration tooling.

## Run locally

### Requirements

- Python 3.12 or newer
- PostgreSQL and an existing database

### Setup

In PowerShell, from the project directory:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and set `DATABASE_URL` to your PostgreSQL connection string. For example, a local development database might use:

```dotenv
DATABASE_URL=postgresql://postgres:your-password@localhost:5432/pypath
```

Set `AI_API_KEY` if you want to use the AI tutor. Never commit `.env` or share its contents.

Python and Java execution is optional until you configure the self-hosted Judge0 service below.

Create the schema, optionally load the starter catalog, and run Django:

```powershell
python manage.py migrate
python manage.py seed_courses
python manage.py runserver
```

Open <http://127.0.0.1:8000/>.

> **Note:** `seed_courses` refreshes starter course content. Use it for an empty development database. The deployment uses `seed_courses --missing-only`, which adds missing courses and repairs missing lessons, assessments, and assignments while preserving existing course and lesson edits.

## Accounts

New accounts require an email address and password. Different accounts may use the same username; use your email address to sign in. Existing accounts without an email can continue signing in with their username until an email address is added.

## AI tutor

Set these variables in `.env`:

```dotenv
AI_API_BASE_URL=https://generativelanguage.googleapis.com/v1beta
AI_API_KEY=your-gemini-api-key
AI_MODEL=gemini-flash-latest
AI_API_TIMEOUT=60
```

`AI_API_TIMEOUT` is the maximum wait in seconds for the provider (default 60). Restart Django after changing environment variables. Set either `AI_API_KEY` or `GEMINI_API_KEY` on the server; `AI_API_KEY` takes precedence. Keep API keys out of browser code and GitHub. Tutor hints and quizzes use course material and do not require an AI API key.

## Run tests

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test tutor
```

Tests create and destroy a separate test database. Do not configure production credentials as the test database.

## Deploy with Neon and Render

PyPath serves the UI, backend, and static assets from one Django web service. Neon provides PostgreSQL; Render runs the web app. The repository includes [render.yaml](render.yaml) as a Render Blueprint.

1. Push the project, including `render.yaml`, to GitHub. Ensure `.env` is **not** tracked.
2. In Render, choose **New → Blueprint**, connect the repository, and apply the Blueprint.
3. Configure the service environment variables:
   - `DATABASE_URL`: Neon’s **pooled** PostgreSQL connection URL for app requests.
   - `DATABASE_URL_UNPOOLED`: Neon’s **direct** PostgreSQL connection URL for migrations and seeding.
   - `AI_API_KEY` or `GEMINI_API_KEY`: your Gemini API key. `AI_API_KEY` takes precedence if both are set.
   - `DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_EMAIL`, and `DJANGO_SUPERUSER_PASSWORD`: set all three in Render’s environment settings to bootstrap the first admin account.
4. Let Render generate `DJANGO_SECRET_KEY`. The Blueprint sets `DJANGO_DEBUG=0`; Django uses the Render hostname automatically.
5. Review the build logs. When the deployment succeeds, open the Render service URL and test the site.

The build collects static assets, applies migrations with the direct database URL, optionally creates the initial admin account, and adds missing starter courses and lessons without overwriting existing course content. The admin bootstrap is skipped if all three `DJANGO_SUPERUSER_*` values are unset, and it never changes an existing superuser's password. After creation, you can remove `DJANGO_SUPERUSER_PASSWORD` from Render; the username and email can remain set, and later builds leave that existing superuser unchanged. Never put a real password in `.env.example` or commit it to Git.

Sign in at `/admin/` to review learner accounts, admin actions, and read-only learning activity. The admin site can display private learner submissions and tutor conversations, so limit superuser access to trusted staff. Application and HTTP request logs are sent to the Render service's **Logs** page. Request records include the route, method, status, duration, and signed-in user's ID, username, and email; they do not include request bodies, query strings, passwords, API keys, or client IP addresses. Local data must be restored into Neon before deployment if it has not already been migrated. Render and Neon free-tier quotas and availability can change; free services may sleep or have limited backups and should not be treated as a production uptime guarantee.

The Gemini tutor uses the native `generateContent` API. Set `AI_API_BASE_URL` to `https://generativelanguage.googleapis.com/v1beta` (or to a full model endpoint ending in `:generateContent`) and `AI_MODEL` to the model name, such as `gemini-flash-latest`. Set `AI_API_KEY` or `GEMINI_API_KEY` in Render; provider/configuration failures appear in the tutor response and Render logs. The key is sent only in the server-to-server `X-goog-api-key` header and is never sent to the browser.

## Self-hosted Python code runner

PyPath sends Python submissions from Django to a separate Judge0 CE instance; it never executes learner code inside the web process. The repository includes a Docker Compose deployment in [`infra/judge0`](infra/judge0).

1. Provision a dedicated, current Linux host for Judge0. Judge0 requires privileged containers for its Isolate sandbox; do not run it on the Django host or alongside databases or services containing sensitive data.
2. Copy the files in `infra/judge0` to that host and run these commands in their directory:

   ```sh
   cp .env.example .env
   cp judge0.conf.example judge0.conf
   ```

   Replace all sample passwords and the Judge0 authentication token with independently generated secrets. Set `JUDGE0_DOMAIN` in `.env` to a DNS name pointing at the host. Allow inbound ports 80 and 443 for Caddy; do not expose Judge0's port 2358, PostgreSQL, or Redis to the public internet.
3. Start the services with `docker compose up -d`. Caddy obtains TLS for the configured domain and proxies to Judge0; the Judge0 API itself is not published directly. Check `docker compose logs` and verify `https://<JUDGE0_DOMAIN>/system_info` with the `X-Auth-Token` header set to your Judge0 token.
4. Configure Django/Render with:
   - `CODE_RUNNER_URL=https://<JUDGE0_DOMAIN>`
   - `CODE_RUNNER_API_KEY` equal to the Judge0 `AUTHN_TOKEN`
   - `CODE_RUNNER_LANGUAGE_ID=71` for the configured Judge0 Python runtime
   - `CODE_RUNNER_JAVA_LANGUAGE_ID=62` for the configured Judge0 Java runtime
   - `CODE_RUNNER_TIMEOUT=30`
5. Keep the token only in Django's server-side environment. Never put it in templates, browser JavaScript, or public Render variables. The code-runner API accepts only the limits enforced by PyPath; network access, callbacks, extra files, custom compiler options, and command-line arguments are disabled in the Judge0 example configuration.

The bundled Judge0 setup pins a release containing the security fixes documented by Judge0. Keep Judge0 and its host patched, restrict host access, and back up the Judge0 database volume. See [Judge0's deployment guidance](https://github.com/judge0/judge0/blob/master/CHANGELOG.md#deployment-procedure) before production use.

For a custom domain, add its hostname to `DJANGO_ALLOWED_HOSTS` and its HTTPS origin to `DJANGO_CSRF_TRUSTED_ORIGINS` in Render.

## Security and privacy

- Store database URLs, Django secrets, and AI keys only in local ignored environment files or your hosting provider’s secret settings.
- Store the initial admin password only in a local ignored `.env` or Render secret setting; `.env.example` contains blank placeholders.
- Use HTTPS and a unique `DJANGO_SECRET_KEY` in production.
- The browser playground sandbox restricts access to the parent page and blocks external resource loading and form submission.
- Private learner notes, tutor conversations, and quiz answers are not shown on public profiles.
- Public profiles and leaderboard listings are opt-in.
- Keep any code-execution service isolated from the Django app and database.

See [`.env.example`](.env.example) for the environment-variable names and [Django’s deployment checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/) before running a production service.
