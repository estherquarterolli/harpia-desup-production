from django.views.generic import ListView, TemplateView
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from apps.accounts.mixins import PerfilRequiredMixin
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from apps.allocations import services
from apps.allocations.models import AlocacaoCurricular, AlocacaoTurmaDocente
from apps.core.services import build_window_lock_context, enforce_window_or_redirect

# `AlocacaoCurricular.turno` é NOT NULL. O formulário agora exige o turno para novas
# matrizes, mas matrizes legadas/importadas ainda podem ter `CurriculumMatrix.turno=NULL`
# durante o saneamento. Nesses casos o consolidado mantém o fallback para Manhã e avisa
# a DESUP, evitando IntegrityError/500 sem mascarar que o cadastro precisa ser corrigido.
TURNO_PADRAO_ALOCACAO = 'M'


def _semestre_atual():
    return services.semestre_atual()


def _ids_de_outra_unidade(professor_ids, unidade_id):
    """Subconjunto de `professor_ids` que NÃO pertence à unidade (principal ou vínculo)."""
    from django.db.models import Q
    from apps.professors.models import Professor

    ids = {pid for pid in professor_ids if pid}
    if not ids or not unidade_id:
        return set()
    vinculados = set(
        Professor.objects.filter(pk__in=ids).filter(
            Q(unidade_principal_id=unidade_id) | Q(unidades__id=unidade_id)
        ).values_list('pk', flat=True)
    )
    return ids - vinculados


def _cargos_diretivos_vigentes():
    """{professor_id: 'Cargo (SIGLA)'} dos ocupantes vigentes da equipe diretiva.

    Usado para avisar (amarelo) quando alguém da equipe diretiva é alocado em sala.
    """
    from django.db.models import Q
    from django.utils import timezone
    from apps.core.models import OcupacaoEquipeDiretiva

    hoje = timezone.localdate()
    ocupacoes = OcupacaoEquipeDiretiva.objects.filter(
        Q(data_fim__isnull=True) | Q(data_fim__gte=hoje), data_inicio__lte=hoje,
    ).select_related('cargo', 'unidade')
    cargos = {}
    for o in ocupacoes:
        cargos.setdefault(o.professor_id, []).append(f'{o.cargo.nome} ({o.unidade.sigla})')
    return {pid: ', '.join(nomes) for pid, nomes in cargos.items()}

