"""Utilidades do app extra_curricular."""
from django.utils import timezone


def semestre_atual() -> str:
    """Retorna o semestre letivo corrente no formato 'AAAA.S' (S = 1 ou 2).

    Regra: meses 1–6 → semestre '.1'; meses 7–12 → semestre '.2'.

    Fonte única de verdade do "semestre atual". É usada tanto nas telas de
    extracurriculares quanto no cálculo de CH justificada do professor: as
    justificativas são escopadas por semestre (uma ``PendenciaExtra`` por
    professor + semestre) e NÃO devem continuar contando em semestres
    seguintes.
    """
    hoje = timezone.now()
    s = "1" if hoje.month <= 6 else "2"
    return f"{hoje.year}.{s}"
