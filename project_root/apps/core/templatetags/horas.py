from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def hhmm(value):
    """Horas decimais (6.75) em hora relógio: 6h45min, 18h, 45min."""
    if value in (None, ""):
        return ""
    try:
        total = int((Decimal(str(value).replace(",", ".")) * 60).to_integral_value())
    except (InvalidOperation, ValueError):
        return value
    sinal = "-" if total < 0 else ""
    horas, minutos = divmod(abs(total), 60)
    if not minutos:
        return f"{sinal}{horas}h"
    if not horas:
        return f"{sinal}{minutos}min"
    return f"{sinal}{horas}h{minutos:02d}min"
