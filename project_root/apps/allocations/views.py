from django.views.generic import ListView, TemplateView
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from apps.accounts.mixins import PerfilRequiredMixin
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from apps.allocations.models import AlocacaoCurricular
from apps.core.services import build_window_lock_context, enforce_window_or_redirect

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
            
        # Matrizes Vigentes da unidade (ou de todas se unidade_id for vazio)
        if unidade_id:
            matrizes_vigentes = CurriculumMatrix.objects.filter(
                unidades__id=unidade_id,
                is_vigente=True
            ).select_related('curso').prefetch_related('unidades').order_by('curso__nome', 'turno').distinct()
        else:
            matrizes_vigentes = CurriculumMatrix.objects.filter(
                is_vigente=True
            ).select_related('curso').prefetch_related('unidades').order_by('curso__nome', 'turno')

        matrizes_data = []
        total_componentes = 0
        componentes_sem_docente = 0
        for matriz in matrizes_vigentes:
            componentes = matriz.componentes_da_matriz.select_related('componente_curricular', 'docente').order_by('periodo', 'codigo')
            total_componentes += componentes.count()
            componentes_sem_docente += componentes.filter(docente__isnull=True).exclude(status=MatrixComponent.StatusChoices.NAO_OFERECIDA).count()
            matrizes_data.append({
                'matriz': matriz,
                'componentes': componentes
            })
            
        context['matrizes_data'] = matrizes_data
        context['alocacao_curricular_preenchida'] = total_componentes > 0 and componentes_sem_docente == 0
        context['componentes_sem_docente'] = componentes_sem_docente

        # Professores da unidade (ou de todas) para popular os selects
        if unidade_id:
            professores_qs = Professor.objects.filter(
                unidade_principal_id=unidade_id
            ).order_by('rh_nome')
        else:
            professores_qs = Professor.objects.all().order_by('rh_nome')

        context['professores_unidade'] = professores_qs
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
            target_label=str(comp.componente_curricular.nome),
            unidade=unidade_comp,
            fallback_url=request.META.get('HTTP_REFERER', '/alocacao-curricular/'),
        )
        if blocked:
            return blocked
        
        docente_id = request.POST.get('docente_id')
        
        if docente_id == MatrixComponent.StatusChoices.NAO_OFERECIDA:
            comp.docente = None
            comp.status = MatrixComponent.StatusChoices.NAO_OFERECIDA
            comp.save()
            messages.success(request, f'Componente {comp.componente_curricular.nome} marcado como Não oferecido.')
        elif docente_id == MatrixComponent.StatusChoices.SEM_PROFESSOR or not docente_id:
            comp.docente = None
            comp.status = MatrixComponent.StatusChoices.SEM_PROFESSOR
            comp.save()
            messages.success(request, f'Componente {comp.componente_curricular.nome} marcado como Sem professor.')
        else:
            # Segurança: Coordenador só pode alocar professores da sua unidade
            if user.perfil == 'COORDENADOR_UNIDADE':
                prof = Professor.objects.filter(pk=docente_id, unidade_principal=user.unidade).first()
                if not prof:
                    return HttpResponseForbidden('Sem permissão para alocar professores de outra unidade.')
            
            comp.docente_id = docente_id
            comp.status = MatrixComponent.StatusChoices.COMPLETO
            comp.save()
            messages.success(request, f'Docente alocado para {comp.componente_curricular.nome} com sucesso!')
            
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
        hoje = timezone.now()
        s = "1" if hoje.month <= 6 else "2"
        semestre = f"{hoje.year}.{s}"
        
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
        for matriz in matrizes:
            course_unit = CourseUnit.objects.filter(curso=matriz.curso, unidade_id=unidade_id).first()
            if not course_unit:
                continue
            alocacao, _ = AlocacaoCurricular.objects.get_or_create(
                unidade_id=unidade_id,
                curso=course_unit,
                semestre=semestre,
                turno=matriz.turno,
            )
            alocacao.status = AlocacaoCurricular.StatusChoices.APROVADO
            alocacao.save(update_fields=['status', 'data_ultimo_ajuste'])
            aprovadas += 1
        messages.success(request, f'Alocacao curricular aprovada para {aprovadas} matriz(es) da unidade.')
        return redirect(f'/alocacao-curricular/?unidade_id={unidade_id}')


class BuscarProfessoresView(LoginRequiredMixin, PerfilRequiredMixin, View):
    """Endpoint JSON para busca dinâmica de professores (autocomplete).

    Regras de isolamento (server-side):
    - COORDENADOR_UNIDADE: retorna APENAS professores da unidade do usuário.
      O parâmetro `unidade_id` da URL é IGNORADO para este perfil.
    - DESUP: pode buscar em todas as unidades. Se `unidade_id` for informado,
      filtra por aquela unidade; caso contrário, retorna de todas.
    """
    allowed_profiles = ['DESUP', 'COORDENADOR_UNIDADE']

    def get(self, request):
        from apps.professors.models import Professor

        q = request.GET.get('q', '').strip()
        unidade_id = request.GET.get('unidade_id')
        user = request.user

        # Segurança: Coordenador SEMPRE restrito à sua unidade
        if user.perfil == 'COORDENADOR_UNIDADE':
            if not user.unidade:
                return JsonResponse({'results': []})
            qs = Professor.objects.filter(
                unidade_principal=user.unidade, status='Ativo'
            )
        else:  # DESUP — busca global, opcionalmente filtrada por unidade
            qs = Professor.objects.filter(status='Ativo')
            if unidade_id:
                qs = qs.filter(unidade_principal_id=unidade_id)

        if q:
            qs = qs.filter(rh_nome__icontains=q)

        qs = qs.select_related('unidade_principal').order_by('rh_nome')[:20]

        results = [
            {
                'id': p.id,
                'nome': p.rh_nome,
                'unidade': p.unidade_principal.sigla if p.unidade_principal else '',
            }
            for p in qs
        ]
        return JsonResponse({'results': results})
