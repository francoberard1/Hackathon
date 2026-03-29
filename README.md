# SplitIA Hackathon MVP

SplitIA is a beginner-friendly Flask app to split group expenses.

Current goals:
- Keep the app working locally with Flask
- Keep architecture simple (Flask + HTML/CSS/JS)
- Prepare a clean path to Supabase/Postgres later
- Prepare a clean path to Vercel deployment later

## 1. Run Locally (Current MVP)

From project root, move into the app folder:

	cd splitia

Install dependencies:

	pip install -r requirements.txt

Run Flask app:

	python app.py

Open in browser:

	http://127.0.0.1:5000

## 2. Current Architecture (Simple and Clean)

- Route logic: `splitia/app.py`
  - Handles HTTP requests and template rendering.
- Business logic:
  - `splitia/logic/balances.py` for balance calculations
  - `splitia/logic/settlement.py` for settlement transactions
- Data access logic: `splitia/logic/data_access.py`
  - Uses in-memory dictionaries today.
  - This is the main file to replace later with Supabase/Postgres queries.
- Domain-facing model API: `splitia/logic/models.py`
  - Routes and business logic call this layer.
  - Internally delegates storage operations to data access layer.

This separation is intentional so migration to a database does not require a full rewrite.

## 3. SQL Schema for Future Supabase/Postgres

Prepared SQL files:
- `splitia/database/schema.sql`
- `splitia/database/seed.sql`

Tables included:
- groups
- users
- expenses
- expense_shares

How it maps to current local model:
- Local `groups` dict -> SQL table `groups`
- Local `users` dict -> SQL table `users`
- Local `expenses` dict -> SQL table `expenses`
- Local `expense_shares` dict -> SQL table `expense_shares`

So the app logic is already aligned with a relational model.

## 4. Environment Variables

Template file:
- `splitia/.env.example`

Key variables:
- `SECRET_KEY`
- `GEMINI_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`

For local development, app uses a safe default secret if `.env` is missing.
For production, set a real `SECRET_KEY`.
For the receipt upload flow, set `GEMINI_API_KEY` in `splitia/.env` or export it in your shell before starting the app.

## 5. Supabase CLI Workflow (Later)

Prepared folder:
- `splitia/supabase/`
- `splitia/supabase/migrations/20260328000000_init_placeholder.sql`

When you are ready, run from `splitia` folder:

	supabase init
	supabase start

Then place real migrations in:

	supabase/migrations/

You can start from `database/schema.sql` and adapt into migration files.

Important:
- No live Supabase connection is required yet.
- Current app still runs fully local/in-memory.

## 6. Vercel CLI Deployment Workflow (Later)

Prepared file:
- `splitia/vercel.json`

The Flask app exports a top-level `app` object in `splitia/app.py`, which Vercel can use.

When you are ready, run from `splitia` folder:

	vercel login
	vercel

Optional production deploy:

	vercel --prod

## 7. Core Features Preserved

Current MVP features remain:
- Groups
- Users
- Expenses
- Balances
- Settlements

## 8. Quick Command List

From `splitia` folder:

	pip install -r requirements.txt
	python app.py
	supabase init
	supabase start
	vercel login
	vercel
