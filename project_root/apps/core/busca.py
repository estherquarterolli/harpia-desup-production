"""Busca "contém" tolerante, usada nos filtros de texto do sistema.

Ignora acentos e maiúsculas, não depende da ordem das palavras e perdoa uma ou
outra letra faltando/trocada (ex.: "anderson" acha "ANDERSON", "andersn" e
"anderso silva"). Feita em Python sobre as colunas pesquisadas: as tabelas
filtradas (professores, componentes) têm poucos milhares de linhas.
"""
import re
import unicodedata
from difflib import SequenceMatcher


def normalizar(texto) -> str:
    texto = unicodedata.normalize('NFKD', str(texto or ''))
    texto = ''.join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', texto.lower()).strip()


def _token_casa(token: str, haystack: str, palavras: list) -> bool:
    if token in haystack:
        return True
    if len(token) < 4:
        return False
    for palavra in palavras:
        if abs(len(palavra) - len(token)) > 2:
            continue
        if SequenceMatcher(None, token, palavra[:len(token) + 1]).ratio() >= 0.8:
            return True
    return False


def texto_casa(termo, *valores) -> bool:
    tokens = normalizar(termo).split(' ')
    if not tokens or tokens == ['']:
        return True
    haystack = normalizar(' '.join(str(v) for v in valores if v))
    palavras = haystack.split(' ')
    return all(_token_casa(t, haystack, palavras) for t in tokens)


def filtrar_contem(queryset, termo, campos):
    """Filtra `queryset` por `termo` olhando os `campos` (nomes de campos do ORM)."""
    if not normalizar(termo):
        return queryset
    pks = {
        linha[0]
        for linha in queryset.order_by().values_list('pk', *campos)
        if texto_casa(termo, *linha[1:])
    }
    return queryset.filter(pk__in=pks)
