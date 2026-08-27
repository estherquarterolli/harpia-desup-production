from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # Unidades
    path('unidades/', views.UnidadeListView.as_view(), name='unidade_list'),
    path('unidades/add/', views.UnidadeCreateView.as_view(), name='unidade_create'),
    path('unidades/<int:pk>/edit/', views.UnidadeUpdateView.as_view(), name='unidade_update'),

    # Cursos de cada Unidade
    path('unidades/<int:unidade_pk>/cursos/', views.CursoListView.as_view(), name='curso_list'),
    path('unidades/<int:unidade_pk>/cursos/add/', views.CursoCreateView.as_view(), name='curso_create'),
    path('unidades/<int:unidade_pk>/cursos/<int:pk>/edit/', views.CursoUpdateView.as_view(), name='curso_update'),
    path('unidades/<int:unidade_pk>/cursos/<int:pk>/delete/', views.CursoDeleteView.as_view(), name='curso_delete'),

    # Janelas de Entrega
    path('entregas/', views.JanelaEntregaListView.as_view(), name='janela_list'),
    path('entregas/add/', views.JanelaEntregaCreateView.as_view(), name='janela_create'),
    path('entregas/<int:pk>/editar/', views.JanelaEntregaUpdateView.as_view(), name='janela_update'),
    path('entregas/<int:pk>/excluir/', views.JanelaEntregaDeleteView.as_view(), name='janela_delete'),

    # Notificações
    path('notificacoes/<int:pk>/lida/', views.MarcarNotificacaoLidaView.as_view(), name='marcar_notificacao_lida'),

    # Chamados
    path('chamados/alteracao/', views.SolicitarChamadoAlteracaoView.as_view(), name='solicitar_chamado_alteracao'),

    # Logs
    path('logs/exportar/', views.ExportarLogsView.as_view(), name='exportar_logs'),
]