class AllocCurricularView(LoginRequiredMixin, PerfilRequiredMixin, TemplateView):
    template_name = "allocations/alloc_curricular.html"
    allowed_profiles = ['DESUP', 'COORDENADOR_UNIDADE']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        perfil = user.perfil

        from apps.core.models import Unidade
        from apps.professors.models import Professor
        from apps.courses.models import CurriculumMatrix, MatrixComponent
        from django.core.paginator import Paginator
        from django.db.models import Prefetch

        context['unidades'] = Unidade.objects.filter(status=True).order_by('nome')
        unidade_id = self.request.GET.get('unidade_id')
        
        if perfil == 'COORDENADOR_UNIDADE':
            if not user.unidade:
                return context
            unidade_id = user.unidade.id
            
        context['unidade_selecionada_id'] = str(unidade_id) if unidade_id else ''

        if not unidade_id and perfil == 'COORDENADOR_UNIDADE':
            return context
            
        unidade_selecionada = Unidade.objects.filter(id=unidade_id).first() if unidade_id else None
        context['unidade_selecionada'] = unidade_selecionada

        # A base de docentes é consultada sob demanda pelo autocomplete. Este
        # queryset permanece no contexto apenas por compatibilidade com integrações
        # existentes; o template não o materializa.
        if perfil == 'COORDENADOR_UNIDADE' and not user.is_superuser:
            context['professores_unidade'] = services.professores_autorizados_unidade_qs(user.unidade_id).order_by('rh_nome')
        else:
            context['professores_unidade'] = Professor.objects.all().order_by('rh_nome')

        # Antes, abrir a tela DESUP sem filtro carregava matrizes e componentes de
        # TODAS as unidades. Além de confuso, era o principal pico de memória/DOM.
        if not unidade_id:
            context.update({
                'matrizes_data': [],
                'alocacao_curricular_preenchida': False,
                'componentes_sem_docente': 0,
                'alocacao_aprovada': False,
            })
            context.update(build_window_lock_context(
                user,
                unidade=None,
                area_label='Alocação',
                action_label='alocar docente',
                target_label='componente curricular',
            ))
            return context

        linhas_qs = AlocacaoTurmaDocente.objects.filter(
            alocacao_curricular__unidade_id=unidade_id,
            alocacao_curricular__semestre=_semestre_atual(),
        ).select_related('docente').order_by('pk')
        componentes_qs = MatrixComponent.objects.select_related(
            'componente_curricular'
        ).prefetch_related(
            Prefetch('alocacoes_turma_docente', queryset=linhas_qs, to_attr='linhas_carregadas')
        ).order_by('periodo', 'codigo')
        matrizes_vigentes = CurriculumMatrix.objects.filter(
            unidades__id=unidade_id,
            is_vigente=True,
        ).select_related('curso').prefetch_related(
            'unidades',
            Prefetch(
                'componentes_da_matriz',
                queryset=componentes_qs,
                to_attr='componentes_carregados',
            ),
        ).order_by('curso__nome', 'turno').distinct()

        ids_matrizes = matrizes_vigentes.order_by().values('pk')
        componentes_da_unidade = MatrixComponent.objects.filter(
            matriz_id__in=ids_matrizes,
        ).prefetch_related(
            Prefetch('alocacoes_turma_docente', queryset=linhas_qs, to_attr='linhas_carregadas')
        )
        total_componentes = 0
        componentes_sem_docente = 0
        for componente_unidade in componentes_da_unidade:
            total_componentes += 1
            if services.componente_pendente(componente_unidade, componente_unidade.linhas_carregadas):
                componentes_sem_docente += 1

        paginator = Paginator(matrizes_vigentes, 3)
        page_obj = paginator.get_page(self.request.GET.get('page'))

        cargos_diretivos = _cargos_diretivos_vigentes()
        docentes_da_tela = {
            linha.docente_id
            for matriz in page_obj.object_list
            for componente in matriz.componentes_carregados
            for linha in componente.linhas_carregadas
        }
        outras_unidades = _ids_de_outra_unidade(docentes_da_tela, unidade_id)
        matrizes_data = []
        for matriz in page_obj.object_list:
            for componente in matriz.componentes_carregados:
                componente.pendente_alocacao = services.componente_pendente(
                    componente, componente.linhas_carregadas
                )
                for linha in componente.linhas_carregadas:
                    linha.cargo_diretivo = cargos_diretivos.get(linha.docente_id, '')
                    linha.outra_unidade = linha.docente_id in outras_unidades
            matrizes_data.append({
                'matriz': matriz,
                'componentes': matriz.componentes_carregados,
            })

        context['matrizes_data'] = matrizes_data
        context['alocacao_curricular_preenchida'] = total_componentes > 0 and componentes_sem_docente == 0
        context['componentes_sem_docente'] = componentes_sem_docente
        context['page_obj'] = page_obj
        context['paginator'] = paginator
        context['is_paginated'] = page_obj.has_other_pages()
        context['querystring'] = f'unidade_id={unidade_id}'

        # Estado do botão "Aprovar Alocação": aprovado quando todas as matrizes da
        # unidade (que têm CourseUnit) já têm o consolidado APROVADO no semestre.
        alocacao_aprovada = False
        if unidade_id and matrizes_data:
            from apps.allocations.models import AlocacaoCurricular
            from apps.courses.models import CourseUnit
            semestre = _semestre_atual()
            matrizes_curso_turno = list(
                matrizes_vigentes.values_list('curso_id', 'turno')
            )
            course_units = dict(CourseUnit.objects.filter(
                curso_id__in=[curso_id for curso_id, _ in matrizes_curso_turno],
                unidade_id=unidade_id,
            ).values_list('curso_id', 'id'))
            esperadas = {
                (course_units[curso_id], turno or TURNO_PADRAO_ALOCACAO)
                for curso_id, turno in matrizes_curso_turno
                if curso_id in course_units
            }
            aprovadas = set(AlocacaoCurricular.objects.filter(
                unidade_id=unidade_id,
                semestre=semestre,
                status=AlocacaoCurricular.StatusChoices.APROVADO,
            ).values_list('curso_id', 'turno'))
            alocacao_aprovada = bool(esperadas) and esperadas <= aprovadas
        context['alocacao_aprovada'] = alocacao_aprovada

        context.update(build_window_lock_context(
            user,
            unidade=unidade_selecionada,
            area_label='Alocação',
            action_label='alocar docente',
            target_label='componente curricular',
        ))

        return context

