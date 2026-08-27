"""
Views para Alocação Extracurricular.

Perfis e permissões:
  COORDENADOR_UNIDADE → cria/edita PendenciaExtra e itens de justificativa.
                        Campos parecer_desup e motivo_parecer são bloqueados no template.
  DESUP               → vê todas as unidades; edita apenas parecer e motivo via
                        ParecerUpdateView (HTMX inline).
"""
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy, reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView

from apps.accounts.mixins import PerfilRequiredMixin
from apps.core.models import Unidade
from apps.core.services import build_window_lock_context, create_window_ticket, enforce_window_or_redirect, record_window_attempt
from apps.extra_curricular.forms import (
    AtividadeExtensionistaFormSet,
    OrientacaoTCCFormSet,
    ParecerExtensaoForm,
    ParecerReducaoForm,
    ParecerTCCForm,
    PendenciaExtraForm,
    ReducaoCargaHorariaFormSet,
)
from apps.extra_curricular.services import sincronizar_status_pendencia
from apps.extra_curricular.models import (
    AtividadeExtensionista,
    OrientacaoTCC,
    PendenciaExtra,
    ReducaoCargaHoraria,
)
from apps.extra_curricular.services import get_pendencias_data


# ══════════════════════════════════════════════════════════════════════════════
# Helper: obtém semestre da request ou padrão
# ══════════════════════════════════════════════════════════════════════════════
def _semestre_atual():
    from django.utils import timezone
    hoje = timezone.now()
    s = "1" if hoje.month <= 6 else "2"
    return f"{hoje.year}.{s}"


# ══════════════════════════════════════════════════════════════════════════════
# PendenciaListView — /extracurriculares/pendencias/
# ══════════════════════════════════════════════════════════════════════════════
class PendenciaListView(LoginRequiredMixin, PerfilRequiredMixin, View):
    """
    Lista professores com pendência de carga horária e seus registros de justificativa.
    """
    allowed_profiles = ["COORDENADOR_UNIDADE", "DESUP"]
    template_name = "extra_curricular/pendencia_list.html"

    def get(self, request):
        from apps.core.models import Unidade
        from apps.extra_curricular.services import get_pendencias_data

        user = request.user
        perfil = user.perfil

        semestre = request.GET.get("semestre", _semestre_atual())

        unidade = None
        if perfil == "COORDENADOR_UNIDADE":
            unidade = user.unidade
            if not unidade:
                messages.error(request, "Seu usuário não está vinculado a uma unidade.")
                return redirect("dashboard")
            unidades = [unidade]
        else:
            unidades = Unidade.objects.filter(status=True).order_by("nome")
            unidade_id = request.GET.get("unidade_id")
            unidade = Unidade.objects.filter(pk=unidade_id).first() if unidade_id else None

        q = request.GET.get("q", "").strip()
        status_filtro = request.GET.get("status", "").strip().lower()

        # Dados de pendência
        unidade_id_to_filter = unidade.id if unidade else None
        if perfil == 'COORDENADOR_UNIDADE':
            unidade_id_to_filter = unidade.id

        raw_data = get_pendencias_data(unidade_id_to_filter, semestre, q)

        # Filtro de Status
        if status_filtro:
            filtered_data = []
            for item in raw_data:
                status_item = item.get("status_item")
                pendencia = item.get("pendencia")
                
                if status_filtro == 'rascunho' and pendencia and status_item == 'RASCUNHO':
                    filtered_data.append(item)
                elif status_filtro == 'sem_registro' and not pendencia:
                    filtered_data.append(item)
                elif status_filtro == 'pendente' and pendencia and (status_item == 'ENVIADO' or status_item == 'PENDENTE'):
                    filtered_data.append(item)
                elif status_filtro == 'finalizado' and pendencia and status_item == 'APROVADO':
                    filtered_data.append(item)
            pendencias_data = filtered_data
        else:
            pendencias_data = raw_data

        # Semestres para o filtro
        semestres = _gerar_semestres()

        ctx = {
            "unidades": unidades,
            "unidade_selecionada": unidade,
            "semestre": semestre,
            "semestres": semestres,
            "pendencias_data": pendencias_data,
            "q": q,
            "is_desup": (perfil == "DESUP" or user.is_superuser),
            "status_filtro": status_filtro,
        }
        try:
            ctx.update(build_window_lock_context(
                user,
                unidade=unidade,
                area_label='Justificativas',
                action_label='registrar justificativa extracurricular',
                target_label='justificativa extracurricular',
            ))
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Erro ao montar contexto de janela (extracurricular)")
            ctx.update({'window_fechada': False, 'window_aberta': True})
        return render(request, self.template_name, ctx)


def _gerar_semestres():
    """Gera lista de semestres dos últimos 2 anos + próximo."""
    from django.utils import timezone
    ano = timezone.now().year
    result = []
    for a in range(ano + 1, ano - 2, -1):
        result += [f"{a}.2", f"{a}.1"]
    return result


