from django.contrib import admin
from apps.accounts.admin import HarpiaModelAdmin, admin_site
from .models import AlocacaoCurricular, AlocacaoTurmaDocente, Carencia, SolicitacaoRAT

class AlocacaoCurricularAdmin(HarpiaModelAdmin):
    list_display = ('curso', 'semestre', 'turno', 'status', 'unidade')
    list_filter = ('status', 'semestre', 'turno', 'unidade')
    search_fields = ('curso__curso__nome', 'curso__curso__sigla', 'sei_numero')

admin_site.register(AlocacaoCurricular, AlocacaoCurricularAdmin)


class AlocacaoTurmaDocenteAdmin(HarpiaModelAdmin):
    list_display = ('componente_matriz', 'turma', 'docente', 'alocacao_curricular', 'carga_horaria_contabilizada', 'compartilhado')
    list_filter = ('compartilhado', 'alocacao_curricular__semestre', 'alocacao_curricular__unidade')
    search_fields = ('docente__rh_nome', 'docente__desup_nome', 'componente_matriz__codigo')
    autocomplete_fields = ('docente',)


class CarenciaAdmin(HarpiaModelAdmin):
    list_display = ('alocacao_turma_docente', 'status', 'atualizado_em')
    list_filter = ('status',)


class SolicitacaoRATAdmin(HarpiaModelAdmin):
    list_display = ('carencia', 'professor', 'carga_horaria_solicitada', 'status', 'data_solicitacao')
    list_filter = ('status',)
    autocomplete_fields = ('professor',)


admin_site.register(AlocacaoTurmaDocente, AlocacaoTurmaDocenteAdmin)
admin_site.register(Carencia, CarenciaAdmin)
admin_site.register(SolicitacaoRAT, SolicitacaoRATAdmin)
