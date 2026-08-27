import unicodedata
from difflib import SequenceMatcher

from apps.professors.models import Professor


def _normalize(value):
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", str(value))
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return " ".join(normalized.casefold().split())


def update_or_create_professor(id_funcional, rh_matricula, defaults, legacy_values=None, legacy_names=None, unidade=None):
    legacy_values = legacy_values or []
    legacy_names = legacy_names or []
    qs = Professor.objects.all().order_by("pk")
    if unidade is not None:
        qs = qs.filter(unidade_principal=unidade)

    professor = qs.filter(id_funcional=id_funcional).first() or qs.filter(rh_matricula=rh_matricula).first()
    if professor is None:
        for value in legacy_values:
            professor = qs.filter(id_funcional=value).first() or qs.filter(rh_matricula=value).first()
            if professor:
                break

    if professor is None and legacy_names:
        normalized_legacy = {_normalize(name) for name in legacy_names if name}
        for candidate in qs:
            if _normalize(candidate.rh_nome) in normalized_legacy:
                professor = candidate
                break

    if professor is None and legacy_names:
        normalized_legacy = [_normalize(name) for name in legacy_names if name]
        best_score = 0.0
        best_candidate = None
        for candidate in qs:
            candidate_name = _normalize(candidate.rh_nome)
            for legacy_name in normalized_legacy:
                if candidate_name == legacy_name or candidate_name in legacy_name or legacy_name in candidate_name:
                    professor = candidate
                    best_score = 1.0
                    break
                score = SequenceMatcher(None, candidate_name, legacy_name).ratio()
                if score > best_score:
                    best_score = score
                    best_candidate = candidate
            if professor:
                break
        if professor is None and best_score >= 0.72:
            professor = best_candidate

    if professor:
        for field, value in {
            "id_funcional": id_funcional,
            "rh_matricula": rh_matricula,
            **defaults,
        }.items():
            setattr(professor, field, value)
        professor.save()
        return professor, False

    return Professor.objects.create(
        id_funcional=id_funcional,
        rh_matricula=rh_matricula,
        **defaults,
    ), True