def _contexto_componente(request, pk):
    """Carrega o componente e valida perfil/unidade/janela.

    Retorna (componente, unidade, resposta_de_erro). Quando `resposta_de_erro`
    não é None, a view deve devolvê-la sem processar a operação.
    """
    from apps.courses.models import MatrixComponent
    from django.http import HttpResponseForbidden

    comp = get_object_or_404(MatrixComponent.objects.select_related('matriz', 'matriz__curso'), pk=pk)
    user = request.user

    # Segurança: Coordenador só pode modificar componentes da sua unidade
    if user.perfil == 'COORDENADOR_UNIDADE':
        if not user.unidade_id or not comp.matriz.unidades.filter(id=user.unidade_id).exists():
            return comp, None, HttpResponseForbidden('Sem permissão para modificar componentes de outra unidade.')
        unidade = comp.matriz.unidades.filter(id=user.unidade_id).first()
    else:
        unidades = comp.matriz.unidades.order_by('pk')
        unidade_id = request.POST.get('unidade_id', '')
        unidade = unidades.filter(pk=unidade_id).first() if unidade_id.isdigit() else None
        unidade = unidade or unidades.first()

    blocked = enforce_window_or_redirect(
        request,
        area_label='Alocação',
        action_label='alocar docente',
        target_label=str(comp.nome_disciplina),
        unidade=unidade,
        fallback_url=request.META.get('HTTP_REFERER', '/alocacao-curricular/'),
    )
    if blocked:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # A mensagem de janela fechada já foi enfileirada; o cliente recarrega para exibi-la.
            return comp, unidade, JsonResponse({'ok': False, 'reload': True}, status=403)
        return comp, unidade, blocked
    return comp, unidade, None


def _eh_ajax(request):
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


def _resposta_erro(request, erro):
    if _eh_ajax(request):
        return JsonResponse({'ok': False, 'message': erro.message}, status=erro.status)
    messages.error(request, erro.message)
    return redirect(request.META.get('HTTP_REFERER', '/alocacao-curricular/'))


def _avisar_professor_de_outra_unidade(request, comp, unidade, docente):
    """Notifica a DESUP (e e-mail, via signal) quando um professor de outra unidade é alocado."""
    from django.urls import reverse
    from apps.core.models import Notificacao

    Notificacao.objects.create(
        destinatario=None,
        unidade_destino=None,
        titulo=f'Professor de outra unidade alocado - {unidade.sigla}',
        mensagem=(
            f'{docente.nome} foi alocado em {comp.nome_disciplina} na unidade {unidade.sigla}, '
            'mas não está vinculado a ela.\n\n'
            'Abra o cadastro do professor para ajustar as unidades em que ele atua.'
        ),
        url_acao=reverse('professors:professor_update', args=[docente.pk]),
    )


