"""Compare published USD amounts without binary floating-point errors."""
from decimal import Decimal, ROUND_HALF_UP


def validate_prizes(expected, amounts):
    cent = Decimal("0.01")
    expected_decimal = Decimal(str(expected)).quantize(cent, rounding=ROUND_HALF_UP)
    total = sum((Decimal(str(value)).quantize(cent, rounding=ROUND_HALF_UP)
                 for value in amounts), Decimal("0"))
    difference = total - expected_decimal
    # Small differences are flagged separately, never declared verified matches.
    status = "matched" if difference == 0 else (
        "rounding_difference" if abs(difference) <= Decimal("0.02") else "needs_review"
    )
    return float(total), float(difference), status
