CREATE TYPE shipment_status AS ENUM ('pending', 'in_transit', 'out_for_delivery', 'delivered', 'exception');
CREATE TYPE checkpoint_code AS ENUM ('in_transit', 'out_for_delivery', 'delivered', 'exception');

CREATE TABLE shipments (
    id uuid PRIMARY KEY,
    order_id uuid NOT NULL UNIQUE,
    status shipment_status NOT NULL DEFAULT 'pending',
    last_sequence bigint NOT NULL DEFAULT 0 CHECK (last_sequence >= 0),
    created_at timestamptz NOT NULL DEFAULT transaction_timestamp()
);

CREATE TABLE checkpoints (
    id uuid PRIMARY KEY,
    shipment_id uuid NOT NULL REFERENCES shipments(id),
    provider_event_id text NOT NULL,
    sequence_no bigint NOT NULL CHECK (sequence_no >= 0),
    code checkpoint_code NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT transaction_timestamp(),
    CONSTRAINT inv_checkpoint_event_once_per_shipment UNIQUE (shipment_id, provider_event_id)
);

CREATE INDEX idx_checkpoints_shipment_sequence ON checkpoints(shipment_id, sequence_no);

-- INV-SHIP-001's DB-level half: last_sequence must always equal the highest recorded
-- checkpoint's sequence_no (or 0 with none). Combined with the application-level guard
-- (only accept sequence_no > current last_sequence, evaluated under a row lock), this
-- fully enforces "checkpoints applied only in strictly increasing order."
CREATE OR REPLACE FUNCTION assert_shipment_sequence_matches_checkpoints(target_shipment_id uuid)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
    tracked bigint;
    highest bigint;
BEGIN
    SELECT last_sequence INTO tracked FROM shipments WHERE id = target_shipment_id;
    IF NOT FOUND THEN
        RETURN;
    END IF;

    SELECT COALESCE(MAX(sequence_no), 0) INTO highest FROM checkpoints WHERE shipment_id = target_shipment_id;

    IF tracked <> highest THEN
        RAISE EXCEPTION 'shipment % last_sequence (%) does not match highest recorded checkpoint sequence_no (%)',
            target_shipment_id, tracked, highest
            USING ERRCODE = '23514',
                  CONSTRAINT = 'inv_ship_last_sequence_matches_checkpoints';
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION enforce_shipment_sequence_invariant()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_TABLE_NAME = 'shipments' THEN
        PERFORM assert_shipment_sequence_matches_checkpoints(CASE WHEN TG_OP = 'DELETE' THEN OLD.id ELSE NEW.id END);
    ELSE
        PERFORM assert_shipment_sequence_matches_checkpoints(CASE WHEN TG_OP = 'DELETE' THEN OLD.shipment_id ELSE NEW.shipment_id END);
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;

CREATE CONSTRAINT TRIGGER inv_ship_sequence_after_shipment_change
AFTER INSERT OR UPDATE ON shipments
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION enforce_shipment_sequence_invariant();

CREATE CONSTRAINT TRIGGER inv_ship_sequence_after_checkpoint_change
AFTER INSERT ON checkpoints
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION enforce_shipment_sequence_invariant();
