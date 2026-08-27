from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from apps.accounts.admin import admin_site
from apps.core.views import custom_500

handler500 = custom_500
from apps.accounts.views import (
    login_view,
    CustomPasswordChangeView,
    PasswordChangeConfirmView,
    ForgotPasswordView,
    ApprovePasswordResetView,
)
from apps.core.views import DashboardView, DashboardDesupView, DashboardUnidadeView, DashboardProfessoresPartialView
from django.contrib.auth import views as auth_views
from apps.allocations.views import AllocCurricularView, LiberarAlocacaoView, AprovarAlocacaoUnidadeView, AlocarDocenteComponenteView, BuscarProfessoresView

urlpatterns = [
    # acesso ao perfil SuperAdmin via Admin Site Customizado
    path('admin/', admin_site.urls),
    
    path('accounts/password_change/', CustomPasswordChangeView.as_view(), name='password_change'),
    path('accounts/password_change/confirm/<uuid:token>/', PasswordChangeConfirmView.as_view(), name='password_change_confirm'),
    path('accounts/forgot-password/', ForgotPasswordView.as_view(), name='forgot_password'),
    path('accounts/reset/aprovar/<uuid:token>/', ApprovePasswordResetView.as_view(), name='approve_password_reset'),
    
    # Acesso aos outros perfils (admin e unidade)
    path('accounts/', include('django.contrib.auth.urls')),
    
    # caminho da página de login usando a login_view customizada (Regra #10)
    path('login/', login_view, name='login'),
    
    # Gestão Acadêmica (Matrizes e Turmas)
    path('courses/', include('apps.courses.urls')),
    
    # caminho da pag de alocação curricular (agora usando a classe)
    path('alocacao-curricular/', AllocCurricularView.as_view(), name='alloc_curricular'),
    path('alocacao-curricular/componente/<int:pk>/alocar/', AlocarDocenteComponenteView.as_view(), name='alocar_docente_componente'),
    path('alocacao-curricular/<int:pk>/liberar/', LiberarAlocacaoView.as_view(), name='liberar_alocacao'),
    path('alocacao-curricular/unidade/<int:unidade_id>/aprovar/', AprovarAlocacaoUnidadeView.as_view(), name='aprovar_alocacao_unidade'),
    path('alocacao-curricular/buscar-professores/', BuscarProfessoresView.as_view(), name='buscar_professores'),
    
    # caminho da pag principal, onde os dashboards ficam. 
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('dashboard/desup/', DashboardDesupView.as_view(), name='dashboard_desup'),
    path('dashboard/desup/professores/', DashboardProfessoresPartialView.as_view(), name='dashboard_professores_partial'),
    path('dashboard/unidade/', DashboardUnidadeView.as_view(), name='dashboard_unidade'),
    
    # Redirecionamento da raiz para o dashboard
    path('', RedirectView.as_view(pattern_name='dashboard', permanent=False)),
    path('core/', include('apps.core.urls')),

  
    path('professores/', include('apps.professors.urls')),

    # Atividades Extracurriculares (Alocação Extra-Curricular)
    path('extracurriculares/', include('apps.extra_curricular.urls', namespace='extra_curricular')),

    # Rota legada — redireciona para a nova lista de pendências
    path('extracurriculares-legado/', RedirectView.as_view(pattern_name='extra_curricular:pendencia_list', permanent=True), name='extracurricular_index'),
]
