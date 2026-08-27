from django.urls import path
from . import views

app_name = 'professors'

urlpatterns = [
    path('', views.ProfessorListView.as_view(), name='professor_list'),
    path('criar/', views.ProfessorCreateView.as_view(), name='professor_create'),
    path('<int:pk>/editar/', views.ProfessorUpdateView.as_view(), name='professor_update'),
    path('<int:pk>/excluir/', views.ProfessorDeleteView.as_view(), name='professor_delete'),
    path('<int:pk>/duplicar/', views.ProfessorDuplicarView.as_view(), name='professor_duplicar'),

    # Legado & HTMX
    path('alocacao/', views.alloc_curricular_view, name='alloc_curricular'),
    path('htmx/tabela-alocacao/', views.htmx_tabela_alocacao, name='htmx_tabela_alocacao'),
    path('htmx/cursos-unidade/', views.ProfessorCursosPartialView.as_view(), name='htmx_cursos_unidade'),
]