class AlocarDocenteComponenteView(LoginRequiredMixin, PerfilRequiredMixin, View):
    """Define o docente (ou carência / não oferecido) de uma linha do componente.

    POST: `docente_id` (id do professor | SEM_PROFESSOR | NAO_OFERECIDA),
    `linha_id` (opcional: pk da linha, ou `novo` para acrescentar uma linha) e
    `acao=remover` (com `linha_id`) para excluir uma linha adicional.
    """
    allowed_profiles = ['DESUP', 'COORDENADOR_UNIDADE']

    def post(self, request, pk):
        from django.http import HttpResponse

        comp, unidade, erro_resposta = _contexto_componente(request, pk)
        if erro_resposta:
            return erro_resposta

        linha_id = request.POST.get('linha_id') or None
        linha = None
        reload = False
        docente_id_param = request.POST.get('docente_id')
        user = request.user
        if user.perfil == 'COORDENADOR_UNIDADE' and not user.is_superuser:
            if docente_id_param not in (None, '', services.SEM_PROFESSOR, services.NAO_OFERECIDA):
                unidade_alvo_id = unidade.pk if unidade else user.unidade_id
                if not services.professor_autorizado_para_unidade(docente_id_param, unidade_alvo_id):
                    erro = services.AlocacaoError(
                        'Acesso negado: docente não vinculado a esta unidade e sem cessão autorizada.',
                        status=403,
                    )
                    return _resposta_erro(request, erro)
        try:
            if request.POST.get('acao') == 'remover':
                msg = services.remover_linha(comp, unidade, linha_id)
                reload = True
            else:
                msg, linha, reload = services.definir_escolha(
                    comp, unidade, docente_id_param, linha_id, usuario=user
                )
        except services.AlocacaoError as erro:
            return _resposta_erro(request, erro)

        comp.refresh_from_db(fields=['status'])
        outra_unidade = bool(
            linha and linha.docente_id
            and _ids_de_outra_unidade({linha.docente_id}, unidade.pk if unidade else None)
        )
        if outra_unidade and not reload:
            _avisar_professor_de_outra_unidade(request, comp, unidade, linha.docente)
        # Salvamento automático (fetch): responde JSON e a página não recarrega.
        # Sem `messages`, para o aviso não reaparecer numa navegação posterior.
        if _eh_ajax(request):
            return JsonResponse({
                'ok': True,
                'message': msg,
                'status': comp.status,
                'reload': reload,
                'linha_id': linha.pk if linha else None,
                'docente_id': linha.docente_id if linha else None,
                'docente_nome': linha.docente.rh_nome if linha and linha.docente_id else '',
                'outra_unidade': outra_unidade,
                'cargo_diretivo': (
                    _cargos_diretivos_vigentes().get(linha.docente_id, '')
                    if linha and linha.docente_id else ''
                ),
            })

        messages.success(request, msg)
        response = HttpResponse()
        response['HX-Refresh'] = 'true'
        return response


class QuantidadeTurmasComponenteView(LoginRequiredMixin, PerfilRequiredMixin, View):
    """Grava a quantidade de turmas ofertadas do componente (somente números)."""
    allowed_profiles = ['DESUP', 'COORDENADOR_UNIDADE']

    def post(self, request, pk):
        from django.http import HttpResponse

        comp, unidade, erro_resposta = _contexto_componente(request, pk)
        if erro_resposta:
            return erro_resposta
        try:
            msg, quantidade = services.definir_quantidade_turmas(
                comp, unidade, request.POST.get('quantidade_turmas')
            )
        except services.AlocacaoError as erro:
            return _resposta_erro(request, erro)

        comp.refresh_from_db(fields=['status'])
        if _eh_ajax(request):
            return JsonResponse({
                'ok': True,
                'message': msg,
                'status': comp.status,
                'quantidade_turmas': quantidade,
            })
        messages.success(request, msg)
        response = HttpResponse()
        response['HX-Refresh'] = 'true'
        return response


