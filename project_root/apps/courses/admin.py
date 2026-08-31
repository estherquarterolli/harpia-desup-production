from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from apps.accounts.admin import admin_site
from .models import Course, CurricularComponent, CurriculumMatrix, MatrixComponent, ClassGroup, CourseUnit

class CourseAdmin(ModelAdmin):
    list_display = ('nome', 'sigla')
    search_fields = ('nome', 'sigla')

class CourseUnitAdmin(ModelAdmin):
    list_display = ('curso', 'unidade', 'ativo')
    search_fields = ('curso__nome', 'curso__sigla', 'unidade__nome')
    list_filter = ('unidade', 'ativo')

class CurricularComponentAdmin(ModelAdmin):
    list_display = ('nome', 'codigo', 'carga_horaria_padrao', 'creditos')
    search_fields = ('nome', 'codigo')
    filter_horizontal = ('pre_requisitos',)

class MatrixComponentInline(TabularInline):
    model = MatrixComponent
    extra = 1
    autocomplete_fields = ('componente_curricular', 'docente', 'curso_compartilhado')
    filter_horizontal = ('pre_requisitos',)
    fields = (
        'componente_curricular',
        'codigo',
        'periodo',
        'carga_horaria',
        'creditos',
        'pre_requisitos',
        'docente',
        'compartilhado',
        'curso_compartilhado',
        'carga_horaria_semanal',
        'distribuicao_semanal',
        'status',
    )

class CurriculumMatrixAdmin(ModelAdmin):
    list_display = ('curso', 'total_componentes')
    list_filter = ('curso',)
    search_fields = ('curso__nome', 'curso__sigla', 'unidades__nome')
    inlines = (MatrixComponentInline,)

class MatrixComponentAdmin(ModelAdmin):
    list_display = (
        'matriz',
        'componente_curricular',
        'codigo',
        'periodo',
        'carga_horaria',
        'creditos',
        'docente',
        'compartilhado',
        'status',
    )
    list_filter = ('status', 'compartilhado', 'matriz__curso')
    search_fields = (
        'componente_curricular__nome',
        'codigo',
        'matriz__curso__nome',
        'matriz__curso__sigla',
    )
    autocomplete_fields = ('matriz', 'componente_curricular', 'docente', 'curso_compartilhado')
    filter_horizontal = ('pre_requisitos',)

class ClassGroupAdmin(ModelAdmin):
    list_display = ('identificador', 'matriz_curricular', 'matriz_componente', 'ano_semestre')
    list_filter = ('ano_semestre',)

admin_site.register(Course, CourseAdmin)
admin_site.register(CourseUnit, CourseUnitAdmin)
admin_site.register(CurricularComponent, CurricularComponentAdmin)
admin_site.register(CurriculumMatrix, CurriculumMatrixAdmin)
admin_site.register(MatrixComponent, MatrixComponentAdmin)
admin_site.register(ClassGroup, ClassGroupAdmin)
