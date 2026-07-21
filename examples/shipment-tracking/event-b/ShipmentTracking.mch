MACHINE ShipmentTracking

SETS
    SHIPMENT = {s1, s2};
    EVENT = {e1, e2, e3};
    STATUS = {pending, in_transit, out_for_delivery, delivered, exception}

VARIABLES
    status,
    last_sequence,
    processed,
    event_sequence

INVARIANT
    status : SHIPMENT --> STATUS &
    last_sequence : SHIPMENT --> 0..5 &
    processed : SHIPMENT <-> EVENT &
    event_sequence : (SHIPMENT * EVENT) +-> 0..5 &
    dom(event_sequence) = processed &
    !ss.(ss : SHIPMENT =>
        !e.(e : EVENT & ss |-> e : processed => event_sequence(ss |-> e) <= last_sequence(ss)))

INITIALISATION
    status := SHIPMENT * {pending} ||
    last_sequence := SHIPMENT * {0} ||
    processed := {} ||
    event_sequence := {}

OPERATIONS
    record_checkpoint(s, e, seq, code) =
        PRE
            s : SHIPMENT &
            e : EVENT &
            seq : 0..5 &
            code : {in_transit, out_for_delivery, delivered, exception}
        THEN
            IF s |-> e : processed
            THEN
                skip
            ELSIF status(s) : {delivered, exception}
            THEN
                skip
            ELSIF seq <= last_sequence(s)
            THEN
                skip
            ELSIF not(
                (status(s) = pending & code : {in_transit, exception}) or
                (status(s) = in_transit & code : {out_for_delivery, exception}) or
                (status(s) = out_for_delivery & code : {delivered, exception})
            )
            THEN
                skip
            ELSE
                status(s) := code ||
                last_sequence(s) := seq ||
                processed := processed \/ {s |-> e} ||
                event_sequence(s |-> e) := seq
            END
        END

END
