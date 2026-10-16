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

    # Prioridade 1 - governança da DESUP
    path('desup/equipe-diretiva/', views.EquipeDiretivaDesupView.as_view(), name='equipe_diretiva_desup'),
    path('desup/equipe-diretiva/cargos/novo/', views.TipoCargoDiretivoCreateView.as_view(), name='cargo_diretivo_create'),
    path('desup/equipe-diretiva/cargos/<int:pk>/editar/', views.TipoCargoDiretivoUpdateView.as_view(), name='cargo_diretivo_update'),
    path('desup/equipe-diretiva/ocupacoes/<int:pk>/editar/', views.OcupacaoEquipeDiretivaUpdateView.as_view(), name='ocupacao_diretiva_update'),
    path('desup/solicitacoes-professor/', views.SolicitacaoProfessorExternoDesupView.as_view(), name='solicitacao_professor_list'),
    path('desup/solicitacoes-professor/<int:pk>/decidir/', views.SolicitacaoProfessorExternoDecidirView.as_view(), name='solicitacao_professor_decidir'),
    path('desup/alertas-carga/', views.AlertasCargaDesupView.as_view(), name='alertas_carga_desup'),
    path('desup/alertas-carga/limites/novo/', views.LimiteCargaUnidadeCreateView.as_view(), name='limite_carga_create'),
    path('desup/alertas-carga/limites/<int:pk>/editar/', views.LimiteCargaUnidadeUpdateView.as_view(), name='limite_carga_update'),
    path('desup/alertas-carga/readaptacoes/nova/', views.ReadaptacaoProfessorCreateView.as_view(), name='readaptacao_create'),
    path('desup/alertas-carga/readaptacoes/<int:pk>/editar/', views.ReadaptacaoProfessorUpdateView.as_view(), name='readaptacao_update'),
    path('desup/alertas-carga/readaptacoes/<int:pk>/encerrar/', views.ReadaptacaoProfessorEncerrarView.as_view(), name='readaptacao_encerrar'),
    path('desup/alertas-carga/excecoes/<int:pk>/decidir/', views.ExcecaoCargaDecidirView.as_view(), name='excecao_carga_decidir'),

    # Atalhos dos dashboards (DESUP/unidade, por usuário e por perfil)
    path('atalhos/add/', views.AtalhoAddView.as_view(), name='atalho_add'),
    path('atalhos/<int:pk>/remover/', views.AtalhoRemoveView.as_view(), name='atalho_remove'),
]
