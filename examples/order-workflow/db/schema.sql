CREATE TYPE order_status AS ENUM ('draft', 'submitted', 'paid', 'cancelled');
CREATE TYPE payment_status AS ENUM ('new', 'processing', 'confirmed', 'rejected', 'outcome_unknown');

CREATE TABLE app_user (
    id uuid PRIMARY KEY,
    display_name text NOT NULL
);

CREATE TABLE orders (
    id uuid PRIMARY KEY,
    owner_id uuid NOT NULL REFERENCES app_user(id),
    status order_status NOT NULL DEFAULT 'draft',
    total_minor bigint NOT NULL CHECK (total_minor >= 0),
    currency text NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
    payment_id uuid,
    version bigint NOT NULL DEFAULT 1 CHECK (version >= 1),
    created_at timestamptz NOT NULL DEFAULT transaction_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT transaction_timestamp(),
    CONSTRAINT inv_paid_order_payment_reference CHECK (
        (status = 'paid' AND payment_id IS NOT NULL)
        OR
        (status <> 'paid' AND payment_id IS NULL)
    )
);

CREATE TABLE payments (
    id uuid PRIMARY KEY,
    order_id uuid NOT NULL REFERENCES orders(id),
    status payment_status NOT NULL DEFAULT 'new',
    provider_operation_id text NOT NULL UNIQUE,
    amount_minor bigint NOT NULL CHECK (amount_minor >= 0),
    currency text NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
    version bigint NOT NULL DEFAULT 1 CHECK (version >= 1),
    created_at timestamptz NOT NULL DEFAULT transaction_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT transaction_timestamp()
);

ALTER TABLE orders
    ADD CONSTRAINT fk_orders_payment
    FOREIGN KEY (payment_id) REFERENCES payments(id);

CREATE UNIQUE INDEX inv_one_nonterminal_payment_per_order
    ON payments(order_id)
    WHERE status IN ('new', 'processing', 'outcome_unknown');

CREATE TABLE outbox (
    id uuid PRIMARY KEY,
    topic text NOT NULL,
    aggregate_id uuid NOT NULL,
    idempotency_key text NOT NULL UNIQUE,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT transaction_timestamp(),
    published_at timestamptz
);

CREATE OR REPLACE FUNCTION assert_paid_order_invariant_for(target_order_id uuid)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
    target orders%ROWTYPE;
    matching_payment_exists boolean;
BEGIN
    SELECT * INTO target
    FROM orders
    WHERE id = target_order_id;

    IF NOT FOUND OR target.status <> 'paid' THEN
        RETURN;
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM payments p
        WHERE p.id = target.payment_id
          AND p.order_id = target.id
          AND p.status = 'confirmed'
          AND p.amount_minor = target.total_minor
          AND p.currency = target.currency
    ) INTO matching_payment_exists;

    IF NOT matching_payment_exists THEN
        RAISE EXCEPTION 'paid order % lacks a matching confirmed payment', target.id
            USING ERRCODE = '23514',
                  CONSTRAINT = 'inv_paid_order_requires_matching_payment';
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION enforce_order_payment_invariant()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_TABLE_NAME = 'orders' THEN
        PERFORM assert_paid_order_invariant_for(CASE WHEN TG_OP = 'DELETE' THEN OLD.id ELSE NEW.id END);
    ELSE
        PERFORM assert_paid_order_invariant_for(CASE WHEN TG_OP = 'DELETE' THEN OLD.order_id ELSE NEW.order_id END);
        IF TG_OP = 'UPDATE' AND OLD.order_id IS DISTINCT FROM NEW.order_id THEN
            PERFORM assert_paid_order_invariant_for(OLD.order_id);
        END IF;
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;

CREATE CONSTRAINT TRIGGER inv_paid_order_after_order_change
AFTER INSERT OR UPDATE OR DELETE ON orders
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION enforce_order_payment_invariant();

CREATE CONSTRAINT TRIGGER inv_paid_order_after_payment_change
AFTER INSERT OR UPDATE OR DELETE ON payments
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION enforce_order_payment_invariant();