# ══════════════════════════════════════════════════════════════════════════════
# PendenciaDetailView — /extracurriculares/pendencias/<pk>/
# ══════════════════════════════════════════════════════════════════════════════
class PendenciaCreateView(LoginRequiredMixin, PerfilRequiredMixin, View):
    allowed_profiles = ["COORDENADOR_UNIDADE"]
    template_name    = "extra_curricular/pendencia_form.html"

    def get(self, request):
        from django.shortcuts import render
        from apps.extra_curricular.services import get_professores_com_pendencia

        user = request.user
        if not user.unidade:
            messages.error(request, 'Seu usuário não está vinculado a uma unidade.')
            return redirect('dashboard')

        professores_pendentes = get_professores_com_pendencia(user.unidade.pk, _semestre_atual())

        ctx = {
            "professores": professores_pendentes,
            "semestre_atual": _semestre_atual()
        }
        ctx.update(build_window_lock_context(
            user,
            unidade=user.unidade,
            area_label='Justificativas',
            action_label='criar pendência extracurricular',
            target_label='pendência extracurricular',
        ))
        return render(request, self.template_name, ctx)

    def post(self, request):
        from apps.professors.models import Professor
        
        user = request.user
        blocked = enforce_window_or_redirect(
            request,
            area_label='Justificativas',
            action_label='criar pendência extracurricular',
            target_label='pendência extracurricular',
            unidade=user.unidade,
            fallback_url=reverse('extra_curricular:pendencia_create'),
        )
        if blocked:
            return blocked

        professor_ids = request.POST.getlist("professor_id")
        
        if not professor_ids:
            messages.error(request, "Selecione pelo menos um professor válido.")
            return redirect("extra_curricular:pendencia_create")
            
        created_count = 0
        last_pendencia = None

        for prof_id in professor_ids:
            professor = get_object_or_404(Professor, pk=prof_id)
            
            if professor.unidade_principal != user.unidade:
                continue # Pula se for de outra unidade por segurança

            pendencia, created = PendenciaExtra.objects.get_or_create(
                professor=professor,
                semestre=_semestre_atual(),
                defaults={
                    "unidade": professor.unidade_principal,
                    "criado_por": user,
                    "status": PendenciaExtra.StatusChoices.RASCUNHO
                }
            )
            last_pendencia = pendencia
            if created:
                created_count += 1
        
        # Redirecionar para a Mesa de Lote passando os IDs na querystring
        query_string = ",".join(prof_id for prof_id in professor_ids)
        return redirect(f"{reverse('extra_curricular:pendencia_lote')}?ids={query_string}")

class PendenciaLoteView(LoginRequiredMixin, PerfilRequiredMixin, View):
    allowed_profiles = ["COORDENADOR_UNIDADE", "DESUP"]
    template_name = "extra_curricular/pendencia_lote.html"

    def get(self, request):
        from apps.professors.models import Professor
        user = request.user
        ids_str = request.GET.get("ids", "")
        if not ids_str:
            return redirect("extra_curricular:pendencia_list")
            
        prof_ids = [int(i) for i in ids_str.split(",") if i.isdigit()]
        professores = Professor.objects.filter(id__in=prof_ids)
        
        if user.perfil == "COORDENADOR_UNIDADE":
            professores = professores.filter(unidade_principal=user.unidade)
            
        pendencias = PendenciaExtra.objects.filter(professor__in=professores, semestre=_semestre_atual())
        
        # Pega o primeiro SEI encontrado para preencher o input único
        sei_unico = pendencias.exclude(sei_numero__isnull=True).exclude(sei_numero="").first()
        sei_numero = sei_unico.sei_numero if sei_unico else ""

        # Busca todos os itens das pendências
        from apps.extra_curricular.models import OrientacaoTCC, AtividadeExtensionista, ReducaoCargaHoraria
        tcc_items = OrientacaoTCC.objects.filter(pendencia__in=pendencias).select_related('pendencia__professor')
        ext_items = AtividadeExtensionista.objects.filter(pendencia__in=pendencias).select_related('pendencia__professor')
        red_items = ReducaoCargaHoraria.objects.filter(pendencia__in=pendencias).select_related('pendencia__professor')

        ctx = {
            "professores": professores,
            "pendencias": pendencias,
            "sei_numero": sei_numero,
            "semestre": _semestre_atual(),
            "tcc_items": tcc_items,
            "ext_items": ext_items,
            "red_items": red_items,
            "is_coordenador": user.perfil == "COORDENADOR_UNIDADE",
            "is_desup": user.perfil == "DESUP",
            "query_string": ids_str,
            "parecer_tcc_forms": [
                (item, ParecerTCCForm(instance=item, prefix=f"ptcc-{item.pk}"))
                for item in tcc_items
            ],
            "parecer_ext_forms": [
                (item, ParecerExtensaoForm(instance=item, prefix=f"pext-{item.pk}"))
                for item in ext_items
            ],
            "parecer_red_forms": [
                (item, ParecerReducaoForm(instance=item, prefix=f"pred-{item.pk}"))
                for item in red_items
            ],
        }
        ctx.update(build_window_lock_context(
            user,
            unidade=user.unidade if user.perfil == "COORDENADOR_UNIDADE" else None,
            area_label='Justificativas',
            action_label='alterar justificativas extracurriculares',
            target_label='mesa de trabalho',
        ))
        return render(request, self.template_name, ctx)


