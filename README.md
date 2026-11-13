# PyPath

PyPath is a Django learning platform for people learning Python and web development. Learners can create an account, follow 106 guided lessons across Python, JavaScript, and HTML/CSS, including 30 lessons each in JavaScript and HTML/CSS, take a focused 10-lesson object-oriented Python course, explore curated external learning resources, chat with a lesson-aware AI tutor, run Python practice code in a separate sandbox, and save lesson completion. Learners can also search courses and lessons, bookmark lessons, save private lesson notes, take scored learning-path quizzes, set a daily lesson goal, track their streak, and view a personal progress profile.

The courses cover Python fundamentals, object-oriented and advanced Python, JavaScript from language fundamentals through browser APIs and advanced patterns, and HTML/CSS from document structure through responsive, accessible production layouts. Hints and quizzes use course material; open-ended tutoring follows the current lesson language and requires an OpenAI-compatible chat-completions API.

Quiz questions are curated by learning path and are presented on lesson pages. Each submitted attempt is saved to the signed-in learner's profile. Daily goals count newly completed lessons; a lesson can only increase the daily count once because completion is unique per learner and lesson. Bookmarks and notes are private to each learner, and the profile lets learners choose a goal of 1–10 lessons per day.

Learners can earn badges and XP (10 points per completed lesson and 2 per correct quiz answer), review a 12-week activity calendar, plan study sessions for the current week, and track milestones in guided Python, JavaScript, and HTML/CSS projects. Lesson checklists are saved in the current browser. A signed-in learner can download a learning path as a self-contained HTML file for offline reading; private notes, tutor conversations, and account data are not included. Daily reminders are in-app prompts, not email or scheduled push notifications.

Public profiles and leaderboard listings are opt-in. When enabled, a public profile can show the learner's chosen display name (or username), lesson count, XP, and earned badges. Email, private notes, tutor messages, and quiz answers are never shown publicly. Learners can turn public sharing off at any time.

The browser playground runs HTML/CSS/JavaScript only inside a sandboxed iframe. The iframe has no same-origin access, blocks network/resource loading and form submission, and is not an execution service for Python or other server-side code. Saved playground projects use local browser storage; downloads are standalone HTML files. Do not run code you do not trust in your browser.

Learner code is never executed by Django. The code runner feature requires a separately deployed, isolated Judge0-compatible service. Do not point it at an untrusted service: submitted code and input are sent to the configured runner.

## Run locally

