from django.urls import path
from . import views

app_name = 'courses'

urlpatterns = [
    # ── Matrizes Curriculares ────────────────────────────────────
    path('matrices/', views.CurriculumMatrixListView.as_view(), name='matrix_list'),
    path('matrices/add/', views.CurriculumMatrixCreateView.as_view(), name='matrix_create'),
    path('matrices/<int:pk>/', views.CurriculumMatrixDetailView.as_view(), name='matrix_detail'),
    path('matrices/<int:pk>/edit/', views.CurriculumMatrixUpdateView.as_view(), name='matrix_update'),

    # Partial HTMX — retorna apenas o fragmento da tabela (filtros)
    path('matrices/partial/', views.CurriculumMatrixListPartialView.as_view(), name='matrix_list_partial'),

    # HTMX — adiciona nova linha de formset sem reload
    path('matrices/add-row/', views.MatrixAddFormsetRowView.as_view(), name='matrix_add_row'),

    # HTMX — carregar cursos por unidade
    path('matrices/load-courses/', views.LoadCoursesByUnitView.as_view(), name='load_courses_by_unit'),
    path('matrices/load-duplicate-options/', views.LoadMatricesForDuplicateView.as_view(), name='load_duplicate_options'),

    # HTMX — importar matriz anterior do curso
    path('matrices/import-previous/', views.ImportPreviousMatrixView.as_view(), name='matrix_import_previous'),

    # JSON — verificar se existe matriz para o curso+turno (popup de copiar)
    path('matrices/buscar-existente/', views.BuscarMatrizExistenteView.as_view(), name='matrix_buscar_existente'),

    # JSON — dados da matriz para preencher o formset ao copiar
    path('matrices/dados-copiar/<int:pk>/', views.DadosMatrizCopiarView.as_view(), name='matrix_dados_copiar'),

    # ── Turmas ──────────────────────────────────────────────────
    path('groups/', views.ClassGroupListView.as_view(), name='classgroup_list'),
    path('groups/add/', views.ClassGroupCreateView.as_view(), name='classgroup_create'),

    # ── Componentes Curriculares (DESUP) ───────────────────────
    path('componentes/', views.CurricularComponentListView.as_view(), name='component_list'),
    path('componentes/novo/', views.CurricularComponentCreateView.as_view(), name='component_create'),
    path('componentes/<int:pk>/editar/', views.CurricularComponentUpdateView.as_view(), name='component_edit'),
    path('componentes/<int:pk>/excluir/', views.CurricularComponentDeleteView.as_view(), name='component_delete'),

    # JSON — busca autocomplete de componentes curriculares
    path('componentes/buscar/', views.BuscarComponenteView.as_view(), name='buscar_componente'),
]