class PendenciaDetailView(LoginRequiredMixin, PerfilRequiredMixin, DetailView):
    allowed_profiles = ["COORDENADOR_UNIDADE", "DESUP"]
    model = PendenciaExtra
    template_name = "extra_curricular/pendencia_detail.html"

    def get_queryset(self):
        qs = PendenciaExtra.objects.select_related("professor", "unidade", "professor__tipo_contrato")
        user = self.request.user
        if user.perfil == "COORDENADOR_UNIDADE":
            if user.unidade:
                return qs.filter(unidade=user.unidade)
            return qs.none()
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        object_ = self.object
        tcc_items = list(object_.orientacoes_tcc.all())
        ext_items = list(object_.atividades_extensao.all())
        red_items = list(object_.reducoes_ch.all())

        ctx.update({
            "is_coordenador": self.request.user.perfil == "COORDENADOR_UNIDADE",
            "is_desup": self.request.user.perfil == "DESUP" or self.request.user.is_superuser,
            "tcc_items": tcc_items,
            "ext_items": ext_items,
            "red_items": red_items,
            "tcc_form": OrientacaoTCCFormSet(instance=object_, prefix="tcc"),
            "ext_form": AtividadeExtensionistaFormSet(instance=object_, prefix="ext"),
            "red_form": ReducaoCargaHorariaFormSet(instance=object_, prefix="red"),
            "parecer_tcc_forms": [
                (item, ParecerTCCForm(instance=item, prefix=f"ptcc-{item.pk}"))
                for item in tcc_items
            ],
            "parecer_ext_forms": [
                (item, ParecerExtensaoForm(instance=item, prefix=f"pext-{item.pk}"))
                for item in ext_items
            ],
            "parecer_red_forms": [
                (item, ParecerReducaoForm(instance=item, prefix=f"pred-{item.pk}"))
                for item in red_items
            ],
        })
        ctx.update(build_window_lock_context(
            self.request.user,
            unidade=object_.unidade,
            area_label='Justificativas',
            action_label='alterar justificativas extracurriculares',
            target_label=str(object_.professor.nome),
        ))
        return ctx

# ══════════════════════════════════════════════════════════════════════════════
# Salvar itens de justificativa via POST (HTMX ou redirect)
# Rotas separadas por tipo para manter código limpo
# ══════════════════════════════════════════════════════════════════════════════
class _BaseItemSaveView(LoginRequiredMixin, PerfilRequiredMixin, View):
    """Base para salvar itens inline de justificativa. Apenas Coordenador."""
    allowed_profiles = ["COORDENADOR_UNIDADE", "DESUP"]
    formset_class    = None
    prefix           = None
    item_template    = None  # partial para re-renderizar via HTMX

    def _check_permissao(self, user, pendencia):
        if user.is_superuser or user.perfil == "DESUP":
            return True
        if user.perfil == "COORDENADOR_UNIDADE" and pendencia.unidade == user.unidade:
            return True
        raise PermissionDenied

    def post(self, request, pk):
        from django.shortcuts import render
        from django.utils import timezone
        
        pendencia = get_object_or_404(PendenciaExtra, pk=pk)
        self._check_permissao(request.user, pendencia)

        blocked = enforce_window_or_redirect(
            request,
            area_label='Justificativas',
            action_label='alterar justificativas extracurriculares',
            target_label=str(pendencia.professor.nome),
            unidade=pendencia.unidade,
            fallback_url=reverse_lazy("extra_curricular:pendencia_detail", kwargs={"pk": pk}),
        )
        if blocked:
            return blocked

        # Regra de 5 dias sem SEI = bloqueio de edições
        if not pendencia.sei_numero:
            dias_passados = (timezone.now() - pendencia.data_criacao).days
            if dias_passados >= 5:
                messages.error(request, "Prazo de 5 dias excedido. O preenchimento do número SEI no cabeçalho é OBRIGATÓRIO para prosseguir com novas justificativas.")
                return redirect(reverse_lazy("extra_curricular:pendencia_detail", kwargs={"pk": pk}))

        formset = self.formset_class(
            request.POST, instance=pendencia, prefix=self.prefix
        )
        if formset.is_valid():
            formset.save()
            messages.success(request, "Salvo com sucesso.")
            return redirect(reverse_lazy("extra_curricular:pendencia_detail", kwargs={"pk": pk}))

        # Re-renderizar a página com erros
        return redirect(reverse_lazy("extra_curricular:pendencia_detail", kwargs={"pk": pk}))


