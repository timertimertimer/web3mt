from decimal import Decimal, ROUND_DOWN


def format_number(number: Decimal | str | float = None, accuracy: int = None) -> str:
    number = Decimal(str(number))
    sign, digits, exponent = number.as_tuple()
    num_decimal_places = abs(exponent)
    if accuracy:
        return str(number.quantize(Decimal(f'1.{"0" * (accuracy or num_decimal_places)}'), rounding=ROUND_DOWN))
    return f"{number:.{num_decimal_places}f}"
