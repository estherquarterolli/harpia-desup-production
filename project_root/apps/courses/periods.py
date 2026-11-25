"""Opções novas e reconhecimento de períodos importados, sem regravar legados."""
import re

from apps.core.busca import normalizar

PERIODO_COMPONENTE_CHOICES = [('', 'Selecione')] + [
    (f'{i}º Período', f'{i}º Período') for i in range(1, 9)
]


def normalizar_periodo_matriz(periodo):
    texto = normalizar(str(periodo or '').strip())
    # Preserve as variações já aceitas pelo importador, inclusive separadores
    # após o ordinal; a mudança é de nomenclatura, não de validação da planilha.
    inicio = re.match(r'^([1-8])(?:\s|º|°|o|a|$)', texto)
    invertido = re.search(r'(?:semestre|periodo)\s*([1-8])$', texto)
    match = inicio or invertido
    if match:
        return f'{match.group(1)}º Período'
    return None