class SalvarTCCView(_BaseItemSaveView):
    formset_class = OrientacaoTCCFormSet
    prefix        = "tcc"


class SalvarExtensaoView(_BaseItemSaveView):
    formset_class = AtividadeExtensionistaFormSet
    prefix        = "ext"


class SalvarReducaoView(_BaseItemSaveView):
    formset_class = ReducaoCargaHorariaFormSet
    prefix        = "red"


# ══════════════════════════════════════════════════════════════════════════════
# Views de Lote — operam sobre múltiplas pendências de uma vez
# (mesa de trabalho: /extracurriculares/pendencias/lote/...)
# ══════════════════════════════════════════════════════════════════════════════
class _BaseLoteItemSaveView(LoginRequiredMixin, PerfilRequiredMixin, View):
    """Base para salvar itens em lote via POST."""
    allowed_profiles = ["COORDENADOR_UNIDADE", "DESUP"]
    formset_class    = None
    prefix           = None

    def _get_pendencias(self, request):
        ids_str = request.POST.get("ids", "")
        ids = [int(i) for i in ids_str.split(",") if i.isdigit()]
        qs = PendenciaExtra.objects.filter(pk__in=ids)
        if request.user.perfil == "COORDENADOR_UNIDADE":
            qs = qs.filter(unidade=request.user.unidade)
        return qs

    def post(self, request):
        pendencias = self._get_pendencias(request)
        unidade = pendencias.first().unidade if pendencias.exists() else getattr(request.user, 'unidade', None)
        blocked = enforce_window_or_redirect(
            request,
            area_label='Justificativas',
            action_label='alterar justificativas extracurriculares',
            target_label='mesa de trabalho',
            unidade=unidade,
            fallback_url=reverse_lazy('extra_curricular:pendencia_lote'),
        )
        if blocked:
            return blocked

        for pendencia in pendencias:
            formset = self.formset_class(
                request.POST, instance=pendencia, prefix=self.prefix
            )
            if formset.is_valid():
                formset.save()
        messages.success(request, "Itens salvos em lote com sucesso.")
        ids_str = request.POST.get("ids", "")
        return redirect(f"{reverse_lazy('extra_curricular:pendencia_lote')}?ids={ids_str}")


class SalvarTCCLoteView(LoginRequiredMixin, PerfilRequiredMixin, View):
    allowed_profiles = ["COORDENADOR_UNIDADE"]

    def post(self, request):
        ids_str = request.POST.get("ids", "")
        pendencia_id = request.POST.get("pendencia_id")
        num_orientandos = request.POST.get("num_orientandos")
        
        if pendencia_id and num_orientandos:
            pendencia = get_object_or_404(PendenciaExtra, pk=pendencia_id, unidade=request.user.unidade)
            blocked = enforce_window_or_redirect(
                request,
                area_label='Justificativas',
                action_label='alterar justificativas extracurriculares',
                target_label=str(pendencia.professor.nome),
                unidade=pendencia.unidade,
                fallback_url=reverse_lazy('extra_curricular:pendencia_lote'),
            )
            if blocked:
                return blocked
            OrientacaoTCC.objects.create(pendencia=pendencia, num_orientandos=int(num_orientandos))
            messages.success(request, "Orientação de TCC adicionada com sucesso.")
        return redirect(f"{reverse_lazy('extra_curricular:pendencia_lote')}?ids={ids_str}&open=tcc")


class SalvarExtensaoLoteView(LoginRequiredMixin, PerfilRequiredMixin, View):
    allowed_profiles = ["COORDENADOR_UNIDADE"]

    def post(self, request):
        ids_str = request.POST.get("ids", "")
        pendencia_id = request.POST.get("pendencia_id")
        num_estudantes = request.POST.get("num_estudantes")
        
        if pendencia_id and num_estudantes:
            pendencia = get_object_or_404(PendenciaExtra, pk=pendencia_id, unidade=request.user.unidade)
            blocked = enforce_window_or_redirect(
                request,
                area_label='Justificativas',
                action_label='alterar justificativas extracurriculares',
                target_label=str(pendencia.professor.nome),
                unidade=pendencia.unidade,
                fallback_url=reverse_lazy('extra_curricular:pendencia_lote'),
            )
            if blocked:
                return blocked
            AtividadeExtensionista.objects.create(pendencia=pendencia, num_estudantes=int(num_estudantes))
            messages.success(request, "Atividade extensionista adicionada com sucesso.")
        return redirect(f"{reverse_lazy('extra_curricular:pendencia_lote')}?ids={ids_str}&open=ext")