1. Install Python 3.10 or newer.
2. Install the project dependency:

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env`, edit `DATABASE_URL` to point to an existing PostgreSQL database named `pypath`, then create its schema and start the development server:

   ```powershell
   python manage.py migrate
   python manage.py seed_courses
   python manage.py runserver
   ```

4. Open http://127.0.0.1:8000 and create an account.

PostgreSQL is the only supported application database in development and production. Copy `.env.example` to `.env`, set a valid PostgreSQL `DATABASE_URL`, and ensure the named database already exists. Then run `python manage.py migrate` and `python manage.py seed_courses`. The seed command is idempotent, but rerunning it resets seeded entries to their starter content; it leaves additional records untouched. Never commit the connection string or its password. Migrations create or update the schema; they do not transfer records from another database.

## Learning, assessment, and community

Courses, modules, lessons, final-assessment questions, starter assignments, career prompts, and plan records are stored in the database. Staff manage content in Django admin. Assign a course instructor in the course admin to let that instructor review submissions for their course.

Learners can submit course assignments for instructor review, join or create study groups, post community discussions, and save private career-practice responses. Certificates are issued only after every lesson in a course is completed and its final assessment is passed; the certificate page provides a verification link and an owner-only PDF download.

Free-plan enrollment is stored locally. Premium pricing and payment processing are intentionally unavailable until a payment provider is configured; the app does not collect payment details or pretend to complete a purchase.

## Install PyPath

Use the **Install app** button in the site navigation. Browsers with native PWA installation show their install prompt; otherwise, the button opens device-specific instructions for installing from the browser menu or sharing to the home screen. PyPath provides 192px and 512px PWA icons plus an Apple touch icon. The offline app shell and friendly offline page are cached; lessons, account data, and other personalized pages still require a network connection. Service workers require HTTPS in production; localhost is supported for local development.

## Configure AI tutoring and code execution

Copy `.env.example` to `.env` in the project folder and replace the placeholder with your Gemini API key. Django loads `.env` automatically on startup. The `.env` file is ignored by Git. Never commit or share your real key.

You can keep the endpoint and model in `.env` too:

```dotenv
AI_API_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
AI_API_KEY=your-new-gemini-api-key
AI_MODEL=gemini-3.5-flash-lite
```

After editing `.env`, stop the current Django server with `Ctrl+C`, then run `python manage.py runserver` again from the project folder. Provider HTTP errors are shown in the tutor so invalid keys and unavailable model names are easier to diagnose.

For code execution, deploy your own isolated Judge0-compatible service and configure its base API URL. Set the language ID to one supported by that installation:

```powershell
$env:CODE_RUNNER_URL = "https://your-private-runner.example"
$env:CODE_RUNNER_API_KEY = "your-runner-api-key"
$env:CODE_RUNNER_LANGUAGE_ID = "71"
```

The code runner request applies CPU, wall-time, and memory limits. Keep the runner private, authenticated, and isolated from application data. Without these settings, the app returns a clear configuration error rather than executing code unsafely or pretending the feature is active.

Run the tests with:

```powershell
python manage.py test tutor
```

## Production

Before deploying, set a unique `DJANGO_SECRET_KEY`, set `DJANGO_DEBUG=0`, configure `DJANGO_ALLOWED_HOSTS` as a comma-separated list of hostnames, and set `DATABASE_URL` to a PostgreSQL connection string. The app refuses to start without PostgreSQL in every environment. Run `python manage.py migrate` and `python manage.py seed_courses` against the target database. Use HTTPS; do not use the development server in production.

## Free deployment (Render + Neon)

The included `render.yaml` deploys the Django app as a free Render web service and connects it to a Neon PostgreSQL database. The deployment builds static files, applies migrations, and seeds the starter catalog only if the database has no courses. Existing course edits are left untouched on later deploys.

1. Create a free Neon project and copy its pooled PostgreSQL connection string. Keep it private; do not paste it into chat or commit it.
2. Push this project to a private GitHub repository. The project folder must be a Git repository before Render can connect it; `.env`, local virtual environments, and collected static files are ignored.
3. In Render, create a **Blueprint** and connect the repository containing `render.yaml`. Choose the free plan.
4. When prompted, enter the Neon connection string as `DATABASE_URL` and your Gemini key as `AI_API_KEY`. Render generates `DJANGO_SECRET_KEY`; `DJANGO_DEBUG=0` is set by the Blueprint. The Render hostname is added to Django's allowed hosts automatically.
5. Wait for the build to complete, then open the Render URL and create a learner account.

This creates a fresh hosted database; local accounts, progress, and other PostgreSQL records are not copied. The course catalog is seeded automatically. To use a custom domain, add its hostname to `DJANGO_ALLOWED_HOSTS` and its HTTPS origin to `DJANGO_CSRF_TRUSTED_ORIGINS` in Render.

Free-tier caveats: Render's free web service sleeps after 15 minutes without traffic and can take about a minute to wake. Its filesystem is temporary, so app data must live in PostgreSQL. Neon Free is currently a permanent free plan, but has compute and storage quotas. Do not use Render's free PostgreSQL for this setup; Render documents that it expires after 30 days. These limits make this a hobby/demo deployment, not a production availability guarantee. See [Render's free service limits](https://render.com/docs/free) and [Neon's pricing](https://neon.com/pricing).
#   P y - P a t h  
 