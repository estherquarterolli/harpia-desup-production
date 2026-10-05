from django.contrib import admin
from apps.accounts.admin import HarpiaModelAdmin, admin_site
from .models import Professor, ContractType, Availability, AbsenceRecord

class ProfessorAdmin(HarpiaModelAdmin):
    list_display = ('nome', 'id_funcional', 'rh_matricula', 'unidades_display', 'status')
    search_fields = ('rh_nome', 'id_funcional', 'rh_matricula')
    list_filter = ('status', 'unidades', 'tipo_contrato')
    filter_horizontal = ('unidades', 'cursos')

    @admin.display(description='Unidades')
    def unidades_display(self, obj):
        return ', '.join(unidade.sigla for unidade in obj.unidades_exibicao) or '—'

class ContractTypeAdmin(HarpiaModelAdmin):
    list_display = ('nome', 'categoria', 'regime_trabalho', 'dias_presenca_obrigatorios', 'max_class_hours', 'max_total_hours')
    search_fields = ('nome', 'regime_trabalho')

class AvailabilityAdmin(HarpiaModelAdmin):
    list_display = ('professor', 'dia_semana', 'turno')
    list_filter = ('dia_semana', 'turno')

class AbsenceRecordAdmin(HarpiaModelAdmin):
    list_display = ('professor', 'data_inicio', 'data_fim', 'motivo')
    list_filter = ('data_inicio', 'data_fim')

admin_site.register(Professor, ProfessorAdmin)
admin_site.register(ContractType, ContractTypeAdmin)
admin_site.register(Availability, AvailabilityAdmin)
admin_site.register(AbsenceRecord, AbsenceRecordAdmin)