class SalvarReducaoLoteView(LoginRequiredMixin, PerfilRequiredMixin, View):
    allowed_profiles = ["COORDENADOR_UNIDADE"]

    def post(self, request):
        ids_str = request.POST.get("ids", "")
        pendencia_id = request.POST.get("pendencia_id")
        motivo_reducao = request.POST.get("motivo_reducao")
        horas_reduzidas = request.POST.get("horas_reduzidas")
        
        if pendencia_id and motivo_reducao and horas_reduzidas:
            pendencia = get_object_or_404(PendenciaExtra, pk=pendencia_id, unidade=request.user.unidade)
            blocked = enforce_window_or_redirect(
                request,
                area_label='Justificativas',
                action_label='alterar justificativas extracurriculares',
                target_label=str(pendencia.professor.nome),
                unidade=pendencia.unidade,
                fallback_url=reverse_lazy('extra_curricular:pendencia_lote'),
            )
            if blocked:
                return blocked
            ReducaoCargaHoraria.objects.create(
                pendencia=pendencia, 
                motivo_reducao=motivo_reducao,
                horas_reduzidas=Decimal(horas_reduzidas.replace(',', '.'))
            )
            messages.success(request, "Redução de carga horária adicionada com sucesso.")
        return redirect(f"{reverse_lazy('extra_curricular:pendencia_lote')}?ids={ids_str}&open=red")


class DeletarItemLoteView(LoginRequiredMixin, PerfilRequiredMixin, View):
    """Deleta um item de uma pendência em lote, redirecionando de volta."""
    allowed_profiles = ["COORDENADOR_UNIDADE", "DESUP"]

    _map = {
        "tcc": OrientacaoTCC,
        "ext": AtividadeExtensionista,
        "red": ReducaoCargaHoraria,
    }

    def post(self, request, tipo, item_pk):
        model = self._map.get(tipo)
        if not model:
            messages.error(request, "Tipo inválido.")
            return redirect("extra_curricular:pendencia_list")
        item = get_object_or_404(model, pk=item_pk)
        pendencia = item.pendencia
        user = request.user
        if user.perfil == "COORDENADOR_UNIDADE" and pendencia.unidade != user.unidade:
            raise PermissionDenied
        blocked = enforce_window_or_redirect(
            request,
            area_label='Justificativas',
            action_label='excluir justificativa extracurricular',
            target_label=str(pendencia.professor.nome),
            unidade=pendencia.unidade,
            fallback_url=reverse_lazy('extra_curricular:pendencia_lote'),
        )
        if blocked:
            return blocked
        item.delete()
        sincronizar_status_pendencia(pendencia)
        messages.success(request, "Item removido.")
        ids_str = request.POST.get("ids", "")
        return redirect(f"{reverse_lazy('extra_curricular:pendencia_lote')}?ids={ids_str}")


class EnviarParaDesupLoteView(LoginRequiredMixin, PerfilRequiredMixin, View):
    """Envia para DESUP todas as pendências do lote que possuem SEI."""
    allowed_profiles = ["COORDENADOR_UNIDADE"]

    def post(self, request):
        ids_str = request.POST.get("ids", "")
        prof_ids = [int(i) for i in ids_str.split(",") if i.isdigit()]
        semestre = _semestre_atual()
        pendencias = PendenciaExtra.objects.filter(
            professor_id__in=prof_ids,
            semestre=semestre,
            unidade=request.user.unidade
        )
        blocked = enforce_window_or_redirect(
            request,
            area_label='Justificativas',
            action_label='enviar justificativas para a DESUP',
            target_label='mesa de trabalho',
            unidade=request.user.unidade,
            fallback_url=reverse_lazy('extra_curricular:pendencia_lote'),
        )
        if blocked:
            return blocked
        enviadas = 0
        nomes_professores = []
        for pendencia in pendencias:
            if pendencia.sei_numero:
                pendencia.status = PendenciaExtra.StatusChoices.ENVIADO
                pendencia.save()
                enviadas += 1
                nomes_professores.append(pendencia.professor.nome)
        if enviadas:
            # Criar notificação para DESUP
            from apps.core.models import Notificacao
            unidade = request.user.unidade
            nomes_str = ", ".join(nomes_professores[:5])
            if len(nomes_professores) > 5:
                nomes_str += f" e mais {len(nomes_professores) - 5}"
            from django.urls import reverse
            Notificacao.objects.create(
                destinatario=None,
                unidade_destino=None,
                titulo=f"📋 Pendência Extracurricular — {unidade.sigla}",
                mensagem=f"A unidade {unidade.nome} enviou {enviadas} justificativa(s) extracurricular(es) para aprovação ({semestre}). Docentes: {nomes_str}.",
                url_acao=f"{reverse('extra_curricular:pendencia_list')}?unidade_id={unidade.pk}&semestre={semestre}"
            )
            messages.success(request, f"{enviadas} pendência(s) enviada(s) para a DESUP.")
            return redirect("extra_curricular:pendencia_list")
        if not enviadas:
            messages.error(request, "Nenhuma pendência enviada. Verifique se o número SEI foi preenchido.")
            ids_str = request.POST.get("ids", "")
            return redirect(
                f"{reverse_lazy('extra_curricular:pendencia_lote')}?ids={ids_str}&sei_error=1"
            )