class LiberarAlocacaoView(LoginRequiredMixin, PerfilRequiredMixin, View):
    allowed_profiles = ['DESUP']
    
    def post(self, request, pk):
        alocacao = get_object_or_404(AlocacaoCurricular, pk=pk)
        
        # Regra solicitada: Se o botão de liberar foi clicado, retornamos a alocação para Rascunho
        # ou, se necessário, apenas marcamos a janela como reaberta.
        # Aqui, vamos definir o status da alocação de volta para Rascunho para que a Unidade edite
        alocacao.status = AlocacaoCurricular.StatusChoices.RASCUNHO
        alocacao.save()
        
        # Opcional: Reabrir janela de entrega automaticamente para essa unidade.
        from apps.core.models import JanelaEntrega
        from django.utils import timezone
        
        hoje = timezone.now().date()
        janela = JanelaEntrega.objects.filter(
            semestre=alocacao.semestre, 
            unidade=alocacao.unidade
        ).first()
        
        if janela:
            janela.status = JanelaEntrega.StatusChoices.REABERTO
            if janela.data_fim < hoje:
                import datetime
                janela.data_fim = hoje + datetime.timedelta(days=7) # + 7 dias
            janela.save()
            
        messages.success(request, f'Alocação do curso {alocacao.curso.sigla} liberada/reaberta para edição.')
        return redirect('alloc_curricular')

class AprovarAlocacaoUnidadeView(LoginRequiredMixin, PerfilRequiredMixin, View):
    allowed_profiles = ['DESUP']
    
    def post(self, request, unidade_id):
        from apps.allocations.models import AlocacaoCurricular
        from apps.courses.models import CurriculumMatrix, MatrixComponent
        from django.utils import timezone
        
        # Obtém semestre atual (mesma lógica usada nas pendências)
        semestre = _semestre_atual()

        from apps.courses.models import CourseUnit
        # 1. Aprova todas as alocações curriculares da unidade no semestre
        matrizes = CurriculumMatrix.objects.filter(
            unidades__id=unidade_id,
            is_vigente=True,
        ).select_related('curso').distinct()
        from django.db.models import Prefetch
        linhas_qs = AlocacaoTurmaDocente.objects.filter(
            alocacao_curricular__unidade_id=unidade_id,
            alocacao_curricular__semestre=semestre,
        )
        componentes_sem_docente = sum(
            1
            for componente in MatrixComponent.objects.filter(matriz__in=matrizes).prefetch_related(
                Prefetch('alocacoes_turma_docente', queryset=linhas_qs, to_attr='linhas_carregadas')
            )
            if services.componente_pendente(componente, componente.linhas_carregadas)
        )
        if componentes_sem_docente:
            messages.error(request, f'Ainda existem {componentes_sem_docente} componente(s) sem docente. Complete a alocacao antes de aprovar.')
            return redirect(f'/alocacao-curricular/?unidade_id={unidade_id}')

        aprovadas = 0
        matrizes_sem_turno = []
        for matriz in matrizes:
            course_unit = CourseUnit.objects.filter(curso=matriz.curso, unidade_id=unidade_id).first()
            if not course_unit:
                continue
            # Matriz sem turno não pode virar consolidado NOT NULL: cai no turno padrão
            # (ver TURNO_PADRAO_ALOCACAO) para a aprovação não morrer em 500.
            turno = matriz.turno or TURNO_PADRAO_ALOCACAO
            if not matriz.turno:
                matrizes_sem_turno.append(str(matriz))
            alocacao, _ = AlocacaoCurricular.objects.get_or_create(
                unidade_id=unidade_id,
                curso=course_unit,
                semestre=semestre,
                turno=turno,
            )
            alocacao.status = AlocacaoCurricular.StatusChoices.APROVADO
            alocacao.save(update_fields=['status', 'data_ultimo_ajuste'])
            aprovadas += 1
        messages.success(request, f'Alocacao curricular aprovada para {aprovadas} matriz(es) da unidade.')
        if matrizes_sem_turno:
            messages.warning(
                request,
                'Matriz(es) sem turno definido consolidada(s) como Manhã: '
                f'{", ".join(matrizes_sem_turno)}. Ajuste o turno da matriz para o '
                'consolidado ficar correto.',
            )
        return redirect(f'/alocacao-curricular/?unidade_id={unidade_id}')


