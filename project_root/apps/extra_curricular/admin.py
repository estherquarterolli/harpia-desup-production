from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from apps.accounts.admin import admin_site
from apps.extra_curricular.models import (
    AtividadeExtensionista,
    OrientacaoTCC,
    PendenciaExtra,
    ReducaoCargaHoraria,
)


# ── Inlines ──────────────────────────────────────────────────────────────────
class OrientacaoTCCInline(TabularInline):
    model  = OrientacaoTCC
    extra  = 0
    fields = ["num_orientandos", "carga_horaria", "parecer_desup", "motivo_parecer"]
    readonly_fields = ["carga_horaria"]


class AtividadeExtensionistaInline(TabularInline):
    model  = AtividadeExtensionista
    extra  = 0
    fields = ["num_estudantes", "carga_horaria", "parecer_desup", "motivo_parecer"]
    readonly_fields = ["carga_horaria"]


class ReducaoCargaHorariaInline(TabularInline):
    model  = ReducaoCargaHoraria
    extra  = 0
    fields = ["motivo_reducao", "horas_reduzidas", "parecer_desup", "motivo_parecer"]


# ── PendenciaExtra Admin ──────────────────────────────────────────────────────
class PendenciaExtraAdmin(ModelAdmin):
    list_display  = [
        "professor", "unidade", "semestre", "status",
        "sei_numero", "ch_total_justificada_display", "data_atualizacao",
    ]
    list_filter   = ["status", "semestre", "unidade"]
    search_fields = ["professor__rh_nome", "professor__desup_nome", "sei_numero"]
    readonly_fields = ["data_criacao", "data_atualizacao", "criado_por"]
    inlines       = [
        OrientacaoTCCInline,
        AtividadeExtensionistaInline,
        ReducaoCargaHorariaInline,
    ]

    @admin.display(description="CH Justificada Total")
    def ch_total_justificada_display(self, obj):
        return f"{obj.ch_total_justificada}h"

admin_site.register(PendenciaExtra, PendenciaExtraAdmin)
