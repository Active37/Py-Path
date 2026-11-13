# PyPath

**Your path to becoming a developer.**

PyPath is a responsive Django learning platform for people learning Python and web development. It combines guided lessons, practice, progress tracking, and an AI programming tutor in one app.

## Features

- **Guided courses:** 106 lessons across Python, object-oriented Python, JavaScript, and HTML/CSS.
- **Practice and review:** lesson examples and exercises, quizzes, hints, bookmarks, and private lesson notes.
- **AI tutor:** lesson-aware programming help powered by an OpenAI-compatible chat-completions API, including Gemini.
- **Progress tracking:** completed lessons, daily goals, streaks, XP, badges, and an activity calendar.
- **Projects and careers:** guided project milestones, assignments, study groups, community discussions, and career practice.
- **Certificates:** earn a certificate by completing a course and passing its final assessment.
- **Browser playground:** preview HTML, CSS, and JavaScript in a sandboxed iframe.
- **Installable web app:** install PyPath from supported browsers; the cached app shell and offline page are available without a connection.

Learner Python code is **not** executed on the Django server. Server-side code execution is available only when an isolated, authenticated Judge0-compatible service is configured. The browser playground is for HTML, CSS, and JavaScript only; saved playground projects stay in browser storage.

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

Create the schema, optionally load the starter catalog, and run Django:

```powershell
python manage.py migrate
python manage.py seed_courses
python manage.py runserver
```

Open <http://127.0.0.1:8000/>.

> **Note:** `seed_courses` refreshes the starter course content. Use it for an empty development database. The deployment uses `seed_courses --if-empty` so it does not overwrite an existing catalog.

## AI tutor

Set these variables in `.env`:

```dotenv
AI_API_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
AI_API_KEY=your-gemini-api-key
AI_MODEL=gemini-3.5-flash-lite
```

Restart Django after changing environment variables. Keep API keys on the server; do not expose them in browser code or commit them to GitHub. Tutor hints and quizzes use course material and do not require an AI API key.

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
   - `AI_API_KEY`: your Gemini API key.
4. Let Render generate `DJANGO_SECRET_KEY`. The Blueprint sets `DJANGO_DEBUG=0`; Django uses the Render hostname automatically.
5. Review the build logs. When the deployment succeeds, open the Render service URL and test the site.

The build collects static assets, applies migrations with the direct database URL, and seeds the starter catalog only if there are no courses. Local data must be restored into Neon before deployment if it has not already been migrated. Render and Neon free-tier quotas and availability can change; free services may sleep or have limited backups and should not be treated as a production uptime guarantee.

For a custom domain, add its hostname to `DJANGO_ALLOWED_HOSTS` and its HTTPS origin to `DJANGO_CSRF_TRUSTED_ORIGINS` in Render.

## Security and privacy

- Store database URLs, Django secrets, and AI keys only in local ignored environment files or your hosting provider’s secret settings.
- Use HTTPS and a unique `DJANGO_SECRET_KEY` in production.
- The browser playground sandbox restricts access to the parent page and blocks external resource loading and form submission.
- Private learner notes, tutor conversations, and quiz answers are not shown on public profiles.
- Public profiles and leaderboard listings are opt-in.
- Keep any code-execution service isolated from the Django app and database.

See [`.env.example`](.env.example) for the environment-variable names and [Django’s deployment checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/) before running a production service.
