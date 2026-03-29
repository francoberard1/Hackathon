# SplitIA

SplitIA is a Splitwise-like expense management app built for HackITBA.

It helps groups track shared expenses, understand balances, and settle up faster.  
Its main differentiator is an AI-assisted flow that lets users:

- upload a receipt
- record an audio explanation of who consumed what
- automatically transform that into a structured expense draft
- review the final form before saving

Live demo: [https://splitia-alpha.vercel.app](https://splitia-alpha.vercel.app)

## Why this matters

Splitting a group dinner is usually annoying for two reasons:

1. someone has to transcribe the receipt
2. someone has to explain who consumed each item and do the math

SplitIA reduces that friction by combining:

- OCR-style receipt extraction
- audio transcription
- natural-language parsing
- automatic item assignment and split calculation

The backend remains the source of truth, and the user always keeps final control before persisting the expense.

## What the app does

### Core product

- create groups
- add members
- add expenses
- calculate balances
- generate settlement transactions

### AI-assisted expense entry

- upload a food receipt/ticket
- extract merchant, total, date, tax, tip, and line items
- record an audio note explaining:
  - who paid
  - who attended
  - who consumed specific items
  - who should receive the remainder
- automatically fill:
  - expense title
  - total amount
  - date
  - payer
  - participants
  - exact share amount per person

### Admin / product features

- archive groups instead of hard-deleting them
- edit persisted expenses
- delete expenses
- business stats on the home page
- group-level stats inside each group
- dark / light mode

## Demo flow recommended for judges

### 1. Open the home page

What to notice:

- active groups
- archived groups
- total platform spend
- minimal analytics panels at the bottom

### 2. Enter a group

What to notice:

- real member count
- balances
- expense list
- edit / delete expense actions
- group stats at the bottom

### 3. Add an expense with AI assistance

Recommended flow:

1. upload a receipt
2. verify that merchant, total and date autofill the form
3. record an audio like:

   `Este gasto lo pagó Franco. Facu tomó coca cola, Juaco tomó coca light, Franco comió dos trofie y el resto para Franco.`

4. verify that:
   - payer updates
   - ticket items get assigned to specific members
   - shares update automatically in the main expense form
5. edit anything manually if needed
6. save the expense

### 4. Check balances and settlements

The saved expense updates:

- balances
- group analytics
- settlement suggestions

## Architecture

Final architecture used in the project:

- Frontend: server-rendered HTML + JavaScript
- Backend: Flask
- Database: Supabase Postgres
- Deployment: Vercel

The backend is the source of truth.

## Tech stack

- Python
- Flask
- Supabase
- Vercel
- JavaScript
- HTML/CSS
- AssemblyAI
- Gemini

## AI pipeline

### Receipt pipeline

Receipt images are processed in the backend and normalized into a structured receipt draft.

The extraction aims to recover:

- merchant name
- subtotal
- tax
- tip
- total
- date
- extracted line items

### Audio pipeline

Audio is transcribed first, then parsed into structured expense data.

The parser currently supports patterns such as:

- `pagó X`
- `X pagó`
- `fuimos todos`
- explicit participant lists
- equal split
- fixed amount for one person plus remainder split
- explicit item consumption when a ticket is already loaded
- `el resto para X`
- relative dates like `hoy`, `ayer`, `anteayer`

### Ticket + audio combined mode

When a ticket already exists, the audio parser can use ticket items as context.

That enables flows like:

- `Facu tomó coca cola`
- `Juaco tomó coca light`
- `Franco comió dos trofie`
- `el resto para Franco`

The result is applied directly to:

- item assignment dropdowns
- share amounts in the main form

If no ticket is present, the original audio-only flow still works.

## Project structure

```text
Hackathon/
├── README.md
├── splitia/
│   ├── app.py
│   ├── requirements.txt
│   ├── database/
│   ├── logic/
│   │   ├── data_access.py
│   │   ├── models.py
│   │   ├── parser.py
│   │   ├── receipt_service.py
│   │   ├── receipt_review.py
│   │   ├── settlement.py
│   │   └── stats.py
│   ├── static/
│   ├── templates/
│   ├── supabase/
│   └── vercel.json
```

## Important routes

UI routes:

- `/`
- `/group/<group_id>`
- `/add_group`
- `/add_user/<group_id>`
- `/add_expense/<group_id>`
- `/expense/<expense_id>/edit`
- `/settle/<group_id>`

Mutation routes:

- `POST /group/<group_id>/delete`
- `POST /expense/<expense_id>/delete`

AI routes:

- `POST /api/receipt/draft`
- `POST /api/audio/transcribe`
- `POST /api/audio/parse`

## Data model

Main entities:

- groups
- users
- expenses
- expense_shares

Groups are archived logically instead of being hard-deleted, so historical analytics can be preserved.

## How to run locally

From the repo root:

```bash
cd splitia
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open:

[http://127.0.0.1:5001](http://127.0.0.1:5001)

## Environment variables

The app supports a `.env` file in `/Users/facundotrueba/Documents/GitHub/Hackathon/splitia/.env`.

Typical variables:

- `SECRET_KEY`
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `ASSEMBLYAI_API_KEY`
- `GEMINI_API_KEY`
- `ASSEMBLYAI_LLM_MODEL`

See:

- [/Users/facundotrueba/Documents/GitHub/Hackathon/splitia/.env.example](/Users/facundotrueba/Documents/GitHub/Hackathon/splitia/.env.example)

## What was prioritized

For the hackathon, we prioritized:

- end-to-end usability
- real product feel
- AI-assisted expense entry
- explainable, editable final form
- focused changes over heavy refactors

## Known limitations

- Natural-language parsing is heuristic-heavy and still depends on transcript quality.
- Ticket item assignment works best when item names are reasonably legible.
- Some very ambiguous audio phrasings may still require manual correction.
- The current frontend is optimized for speed and demo clarity over perfect polish.

## Team angle / business angle

SplitIA is designed not only as a user tool but also as a product with operational visibility:

- business snapshot on the home screen
- group-level usage analytics
- historical group archival instead of destructive deletion

That leaves room for future analytics like:

- retention by group
- spend over time
- archived-group lifecycle analysis
- AI-assisted usage adoption

## Business model

Our business model combines **two complementary revenue streams**.

The first, and main one, is allowing users to **settle debts directly inside the product** through a payment integration such as **Mercado Pago**, charging a **0.99% fee per transaction**. Since part of that percentage would also be absorbed by the payment processor, the estimated net margin for SplitIA would be around **0.19% to 0.20%**, so the business logic is not based on high margin per operation, but on scaling usage volume across many groups and settlements.

The second revenue stream appears when users decide **not** to pay inside the application and prefer to settle the debt outside the platform. In that case, SplitIA can monetize that exit point through **ads or sponsored placements**, generating revenue even when the transaction is completed externally.

Why this model makes sense for us:

- it keeps the barrier to entry low, since the user still has the option to pay outside the app
- it monetizes the moment of highest value when a debt is actually resolved
- Mercado Pago is a credible and familiar path for users in Argentina
- even users who do not convert to in-app payments can still be monetized through the external payment flow
- the model is designed to scale with real usage, not only with registrations

For this reason, the business model we are defending is a **mixed monetization strategy**: low-fee in-app payments as the core, and ads as a complementary revenue stream.

## Submission note

This repository contains a working hackathon implementation, not a mockup.

The core flows that matter most are already functional:

- shared expense management
- AI-assisted receipt entry
- audio-based split explanation
- automatic per-person share calculation
- persistent data in Supabase
- production deployment on Vercel
