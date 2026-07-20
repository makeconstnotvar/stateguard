MACHINE OrderWorkflow

SETS
    ORDER = {o1, o2};
    PAYMENT = {p1, p2};
    STATUS = {draft, submitted, paid, cancelled};
    PAYMENT_STATUS = {payment_pending, payment_confirmed, payment_rejected}

VARIABLES
    status,
    version,
    payment_of,
    payment_status,
    payment_order

INVARIANT
    status : ORDER --> STATUS &
    version : ORDER --> NAT1 &
    payment_of : ORDER +-> PAYMENT &
    payment_status : PAYMENT --> PAYMENT_STATUS &
    payment_order : PAYMENT --> ORDER &
    !o.(o : ORDER & status(o) = paid =>
        o : dom(payment_of) &
        payment_status(payment_of(o)) = payment_confirmed &
        payment_order(payment_of(o)) = o)

INITIALISATION
    status := ORDER * {draft} ||
    version := ORDER * {1} ||
    payment_of := {} ||
    payment_status := PAYMENT * {payment_pending} ||
    payment_order := {p1 |-> o1, p2 |-> o2}

OPERATIONS
    submit(o, expected_version) =
        PRE
            o : ORDER &
            expected_version : NAT1 &
            status(o) = draft &
            version(o) = expected_version
        THEN
            status(o) := submitted ||
            version(o) := version(o) + 1
        END;

    confirm_payment(p) =
        PRE
            p : PAYMENT &
            payment_status(p) = payment_pending
        THEN
            payment_status(p) := payment_confirmed
        END;

    mark_paid(o, p, expected_version) =
        PRE
            o : ORDER &
            p : PAYMENT &
            expected_version : NAT1 &
            status(o) = submitted &
            version(o) = expected_version &
            payment_status(p) = payment_confirmed &
            payment_order(p) = o
        THEN
            payment_of(o) := p ||
            status(o) := paid ||
            version(o) := version(o) + 1
        END;

    cancel(o, expected_version) =
        PRE
            o : ORDER &
            expected_version : NAT1 &
            status(o) : {draft, submitted} &
            version(o) = expected_version
        THEN
            status(o) := cancelled ||
            version(o) := version(o) + 1
        END

END
