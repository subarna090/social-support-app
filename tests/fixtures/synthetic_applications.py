"""Synthetic applications for SC-005 and SC-006 (T023). All names and IDs are fictional."""

from social_support.domain.models import Outcome

A, R, S = Outcome.APPROVE, Outcome.NEEDS_HUMAN_REVIEW, Outcome.SOFT_DECLINE


def valid_payload(**overrides) -> dict:
    payload = {
        "full_name": "Aisha Al Mansoori",
        "emirates_id": "784-1990-1234567-1",
        "family_size": 4,
        "net_monthly_income_aed": "6000.00",
        "employment_status": "EMPLOYED",
    }
    return payload | overrides


def _case(n: int, family: int, income: str, status: str, expected: Outcome):
    payload = valid_payload(
        full_name=f"Synthetic Applicant {n:02d}",
        emirates_id=f"784-19{70 + n:02d}-{1000000 + n:07d}-{n % 10}",
        family_size=family,
        net_monthly_income_aed=income,
        employment_status=status,
    )
    return payload, expected


# (payload, expected outcome); income per member shown in the comment.
VALID_CASES = [
    _case(1, 4, "6000.00", "EMPLOYED", A),  # 1500.00
    _case(2, 1, "1999.99", "EMPLOYED", A),  # 1999.99, just below the threshold
    _case(3, 1, "2000.00", "EMPLOYED", R),  # 2000.00, at the threshold
    _case(4, 1, "2500.00", "SELF_EMPLOYED", R),  # 2500.00, top of the band
    _case(5, 1, "2500.01", "SELF_EMPLOYED", S),  # 2500.01, just above the band
    _case(6, 3, "0", "UNEMPLOYED", A),  # 0.00, zero income
    _case(7, 20, "39999.80", "EMPLOYED", A),  # 1999.99, family of 20
    _case(8, 20, "40000.00", "EMPLOYED", R),  # 2000.00
    _case(9, 20, "50000.20", "EMPLOYED", S),  # 2500.01
    _case(10, 2, "4500.00", "SELF_EMPLOYED", R),  # 2250.00
    _case(11, 1, "3000.00", "STUDENT", S),  # 3000.00
    _case(12, 5, "7500.00", "RETIRED", A),  # 1500.00
    _case(13, 6, "15000.06", "EMPLOYED", S),  # 2500.01
    _case(14, 2, "3999.98", "STUDENT", A),  # 1999.99
    _case(15, 4, "10000.00", "RETIRED", R),  # 2500.00
    _case(16, 3, "1000.00", "UNEMPLOYED", A),  # 333.33, rounding
    _case(17, 7, "20000.00", "EMPLOYED", S),  # 2857.14
    _case(18, 8, "16000.00", "SELF_EMPLOYED", R),  # 2000.00
    _case(19, 1, "1000000.00", "EMPLOYED", S),  # 1000000.00, upper income limit
    _case(20, 10, "12500.00", "UNEMPLOYED", A),  # 1250.00
    _case(21, 3, "6000.03", "RETIRED", R),  # 2000.01
    _case(22, 2, "5000.02", "STUDENT", S),  # 2500.01
    _case(23, 3, "7500.01", "EMPLOYED", R),  # 2500.0033 rounds to 2500.00
    _case(24, 3, "7500.02", "EMPLOYED", S),  # 2500.0067 rounds to 2500.01
]


def _without(field: str) -> dict:
    payload = valid_payload()
    del payload[field]
    return payload


# (payload, field expected in errors[]); at least one case per FR-002 rule, plus FR-014.
INVALID_CASES = [
    (_without("full_name"), "full_name"),
    (valid_payload(full_name="A"), "full_name"),
    (valid_payload(full_name="x" * 101), "full_name"),
    (_without("emirates_id"), "emirates_id"),
    (valid_payload(emirates_id="123-45"), "emirates_id"),
    (valid_payload(emirates_id="785-1990-1234567-1"), "emirates_id"),
    (_without("family_size"), "family_size"),
    (valid_payload(family_size=0), "family_size"),
    (valid_payload(family_size=21), "family_size"),
    (valid_payload(family_size=2.5), "family_size"),
    (_without("net_monthly_income_aed"), "net_monthly_income_aed"),
    (valid_payload(net_monthly_income_aed="-1"), "net_monthly_income_aed"),
    (valid_payload(net_monthly_income_aed="1000000.01"), "net_monthly_income_aed"),
    (valid_payload(net_monthly_income_aed="100.123"), "net_monthly_income_aed"),
    (valid_payload(net_monthly_income_aed="lots"), "net_monthly_income_aed"),
    (_without("employment_status"), "employment_status"),
    (valid_payload(employment_status="WORKING"), "employment_status"),
    (valid_payload(nationality="Emirati"), "nationality"),
]