class PendenciaSEIUpdateLoteView(LoginRequiredMixin, PerfilRequiredMixin, View):
    """Atualiza o número SEI de todas as pendências do lote."""
    allowed_profiles = ["COORDENADOR_UNIDADE", "DESUP"]

    def post(self, request):
        ids_str = request.POST.get("ids", "")
        sei_numero = request.POST.get("sei_numero", "").strip()
        prof_ids = [int(i) for i in ids_str.split(",") if i.isdigit()]
        semestre = _semestre_atual()
        qs = PendenciaExtra.objects.filter(professor_id__in=prof_ids, semestre=semestre)
        if request.user.perfil == "COORDENADOR_UNIDADE":
            qs = qs.filter(unidade=request.user.unidade)
        blocked = enforce_window_or_redirect(
            request,
            area_label='Justificativas',
            action_label='alterar SEI das justificativas',
            target_label='mesa de trabalho',
            unidade=request.user.unidade if request.user.perfil == "COORDENADOR_UNIDADE" else None,
            fallback_url=reverse_lazy('extra_curricular:pendencia_lote'),
        )
        if blocked:
            return blocked
        updated = qs.update(sei_numero=sei_numero)
        messages.success(request, f"SEI atualizado em {updated} pendência(s).")
        return redirect(f"{reverse_lazy('extra_curricular:pendencia_lote')}?ids={ids_str}")


# ══════════════════════════════════════════════════════════════════════════════
# ParecerUpdateViews — exclusivo DESUP (atualiza parecer inline via POST)
# ══════════════════════════════════════════════════════════════════════════════
def _ch_aprovada_outros(pendencia, model_atual, item_pk):
    """Soma a CH já aprovada nos demais itens da pendência (exclui o item sendo salvo)."""
    total = 0.0
    grupos = (
        (OrientacaoTCC, pendencia.orientacoes_tcc),
        (AtividadeExtensionista, pendencia.atividades_extensao),
        (ReducaoCargaHoraria, pendencia.reducoes_ch),
    )
    for model, related in grupos:
        qs = related.all()
        if model == model_atual:
            qs = qs.exclude(pk=item_pk)
        total += sum(float(item.ch_aprovada) for item in qs)
    return total


class _BaseParecerView(LoginRequiredMixin, PerfilRequiredMixin, View):
    allowed_profiles = ["DESUP"]
    model_class      = None
    form_class       = None
    prefix_base      = ""

    def post(self, request, pk, item_pk):
        pendencia = get_object_or_404(PendenciaExtra, pk=pk)
        item      = get_object_or_404(self.model_class, pk=item_pk, pendencia=pendencia)
        form      = self.form_class(
            request.POST,
            instance=item,
            prefix=f"{self.prefix_base}-{item_pk}",
        )
        if form.is_valid():
            instance = form.save(commit=False)
            limite = pendencia.professor.limite_horas_extra_efetivo
            outros = _ch_aprovada_outros(pendencia, self.model_class, item.pk)
            if (outros + float(instance.ch_aprovada)) > limite:
                messages.error(
                    request,
                    f"Limite de horas extras excedido. O docente {pendencia.professor.nome} possui "
                    f"{limite}h disponíveis e as demais justificativas já somam {outros}h."
                )
                return redirect(reverse_lazy("extra_curricular:pendencia_detail", kwargs={"pk": pk}))
            instance.save()
            sincronizar_status_pendencia(pendencia)
            messages.success(request, "Parecer atualizado.")
        else:
            messages.error(request, f"Erro ao salvar parecer: {form.errors}")
        return redirect(reverse_lazy("extra_curricular:pendencia_detail", kwargs={"pk": pk}))


class ParecerTCCUpdateView(_BaseParecerView):
    model_class = OrientacaoTCC
    form_class  = ParecerTCCForm
    prefix_base = "ptcc"


class ParecerExtensaoUpdateView(_BaseParecerView):
    model_class = AtividadeExtensionista
    form_class  = ParecerExtensaoForm
    prefix_base = "pext"


class ParecerReducaoUpdateView(_BaseParecerView):
    model_class = ReducaoCargaHoraria
    form_class  = ParecerReducaoForm
    prefix_base = "pred"


