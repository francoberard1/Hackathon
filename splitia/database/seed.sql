-- Sample data for local SQL tests (PostgreSQL/Supabase compatible).
-- Run after schema.sql.

INSERT INTO groups (id, name) VALUES
    (1, 'Hackathon Team Trip');

INSERT INTO users (id, group_id, name) VALUES
    (1, 1, 'Alice'),
    (2, 1, 'Bob'),
    (3, 1, 'Carol');

INSERT INTO expenses (id, group_id, payer_id, description, total_amount) VALUES
    (1, 1, 1, 'Dinner', 60.00),
    (2, 1, 2, 'Taxi', 30.00);

INSERT INTO expense_shares (expense_id, user_id, amount) VALUES
    -- Dinner split equally among 3
    (1, 1, 20.00),
    (1, 2, 20.00),
    (1, 3, 20.00),
    -- Taxi split equally among 3
    (2, 1, 10.00),
    (2, 2, 10.00),
    (2, 3, 10.00);

-- Keep auto-increment values in sync after explicit IDs
SELECT setval('groups_id_seq', COALESCE((SELECT MAX(id) FROM groups), 1));
SELECT setval('users_id_seq', COALESCE((SELECT MAX(id) FROM users), 1));
SELECT setval('expenses_id_seq', COALESCE((SELECT MAX(id) FROM expenses), 1));
SELECT setval('expense_shares_id_seq', COALESCE((SELECT MAX(id) FROM expense_shares), 1));
