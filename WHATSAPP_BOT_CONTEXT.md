# WhatsApp Shared Expenses Bot

This file documents the current WhatsApp bot design and implementation context for the shared-expenses assistant.

Important:

- This is documentation only.
- It does not change or integrate with the current web app automatically.
- It exists so future work can reuse the bot logic without affecting the current Flask + Supabase + Vercel site.

## Overview

The bot is a WhatsApp-based Splitwise-style assistant for shared expenses.

Main capabilities:

- create expense groups
- add and remove members
- register expenses
- split costs automatically
- transcribe voice notes
- analyze receipt images
- calculate balances
- calculate optimal settlement transfers
- notify group members when a new expense is registered

## Current Bot Stack

- WhatsApp bot runtime: Kapso Automation Canvas
- Database: Cloudflare D1 (SQLite)
- Serverless functions: Cloudflare Workers
- LLM agent: Gemini 2.5 Flash
- Audio transcription: OpenAI Whisper

## Database Schema

### `groups`

```sql
CREATE TABLE groups (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT,
  created_by_phone TEXT,
  currency TEXT DEFAULT 'ARS',
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### `group_members`

```sql
CREATE TABLE group_members (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  group_id INTEGER,
  phone_number TEXT,
  display_name TEXT,
  added_at TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(group_id, phone_number)
);
```

### `expenses`

```sql
CREATE TABLE expenses (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  group_id INTEGER,
  description TEXT,
  amount NUMERIC,
  paid_by_member_id INTEGER,
  expense_date TEXT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### `expense_shares`

```sql
CREATE TABLE expense_shares (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  expense_id INTEGER,
  member_id INTEGER,
  share_amount NUMERIC
);
```

## Kapso Workflow

Workflow name:

- `Bot de Gastos Compartidos`

Workflow id:

- `4cd765ec-cd73-4311-a78a-b9b60bdb7e71`

Status:

- `active`

Flow:

```text
start
  -> function: transcribe-audio
  -> agent: AI Agent (gemini-2.5-flash)
```

### `transcribe-audio`

Purpose:

- detect whether the inbound WhatsApp message is a voice note
- transcribe it automatically with Whisper
- save the result in workflow vars

Outputs:

- `vars.transcription`
- `vars.original_was_audio`

### AI Agent

Model:

- `google/gemini-2.5-flash`

Temperature:

- `0.0`

Max iterations:

- `80`

## Tools Available To The Agent

Default tools:

- `send_notification_to_user`
- `send_media`
- `get_execution_metadata`
- `get_whatsapp_context`
- `get_current_datetime`
- `save_variable`
- `get_variable`
- `ask_about_file`
- `enter_waiting`
- `complete_task`
- `handoff_to_human`

Custom function tools:

1. `create_group`
2. `list_user_groups`
3. `list_group_members`
4. `add_member`
5. `remove_member`
6. `create_expense`
7. `list_expenses`
8. `edit_expense`
9. `delete_expense`
10. `calculate_balances`
11. `calculate_settlement`
12. `add_members_from_contacts`

## Cloudflare Worker Functions

The bot currently relies on these Workers:

### 1. `create-group`

Creates a new group and automatically adds the creator as the first member.

Inputs:

- `group_name`
- `currency` optional, default `ARS`
- `creator_name` optional

### 2. `list-user-groups`

Lists all groups where the current phone number participates.

Input source:

- current WhatsApp user phone from execution context

### 3. `list-group-members`

Lists all members for a given group.

Inputs:

- `group_id`

### 4. `add-member`

Adds a member to an existing group.

Inputs:

- `group_id`
- `phone_number`
- `display_name`

### 5. `remove-member`

Removes a member from a group.

Inputs:

- `group_id`
- `phone_number`

### 6. `create-expense`

Creates an expense and splits it among all members or a custom subset.

Inputs:

- `group_id`
- `description`
- `amount`
- `paid_by_phone`
- `split_with` optional array of phone numbers

Behavior:

- if `split_with` is empty, split across the whole group
- creates both the expense row and the corresponding `expense_shares`

### 7. `list-expenses`

Lists expenses in a group.

Inputs:

- `group_id`

### 8. `edit-expense`

Edits description and/or amount of an existing expense.

Inputs:

- `expense_id`
- `description` optional
- `amount` optional

Current behavior:

- if amount changes, it recalculates shares equally across the existing split rows

### 9. `delete-expense`

Deletes an expense and its shares.

Inputs:

- `expense_id`

### 10. `calculate-balances`

Computes, per member:

- how much they paid
- how much they owe
- their net balance

Inputs:

- `group_id`

### 11. `calculate-settlement`

Computes optimal transfers to settle all debts.

Inputs:

- `group_id`

Output:

- list of transfers `{ from, to, amount }`

### 12. `transcribe-audio`

Detects inbound audio and transcribes it with OpenAI Whisper.

Requires:

- `OPENAI_API_KEY`

Behavior:

- uses the last inbound WhatsApp message
- if it is audio, downloads media and sends it to Whisper
- stores the resulting transcript in workflow vars

### 13. `add-members-from-contacts`

Adds members directly from shared WhatsApp contacts.

Inputs:

- `group_id`

Behavior:

- detects `contacts` message type
- extracts contact name and phone number
- inserts each contact into `group_members`

## Trigger

Trigger type:

- `inbound_message`

WhatsApp config:

- `Splitai (+1137531972776863)`

Status:

- `active`

## Agent Behavior Summary

The WhatsApp agent is configured to:

- use `vars.transcription` when a message was audio
- detect shared contacts automatically
- analyze ticket images through `ask_about_file`
- ask for missing details when needed
- keep answers short and informal
- use Argentine Spanish tone
- send notifications after each created expense

Examples of expected behavior:

- if the user says `creá un grupo cenas`, call `create_group`
- if the user shares contacts, call `add_members_from_contacts`
- if the user says `Juan pagó 30000 de cena`, resolve the group, payer, and split, then call `create_expense`
- if the user asks `cómo vamos`, call `calculate_balances`
- if the user asks `quién le debe a quién`, call `calculate_settlement`

## Phone Number Convention

Phone numbers are stored in international format.

Argentina example:

- `+5491123456789`

Rule:

- if the user sends a local number, normalize it to `+549...`

## Notifications

After each successful expense creation, the agent should:

1. fetch group members
2. notify everyone except the user who created the expense
3. send a short message indicating:
   - who paid
   - how much
   - concept
   - how much the recipient owes

## Relationship With The Current Web App

The current web app in this repository uses:

- Flask
- Supabase Postgres
- Vercel

The WhatsApp bot documented here uses:

- Kapso
- Cloudflare Workers
- Cloudflare D1

So, right now:

- they do not share runtime
- they do not share database
- they do not share authentication

This file exists as integration context only.

## Suggested Future Integration Paths

Possible options:

1. Expose a shared REST API and make both bot and web consume the same backend.
2. Move the web app to Cloudflare Pages/Workers + D1 to match the bot stack.
3. Keep both stacks separate and add synchronization between Supabase and D1.
4. Introduce a unified identity layer linking WhatsApp phone numbers with web users.

Recommended long-term direction from the original notes:

- Cloudflare Pages + D1 binding for a shared fullstack Cloudflare architecture

## Important Constraint

This document should be treated as reference material for future integration work.

It should not be assumed that:

- the bot code runs inside this Flask app
- these tables already exist in Supabase exactly as written
- these functions are deployed from this repository

The goal is to preserve the bot specification without affecting the current web implementation.
