from django.views.generic import ListView, TemplateView
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from apps.accounts.mixins import PerfilRequiredMixin
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from apps.allocations.models import AlocacaoCurricular
from apps.core.services import build_window_lock_context, enforce_window_or_redirect

# `AlocacaoCurricular.turno` é NOT NULL. O formulário agora exige o turno para novas
# matrizes, mas matrizes legadas/importadas ainda podem ter `CurriculumMatrix.turno=NULL`
# durante o saneamento. Nesses casos o consolidado mantém o fallback para Manhã e avisa
# a DESUP, evitando IntegrityError/500 sem mascarar que o cadastro precisa ser corrigido.
TURNO_PADRAO_ALOCACAO = 'M'


def _semestre_atual():
    from django.utils import timezone
    hoje = timezone.now()
    return f"{hoje.year}.{'1' if hoje.month <= 6 else '2'}"

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

        componentes_qs = MatrixComponent.objects.select_related(
            'componente_curricular', 'docente'
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
        )
        total_componentes = componentes_da_unidade.count()
        componentes_sem_docente = componentes_da_unidade.filter(
            docente__isnull=True,
        ).exclude(status=MatrixComponent.StatusChoices.NAO_OFERECIDA).count()

        paginator = Paginator(matrizes_vigentes, 3)
        page_obj = paginator.get_page(self.request.GET.get('page'))

        matrizes_data = []
        for matriz in page_obj.object_list:
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

class AlocarDocenteComponenteView(LoginRequiredMixin, PerfilRequiredMixin, View):
    allowed_profiles = ['DESUP', 'COORDENADOR_UNIDADE']
    
    def post(self, request, pk):
        from apps.courses.models import MatrixComponent
        from apps.professors.models import Professor
        from django.http import HttpResponse, HttpResponseForbidden
        
        comp = get_object_or_404(MatrixComponent, pk=pk)
        user = request.user
        
        # Segurança: Coordenador só pode modificar componentes da sua unidade
        if user.perfil == 'COORDENADOR_UNIDADE':
            if not user.unidade or not comp.matriz.unidades.filter(id=user.unidade.id).exists():
                return HttpResponseForbidden('Sem permissão para modificar componentes de outra unidade.')

        unidade_comp = comp.matriz.unidades.filter(id=user.unidade_id).first() if user.unidade_id else comp.matriz.unidades.first()
        blocked = enforce_window_or_redirect(
            request,
            area_label='Alocação',
            action_label='alocar docente',
            target_label=str(comp.nome_disciplina),
            unidade=unidade_comp,
            fallback_url=request.META.get('HTTP_REFERER', '/alocacao-curricular/'),
        )
        if blocked:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                # A mensagem de janela fechada já foi enfileirada; o cliente recarrega para exibi-la.
                return JsonResponse({'ok': False, 'reload': True}, status=403)
            return blocked
        
        docente_id = request.POST.get('docente_id')
        
        if docente_id == MatrixComponent.StatusChoices.NAO_OFERECIDA:
            comp.docente = None
            comp.status = MatrixComponent.StatusChoices.NAO_OFERECIDA
            comp.save()
            msg = f'Componente {comp.nome_disciplina} marcado como Não oferecido.'
        elif docente_id == MatrixComponent.StatusChoices.SEM_PROFESSOR or not docente_id:
            comp.docente = None
            comp.status = MatrixComponent.StatusChoices.SEM_PROFESSOR
            comp.save()
            msg = f'Componente {comp.nome_disciplina} marcado como Sem professor.'
        else:
            # Qualquer unidade pode utilizar um professor da base institucional.
            comp.docente = get_object_or_404(Professor, pk=docente_id)
            comp.status = MatrixComponent.StatusChoices.COMPLETO
            comp.save()
            msg = f'Docente alocado para {comp.nome_disciplina} com sucesso!'

        # Salvamento automático (fetch): responde JSON e a página não recarrega.
        # Sem `messages`, para o aviso não reaparecer numa navegação posterior.
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'ok': True,
                'message': msg,
                'status': comp.status,
                'docente_id': comp.docente_id,
                'docente_nome': comp.docente.rh_nome if comp.docente_id else '',
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
        componentes_sem_docente = sum(
            matriz.componentes_da_matriz.filter(docente__isnull=True).exclude(status=MatrixComponent.StatusChoices.NAO_OFERECIDA).count()
            for matriz in matrizes
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

    A busca é global: todas as unidades consultam a mesma base de docentes.
    """
    allowed_profiles = ['DESUP', 'COORDENADOR_UNIDADE']

    def get(self, request):
        from django.db.models import Q, Value
        from django.db.models.functions import Coalesce, NullIf

        from apps.professors.models import Professor

        q = request.GET.get('q', '').strip()
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

        qs = qs.prefetch_related('unidades').order_by('nome_exibicao')[:20]

        results = [
            {
                'id': p.id,
                'nome': p.nome,
                'unidade': ', '.join(u.sigla for u in p.unidades_exibicao),
            }
            for p in qs
        ]
        return JsonResponse({'results': results})