class PendenciaStatusUpdateView(LoginRequiredMixin, PerfilRequiredMixin, View):
    allowed_profiles = ["DESUP"]

    status_permitidos = {
        PendenciaExtra.StatusChoices.ENVIADO,
        PendenciaExtra.StatusChoices.APROVADO,
    }

    _item_models = {
        "tcc": OrientacaoTCC,
        "ext": AtividadeExtensionista,
        "red": ReducaoCargaHoraria,
    }

    def post(self, request, pk):
        pendencia = get_object_or_404(PendenciaExtra, pk=pk)
        status = request.POST.get("status")
        motivo = request.POST.get("motivo_status_desup", "").strip()
        item_tipo = request.POST.get("item_tipo", "").strip()
        item_pk = request.POST.get("item_pk", "").strip()
        horas_raw = request.POST.get("item_horas_aprovadas", "").strip()

        if status not in self.status_permitidos:
            messages.error(request, "Status invalido para decisao da DESUP.")
            return redirect(request.META.get("HTTP_REFERER", reverse_lazy("extra_curricular:pendencia_list")))

        # Horas aprovadas para o item específico desta linha (não o total do professor)
        item = None
        if item_tipo and item_pk:
            model = self._item_models.get(item_tipo)
            if model:
                item = get_object_or_404(model, pk=item_pk, pendencia=pendencia)

        horas_aprovadas_item = None
        if horas_raw:
            try:
                horas_aprovadas_item = Decimal(horas_raw.replace(",", "."))
                if horas_aprovadas_item < 0:
                    raise InvalidOperation
            except InvalidOperation:
                messages.error(request, "Valor inválido para horas aprovadas.")
                return redirect(request.META.get("HTTP_REFERER", reverse_lazy("extra_curricular:pendencia_list")))

        if item is not None and horas_aprovadas_item is not None:
            outros = _ch_aprovada_outros(pendencia, type(item), item.pk)
            limite = pendencia.professor.limite_horas_extra_efetivo
            if (outros + float(horas_aprovadas_item)) > limite:
                messages.error(
                    request,
                    f"Limite de horas extras excedido. O docente {pendencia.professor.nome} possui "
                    f"{limite}h disponíveis e as demais justificativas já somam {outros}h."
                )
                return redirect(request.META.get("HTTP_REFERER", reverse_lazy("extra_curricular:pendencia_list")))
            item.horas_aprovadas = horas_aprovadas_item
            item.save(update_fields=["horas_aprovadas"])

        pendencia.status = status
        pendencia.motivo_status_desup = motivo
        pendencia.save(update_fields=["status", "motivo_status_desup", "data_atualizacao"])

        parecer = {
            PendenciaExtra.StatusChoices.ENVIADO: "PENDENTE",
            PendenciaExtra.StatusChoices.APROVADO: "APROVADO",
        }[status]
        for related in (pendencia.orientacoes_tcc, pendencia.atividades_extensao, pendencia.reducoes_ch):
            related.update(parecer_desup=parecer, motivo_parecer=motivo)

        messages.success(request, "Status extracurricular atualizado.")
        return redirect(request.META.get("HTTP_REFERER", reverse_lazy("extra_curricular:pendencia_list")))


# ══════════════════════════════════════════════════════════════════════════════
# API JSON para cálculo de CH (usado via JS no frontend)
# ══════════════════════════════════════════════════════════════════════════════
class CalcularCHView(LoginRequiredMixin, View):
    def get(self, request):
        tipo = request.GET.get("tipo")  # "tcc" | "extensao"
        try:
            n = int(request.GET.get("n", 0))
        except (TypeError, ValueError):
            n = 0

        if tipo == "tcc":
            from apps.extra_curricular.services import calcular_ch_tcc
            ch = float(calcular_ch_tcc(n))
        elif tipo == "extensao":
            from apps.extra_curricular.services import calcular_ch_extensao
            ch = float(calcular_ch_extensao(n))
        else:
            return JsonResponse({"error": "tipo inválido"}, status=400)

        return JsonResponse({"ch": ch})


# ══════════════════════════════════════════════════════════════════════════════
# Deletar itens individuais
# ══════════════════════════════════════════════════════════════════════════════
class DeletarItemView(LoginRequiredMixin, PerfilRequiredMixin, View):
    allowed_profiles = ["COORDENADOR_UNIDADE", "DESUP"]

    _map = {
        "tcc":    OrientacaoTCC,
        "ext":    AtividadeExtensionista,
        "red":    ReducaoCargaHoraria,
    }

    def post(self, request, pk, tipo, item_pk):
        pendencia = get_object_or_404(PendenciaExtra, pk=pk)
        user = request.user
        if user.perfil == "COORDENADOR_UNIDADE" and pendencia.unidade != user.unidade:
            raise PermissionDenied

        model = self._map.get(tipo)
        if not model:
            messages.error(request, "Tipo inválido.")
            return redirect(reverse_lazy("extra_curricular:pendencia_detail", kwargs={"pk": pk}))

        item = get_object_or_404(model, pk=item_pk, pendencia=pendencia)
        item.delete()
        sincronizar_status_pendencia(pendencia)
        messages.success(request, "Item removido.")
        return redirect(reverse_lazy("extra_curricular:pendencia_detail", kwargs={"pk": pk}))