class DesfazerAprovacaoUnidadeView(LoginRequiredMixin, PerfilRequiredMixin, View):
    """Desfaz a aprovação da DESUP: devolve os consolidados do semestre a Rascunho."""
    allowed_profiles = ['DESUP']

    def post(self, request, unidade_id):
        revertidas = AlocacaoCurricular.objects.filter(
            unidade_id=unidade_id,
            semestre=_semestre_atual(),
            status=AlocacaoCurricular.StatusChoices.APROVADO,
        ).update(status=AlocacaoCurricular.StatusChoices.RASCUNHO)
        messages.success(request, f'Aprovação desfeita para {revertidas} matriz(es). A alocação pode ser alterada novamente.')
        return redirect(f'/alocacao-curricular/?unidade_id={unidade_id}')


class BuscarProfessoresView(LoginRequiredMixin, PerfilRequiredMixin, View):
    """Endpoint JSON para busca dinâmica de professores (autocomplete).

    A busca é restrita aos professores autorizados da unidade (próprios e cedidos).
    A DESUP possui visão global ou pode filtrar por unidade.
    """
    allowed_profiles = ['DESUP', 'COORDENADOR_UNIDADE']

    def get(self, request):
        from django.db.models import Q, Value
        from django.db.models.functions import Coalesce, NullIf

        from apps.professors.models import Professor
        from apps.allocations.services import professores_autorizados_unidade_qs

        user = request.user
        q = request.GET.get('q', '').strip()

        if user.perfil == 'COORDENADOR_UNIDADE' and not user.is_superuser:
            if not user.unidade_id:
                return JsonResponse({'results': []})
            unidade_alocacao = user.unidade_id
            qs = professores_autorizados_unidade_qs(unidade_alocacao).filter(status='Ativo')
        else:
            unidade_param = request.GET.get('unidade_alocacao', '')
            unidade_alocacao = int(unidade_param) if unidade_param.isdigit() else None
            if unidade_alocacao:
                qs = professores_autorizados_unidade_qs(unidade_alocacao).filter(status='Ativo')
            else:
                qs = Professor.objects.filter(status='Ativo')

        # Regra #3: o ajuste da DESUP (`desup_nome`) prevalece sobre o dado do RH — é o
        # que `Professor.nome` devolve e o que a tela mostra. Antes o endpoint filtrava e
        # devolvia `rh_nome` cru, então o autocomplete não achava (nem exibia) o nome
        # ajustado. `nome_exibicao` reproduz a property no banco para dar pra ordenar.
        qs = qs.annotate(
            nome_exibicao=Coalesce(NullIf('desup_nome', Value('')), 'rh_nome')
        )

        if q:
            # Busca pelos dois nomes: quem só conhece o nome antigo do RH continua achando.
            from apps.core.busca import filtrar_contem
            qs = filtrar_contem(qs, q, ['desup_nome', 'rh_nome'])

        qs = qs.prefetch_related('unidades', 'readaptacoes').order_by('nome_exibicao')[:20]

        cargos_diretivos = _cargos_diretivos_vigentes()
        outras = _ids_de_outra_unidade({p.id for p in qs}, unidade_alocacao)
        results = [
            {
                'id': p.id,
                'nome': p.nome,
                'unidade': ', '.join(u.sigla for u in p.unidades_exibicao),
                'cargo_diretivo': cargos_diretivos.get(p.id, ''),
                'outra_unidade': p.id in outras,
                'readaptado': p.readaptado_vigente,
            }
            for p in qs
        ]
        return JsonResponse({'results': results})
