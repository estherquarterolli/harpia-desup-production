from django.contrib import admin
from unfold.admin import ModelAdmin
from apps.accounts.admin import admin_site
from .models import Professor, ContractType, Availability, AbsenceRecord

class ProfessorAdmin(ModelAdmin):
    list_display = ('nome', 'id_funcional', 'rh_matricula', 'unidade_principal', 'status')
    search_fields = ('rh_nome', 'id_funcional', 'rh_matricula')
    list_filter = ('status', 'unidade_principal', 'tipo_contrato')

class ContractTypeAdmin(ModelAdmin):
    list_display = ('nome', 'categoria', 'regime_trabalho', 'dias_presenca_obrigatorios', 'max_class_hours', 'max_total_hours')
    search_fields = ('nome', 'regime_trabalho')

class AvailabilityAdmin(ModelAdmin):
    list_display = ('professor', 'dia_semana', 'turno')
    list_filter = ('dia_semana', 'turno')

class AbsenceRecordAdmin(ModelAdmin):
    list_display = ('professor', 'data_inicio', 'data_fim', 'motivo')
    list_filter = ('data_inicio', 'data_fim')

admin_site.register(Professor, ProfessorAdmin)
admin_site.register(ContractType, ContractTypeAdmin)
admin_site.register(Availability, AvailabilityAdmin)
admin_site.register(AbsenceRecord, AbsenceRecordAdmin)
