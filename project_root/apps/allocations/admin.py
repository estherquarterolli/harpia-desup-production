from django.contrib import admin
from apps.accounts.admin import HarpiaModelAdmin, admin_site
from .models import AlocacaoCurricular

class AlocacaoCurricularAdmin(HarpiaModelAdmin):
    list_display = ('curso', 'semestre', 'turno', 'status', 'unidade')
    list_filter = ('status', 'semestre', 'turno', 'unidade')
    search_fields = ('curso__curso__nome', 'curso__curso__sigla', 'sei_numero')

admin_site.register(AlocacaoCurricular, AlocacaoCurricularAdmin)
