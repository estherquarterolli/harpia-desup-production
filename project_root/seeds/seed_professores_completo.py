"""
Seed COMPLETA de professores (todas as unidades) — porta os 191 professores e os
4 tipos de contrato de `seeds/sql/seed_supabase.sql` para o schema atual, via ORM.

Idempotente e não-duplicante:
  - Tipos de contrato: get_or_create por nome.
  - Professores: usa `update_or_create_professor` casando por id_funcional / matrícula
    e, como fallback, por NOME dentro da unidade — assim os professores de Paracambi
    já semeados são reconciliados (atualizados) em vez de duplicados.

Reaproveita o parser de `seed_matrizes_completo`.

Uso:
    python seeds/seed_professores_completo.py
"""
import os
import sys
from pathlib import Path

import django

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
django.setup()

from django.db import transaction

from apps.core.models import Unidade
from apps.professors.models import ContractType, Professor
from seeds.helpers import update_or_create_professor
from seeds.seed_matrizes_completo import SQL_PATH, _extract_rows


@transaction.atomic
def run():
    text = SQL_PATH.read_text(encoding="utf-8")

    # 1) Unidades: mapa old_id -> Unidade (dedup por nome, igual à seed de matrizes)
    unidade_by_old = {}
    for oid, nome, sigla, status in _extract_rows(text, "core_unidade"):
        u, _ = Unidade.objects.get_or_create(nome=nome, defaults={"sigla": sigla, "status": bool(status)})
        unidade_by_old[oid] = u

    # 2) Tipos de contrato: old_id -> ContractType (dedup por nome)
    contract_by_old = {}
    for row in _extract_rows(text, "professors_contracttype"):
        oid, nome, categoria, regime, dias, max_ch, max_total, max_turmas = row
        total = max_total if max_total is not None else 40
        # Regra de negócio: o limite de horas em sala (meta de alocação) é METADE
        # do regime — 40h → 20h, 20h → 10h. O valor do dump SQL vinha errado (32/16).
        max_class = total // 2
        ct, _ = ContractType.objects.get_or_create(
            nome=nome,
            defaults={
                "categoria": categoria or "EFETIVO",
                "regime_trabalho": regime or "",
                "dias_presenca_obrigatorios": dias if dias is not None else 3,
                "max_class_hours": max_class,
                "max_total_hours": total,
                "max_classes": max_turmas or 0,
            },
        )
        # Garante correção mesmo em bancos onde o contrato já existia com valor errado.
        if ct.max_class_hours != max_class:
            ct.max_class_hours = max_class
            ct.save(update_fields=["max_class_hours"])
        contract_by_old[oid] = ct
    print(f"Tipos de contrato: {len(contract_by_old)}")

    # 3) Professores
    criados = atualizados = ignorados = 0
    for row in _extract_rows(text, "professors_professor"):
        (oid, id_funcional, rh_matricula, rh_nome, rh_email, unidade_id,
         desup_nome, desup_email, tipo_contrato_id, is_cedido, ha, materia, status) = row

        unidade = unidade_by_old.get(unidade_id)
        contrato = contract_by_old.get(tipo_contrato_id)
        if not contrato:
            ignorados += 1
            continue

        _, created = update_or_create_professor(
            id_funcional=id_funcional,
            rh_matricula=rh_matricula,
            legacy_values=[str(id_funcional), str(rh_matricula)],
            legacy_names=[rh_nome],
            unidade=unidade,
            defaults={
                "rh_nome": rh_nome,
                "rh_email": rh_email or None,
                "unidade_principal": unidade,
                "tipo_contrato": contrato,
                "is_cedido": bool(is_cedido),
                "ha": ha or 0,
                "materia": materia or "",
                "status": status or "Ativo",
            },
        )
        criados += int(created)
        atualizados += int(not created)

    print(f"Professores criados: {criados} | reconciliados/atualizados: {atualizados} | ignorados: {ignorados}")
    print(f"Total de professores no banco: {Professor.objects.count()}")
    print("\nSeed de professores completa finalizada!")


if __name__ == "__main__":
    run()
