from django.urls import path
from apps.extra_curricular import views

app_name = "extra_curricular"

urlpatterns = [
    path("pendencias/<int:pk>/", views.PendenciaDetailView.as_view(), name="pendencia_detail"),
    path("pendencias/<int:pk>/tcc/salvar/", views.SalvarTCCView.as_view(), name="salvar_tcc"),
    path("pendencias/<int:pk>/extensao/salvar/", views.SalvarExtensaoView.as_view(), name="salvar_extensao"),
    path("pendencias/<int:pk>/reducao/salvar/", views.SalvarReducaoView.as_view(), name="salvar_reducao"),
    path("pendencias/<int:pk>/deletar/<str:tipo>/<int:item_pk>/", views.DeletarItemView.as_view(), name="deletar_item"),

    path("pendencias/", views.PendenciaListView.as_view(), name="pendencia_list"),
    path("pendencias/nova/", views.PendenciaCreateView.as_view(), name="pendencia_create"),
    path("pendencias/lote/", views.PendenciaLoteView.as_view(), name="pendencia_lote"),

    path("pendencias/lote/tcc/salvar/", views.SalvarTCCLoteView.as_view(), name="salvar_tcc_lote"),
    path("pendencias/lote/extensao/salvar/", views.SalvarExtensaoLoteView.as_view(), name="salvar_extensao_lote"),
    path("pendencias/lote/reducao/salvar/", views.SalvarReducaoLoteView.as_view(), name="salvar_reducao_lote"),

    path("pendencias/lote/deletar/<str:tipo>/<int:item_pk>/", views.DeletarItemLoteView.as_view(), name="deletar_item_lote"),

    path("pendencias/<int:pk>/parecer/tcc/<int:item_pk>/", views.ParecerTCCUpdateView.as_view(), name="parecer_tcc"),
    path("pendencias/<int:pk>/parecer/extensao/<int:item_pk>/", views.ParecerExtensaoUpdateView.as_view(), name="parecer_extensao"),
    path("pendencias/<int:pk>/parecer/reducao/<int:item_pk>/", views.ParecerReducaoUpdateView.as_view(), name="parecer_reducao"),

    path("pendencias/lote/enviar/", views.EnviarParaDesupLoteView.as_view(), name="enviar_desup_lote"),
    path("pendencias/<int:pk>/avisar/", views.AvisarUnidadeView.as_view(), name="avisar_unidade"),
    path("pendencias/<int:pk>/status/", views.PendenciaStatusUpdateView.as_view(), name="atualizar_status"),
    path("pendencias/<int:pk>/reabrir/", views.PendenciaReabrirView.as_view(), name="reabrir_pendencia"),
    path("pendencias/lote/sei/editar/", views.PendenciaSEIUpdateLoteView.as_view(), name="editar_sei_lote"),
    path("pendencias/<int:pk>/enviar/", views.EnviarParaDesupView.as_view(), name="enviar_desup"),
    path("pendencias/<int:pk>/sei/editar/", views.PendenciaSEIUpdateView.as_view(), name="editar_sei"),

    path("api/calcular-ch/", views.CalcularCHView.as_view(), name="calcular_ch"),
]
