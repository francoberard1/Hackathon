# Supabase CLI Notes

This folder is prepared for future Supabase CLI usage.

## Where migrations will go
When you run `supabase init`, the CLI usually creates:
- `supabase/config.toml`
- `supabase/migrations/`

In this project, you can keep SQL migration files in:
- `supabase/migrations/`

You already have base SQL in `database/schema.sql` and `database/seed.sql`.
You can copy/adapt those into migration files later.