# ══════════════════════════════════════════════════════════════════════════════
# Enviar para DESUP
# ══════════════════════════════════════════════════════════════════════════════
class EnviarParaDesupView(LoginRequiredMixin, PerfilRequiredMixin, View):
    allowed_profiles = ["COORDENADOR_UNIDADE"]

    def post(self, request, pk):
        pendencia = get_object_or_404(PendenciaExtra, pk=pk)
        user = request.user
        if pendencia.unidade != user.unidade and not user.is_superuser:
            raise PermissionDenied
        blocked = enforce_window_or_redirect(
            request,
            area_label='Justificativas',
            action_label='enviar justificativa para a DESUP',
            target_label=str(pendencia.professor.nome),
            unidade=pendencia.unidade,
            fallback_url=reverse_lazy("extra_curricular:pendencia_detail", kwargs={"pk": pk}),
        )
        if blocked:
            return blocked

        if not pendencia.sei_numero:
            messages.error(request, "Informe o número SEI antes de enviar para a DESUP.")
            return redirect(
                reverse_lazy("extra_curricular:pendencia_detail", kwargs={"pk": pk}).__str__() + "?sei_error=1"
            )

        pendencia.status = PendenciaExtra.StatusChoices.ENVIADO
        pendencia.save()
        messages.success(request, "Justificativa enviada para análise da DESUP.")
        return redirect(reverse_lazy("extra_curricular:pendencia_detail", kwargs={"pk": pk}))

# ══════════════════════════════════════════════════════════════════════════════
# Avisar Unidade (DESUP)
# ══════════════════════════════════════════════════════════════════════════════
class AvisarUnidadeView(LoginRequiredMixin, PerfilRequiredMixin, View):
    allowed_profiles = ["DESUP"]

    def post(self, request, pk):
        from apps.core.models import Notificacao
        from django.urls import reverse
        
        pendencia = get_object_or_404(PendenciaExtra, pk=pk)
        
        # Cria a notificação para a unidade
        Notificacao.objects.create(
            unidade_destino=pendencia.unidade,
            titulo="Aviso de Pendência Extracurricular",
            mensagem=f"O(a) docente {pendencia.professor.nome} possui carga horária pendente no semestre {pendencia.semestre}. Por favor, acesse o módulo Extracurricular e justifique a falta.",
            url_acao=reverse('extra_curricular:pendencia_detail', args=[pendencia.pk])
        )
        
        messages.success(request, f"Aviso enviado para a unidade {pendencia.unidade.sigla}.")

        raw_next = request.POST.get("next", request.META.get("HTTP_REFERER", "/"))
        next_url = raw_next if url_has_allowed_host_and_scheme(
            raw_next, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        ) else "/"
        return redirect(next_url)

# ══════════════════════════════════════════════════════════════════════════════
# Editar SEI da Pendência (Coordenador)
# ══════════════════════════════════════════════════════════════════════════════
class PendenciaSEIUpdateView(LoginRequiredMixin, PerfilRequiredMixin, UpdateView):
    allowed_profiles = ["COORDENADOR_UNIDADE", "DESUP"]
    model = PendenciaExtra
    fields = ["sei_numero"]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(build_window_lock_context(
            self.request.user,
            unidade=self.object.unidade,
            area_label='Justificativas',
            action_label='alterar SEI das justificativas',
            target_label=str(self.object.professor.nome),
        ))
        return ctx
    
    def form_valid(self, form):
        pendencia = form.instance
        blocked = enforce_window_or_redirect(
            self.request,
            area_label='Justificativas',
            action_label='alterar SEI das justificativas',
            target_label=str(pendencia.professor.nome) if getattr(pendencia, 'professor_id', None) else 'pendência',
            unidade=pendencia.unidade if getattr(pendencia, 'unidade_id', None) else getattr(self.request.user, 'unidade', None),
            fallback_url=reverse_lazy("extra_curricular:pendencia_detail", kwargs={"pk": pendencia.pk}),
        )
        if blocked:
            return blocked
        messages.success(self.request, "Número SEI atualizado com sucesso.")
        return super().form_valid(form)
        
    def form_invalid(self, form):
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(self.request, f"Erro no campo {field}: {error}")
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse_lazy("extra_curricular:pendencia_detail", kwargs={"pk": self.object.pk})
        
    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        user = self.request.user
        if user.perfil == "COORDENADOR_UNIDADE" and obj.unidade != user.unidade:
            raise PermissionDenied
        return obj
