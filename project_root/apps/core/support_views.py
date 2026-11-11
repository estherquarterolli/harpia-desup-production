from urllib.parse import urlencode

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.generic import FormView, TemplateView

from apps.accounts.mixins import PerfilRequiredMixin
from .models import SolicitacaoSuporte
from .support import (
    SuporteErro, email_suporte, enviar_suporte, ler_contexto, motivo_email_indisponivel,
    novo_contexto, pagina_suporte,
)
from .support_forms import SuporteForm


@method_decorator(never_cache, name='dispatch')
class CentralAjudaView(LoginRequiredMixin, PerfilRequiredMixin, FormView):
    allowed_profiles = ['COORDENADOR_UNIDADE', 'DESUP']
    template_name = 'core/central_ajuda.html'
    form_class = SuporteForm

    def get(self, request, *args, **kwargs):
        # Compatibilidade com os links anteriores, quando FAQ era uma aba.
        if request.GET.get('aba') == 'faq' and not request.GET.get('enviado'):
            query = urlencode({'pagina': request.GET.get('pagina', '')})
            return HttpResponseRedirect(f'{reverse("core:faq")}?{query}')
        return super().get(request, *args, **kwargs)

    def get_initial(self):
        pagina = pagina_suporte(self.request.GET.get('pagina'))
        return {'contexto': novo_contexto(self.request.user, pagina)}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['aba_ativa'] = 'suporte'
        context['suporte_indisponivel_motivo'] = motivo_email_indisponivel()
        context['suporte_disponivel'] = not context['suporte_indisponivel_motivo']
        context['email_suporte'] = email_suporte()
        form = context['form']
        try:
            context['pagina_origem'] = ler_contexto(form['contexto'].value(), self.request.user)['pagina']
        except ValidationError:
            context['pagina_origem'] = 'Central de Ajuda'
        context['recibo'] = None
        try:
            referencia = self.request.GET.get('enviado')
            if referencia:
                context['recibo'] = SolicitacaoSuporte.objects.filter(
                    pk=referencia, usuario=self.request.user, status=SolicitacaoSuporte.Status.ENVIADO,
                ).first()
        except (ValidationError, ValueError):
            pass
        return context

    def form_valid(self, form):
        try:
            contexto = ler_contexto(form.cleaned_data['contexto'], self.request.user)
        except ValidationError as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)
        try:
            recibo = enviar_suporte(self.request.user, form.cleaned_data, contexto)
        except SuporteErro as exc:
            form.add_error(None, str(exc))
            # Falhas concluídas recebem uma nova chave, preservando os campos;
            # reservas em andamento conservam a chave para não duplicar envios.
            if exc.renovar_contexto:
                form.data = form.data.copy()
                form.data['contexto'] = novo_contexto(self.request.user, contexto['pagina'])
            return self.form_invalid(form)
        return HttpResponseRedirect(f'{reverse("core:central_ajuda")}?enviado={recibo.pk}')


@method_decorator(never_cache, name='dispatch')
class FaqView(LoginRequiredMixin, PerfilRequiredMixin, TemplateView):
    allowed_profiles = ['COORDENADOR_UNIDADE', 'DESUP']
    template_name = 'core/central_ajuda.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['aba_ativa'] = 'faq'
        context['faq'] = self.get_faq()
        return context

    def get_faq(self):
        unidade = self.request.user.perfil == 'COORDENADOR_UNIDADE'
        return [
            ('Como consultar os professores?',
             'Abra Professores no menu lateral. Pesquise por nome, ID funcional ou matrícula e refine com os filtros disponíveis. A visão da unidade apresenta os vínculos da própria unidade.'),
            ('Como atualizar a equipe diretiva?',
             'Abra Equipe diretiva no menu lateral. Clique em um cargo para consultar ocupantes e as ações disponíveis. Use Preencher cargo ou Adicionar ocupante quando houver vaga. A redução de carga da unidade é definida pela DESUP.' if unidade else
             'Abra Equipe diretiva e selecione a unidade. Clique em um cargo para consultar e gerenciar seus ocupantes. A engrenagem permite editar o cargo e a redução da unidade selecionada.'),
            ('Como registrar e acompanhar justificativas extracurriculares?',
             'Abra Extracurriculares. Use Nova justificativa para registrar as atividades; a aba Rascunhos permite continuar os registros ainda não enviados. Na aba Justificativas, consulte os envios e seus status. Alterações nessa área respeitam a janela de entrega.' if unidade else
             'Abra Extracurriculares para consultar pendências e justificativas. Use a pesquisa e os filtros de semestre, unidade, status e tipo de justificativa para localizar os registros e acompanhar a análise.'),
            ('A janela de entrega está fechada. O suporte libera alterações?',
             'Não. O suporte técnico não abre janelas nem altera dados. Na área de alocação ou de extracurriculares, use Solicitar abertura no aviso de janela fechada para seguir o fluxo administrativo existente.' if unidade else
             'O suporte técnico não abre janelas nem altera dados. A gestão das janelas de entrega permanece na opção Entrega do menu lateral.'),
            ('Onde encontro o tutorial da página?',
             'O botão com ponto de interrogação no cabeçalho abre o tutorial da página atual. No painel do tutorial, o link Perguntas frequentes e suporte abre esta Central.'),
            ('O que fazer ao encontrar dados inconsistentes ou um erro?',
             'Use Solicitar suporte nesta Central, escolha o tipo e descreva a funcionalidade, o comportamento observado e o esperado. Evite incluir dados pessoais de terceiros, senhas ou informações sigilosas. O contato não substitui pedidos de cadastro, cessão, RAT ou aprovações administrativas.'),
        ]
