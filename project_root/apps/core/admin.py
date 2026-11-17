import csv
from datetime import timedelta

from django.contrib import admin
from django.http import HttpResponse
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join
from django.utils.text import Truncator
from django.utils.safestring import mark_safe
from unfold.contrib.filters.admin import (
    ChoicesDropdownFilter, DropdownFilter, RangeDateTimeFilter, TextFilter,
)

from apps.accounts.admin import HarpiaModelAdmin, admin_site
from .audit import registrar, titulo_da_acao
from .models import (
    AtividadeEstagioSupervisao,
    AuditoriaGlobal,
    ErroSistema,
    ExcecaoCargaUnidade,
    JanelaEntrega,
    LimiteCargaUnidade,
    Notificacao,
    OcupacaoEquipeDiretiva,
    ReadaptacaoProfessor,
    SolicitacaoProfessorExterno,
    TipoCargoDiretivo,
    Unidade,
)
from .forms import JanelaEntregaForm

class UnidadeSemUsuarioFilter(DropdownFilter):
    title = 'Acesso à unidade'
    parameter_name = 'acesso'

    def lookups(self, request, model_admin):
        return [['sem_usuario', 'Ativas e sem nenhum usuário']]

    def queryset(self, request, queryset):
        if self.value() == 'sem_usuario':
            return queryset.filter(status=True, usuarios__isnull=True)
        return queryset


class JanelaPrazoFilter(DropdownFilter):
    title = 'Prazo'
    parameter_name = 'prazo'

    def lookups(self, request, model_admin):
        return [['abertas', 'Abertas ou reabertas']]

    def queryset(self, request, queryset):
        if self.value() == 'abertas':
            return queryset.filter(status__in=['Aberto', 'Reaberto'])
        return queryset


class UnidadeAdmin(HarpiaModelAdmin):
    list_display = ('nome', 'sigla', 'status')
    search_fields = ('nome', 'sigla')
    list_filter = (UnidadeSemUsuarioFilter, 'status')

class JanelaEntregaAdmin(HarpiaModelAdmin):
    form = JanelaEntregaForm
    list_display = ('semestre', 'data_inicio', 'data_fim', 'status', 'unidade')
    list_filter = (JanelaPrazoFilter, 'status', 'semestre', 'unidade')
    search_fields = ('semestre',)

class NotificacaoAdmin(HarpiaModelAdmin):
    list_display = ('titulo', 'destinatario', 'unidade_destino', 'lida', 'data_criacao')
    list_filter = ('lida', 'unidade_destino', 'data_criacao')
    search_fields = ('titulo', 'mensagem')
    ordering = ('-data_criacao',)

class _ContemFilter(TextFilter):
    """Caixa de texto "contém": cada palavra digitada precisa aparecer em algum dos campos.

    Ex.: "maria faeterj" acha todo registro que tenha "maria" E "faeterj" (em qualquer
    ordem, em qualquer maiúscula/minúscula), mesmo no meio de uma frase.
    """

    campos = ()

    def queryset(self, request, queryset):
        valor = (self.value() or '').strip()
        if not valor:
            return queryset
        for termo in valor.split():
            condicao = Q()
            for campo in self.campos:
                condicao |= Q(**{f'{campo}__icontains': termo})
            queryset = queryset.filter(condicao)
        return queryset


class DetalhesContemFilter(_ContemFilter):
    title = 'Detalhes contém'
    parameter_name = 'detalhes_contem'
    campos = ('detalhes',)


class QuemFezContemFilter(_ContemFilter):
    title = 'Quem fez contém (e-mail ou perfil)'
    parameter_name = 'quem_contem'
    campos = ('email', 'perfil_usuario')


class RegistroContemFilter(_ContemFilter):
    title = 'Nome do registro contém (ex.: nome do professor)'
    parameter_name = 'registro_contem'
    campos = ('objeto', 'entidade', 'objeto_id')


class UnidadeContemFilter(_ContemFilter):
    title = 'Unidade contém'
    parameter_name = 'unidade_contem'
    campos = ('unidade_objeto', 'unidade_usuario')


class AcaoContemFilter(_ContemFilter):
    title = 'Código da ação contém'
    parameter_name = 'acao_contem'
    campos = ('acao',)


class OperacaoContemFilter(_ContemFilter):
    title = 'Código da operação (todos os registros de uma mesma ação)'
    parameter_name = 'operacao'
    campos = ('operacao',)


def _csv_seguro(valor):
    """Evita que uma célula comece com =, +, - ou @ (o Excel a trataria como fórmula)."""
    texto = '' if valor is None else str(valor)
    return "'" + texto if texto[:1] in ('=', '+', '-', '@', '\t', '\r') else texto


_CLASSE_CATEGORIA = {
    'CRIACAO': 'criacao', 'ALTERACAO': 'alteracao', 'EXCLUSAO': 'exclusao',
    'ACESSO': 'acesso', 'SEGURANCA': 'seguranca', 'OUTRO': 'outro',
}


def _selo(obj):
    return format_html(
        '<span class="sa-badge sa-badge--{}">{}</span>',
        _CLASSE_CATEGORIA.get(obj.categoria, 'outro'), obj.get_categoria_display(),
    )


def _linhas_texto(texto):
    return [linha.strip() for linha in (texto or '').splitlines() if linha.strip()]


def _campos_do_texto(texto):
    """Reconstrói antes/depois de registros antigos lendo "Campo: antes → depois"."""
    campos = []
    for linha in _linhas_texto(texto):
        if 'Alterações: ' not in linha:
            continue
        resto = linha.split('Alterações: ', 1)[1].rstrip()
        if resto.endswith('.'):
            resto = resto[:-1]
        for parte in resto.split('; '):
            if ' → ' not in parte:
                continue
            esquerda, depois = parte.split(' → ', 1)
            campo, _, antes = esquerda.partition(': ')
            campos.append({
                'campo': campo.strip(), 'antes': antes.strip() or '—', 'depois': depois.strip() or '—',
            })
    return campos


def _campos_da_linha(obj):
    return list(obj.mudancas or []) or _campos_do_texto(obj.detalhes)


def _pares(itens):
    """Lista "rótulo → valor" em grade (`dl`)."""
    return format_html(
        '<dl class="sa-kv">{}</dl>',
        format_html_join(
            '', '<div class="sa-kv__item"><dt>{}</dt><dd>{}</dd></div>',
            ((rotulo, valor or '—') for rotulo, valor in itens),
        ),
    )


class AuditoriaGlobalAdmin(HarpiaModelAdmin):
    """Log do sistema: só leitura, com busca "contém" e detalhe completo de cada registro.

    A lista mostra poucas colunas (cabem na tela sem cortar); ao clicar numa linha, a
    página de detalhe mostra o que mudou campo a campo (antes → depois), quem fez, de
    onde e tudo o que a mesma ação alterou.
    """

    list_display = ('quando', 'o_que_aconteceu', 'quem', 'registro_afetado', 'resumo')
    list_display_links = ('quando', 'o_que_aconteceu')
    list_select_related = ('usuario',)
    list_per_page = 50
    list_filter_submit = True
    list_filter = (
        DetalhesContemFilter,
        RegistroContemFilter,
        QuemFezContemFilter,
        UnidadeContemFilter,
        AcaoContemFilter,
        OperacaoContemFilter,
        ('categoria', ChoicesDropdownFilter),
        ('criado_em', RangeDateTimeFilter),
    )
    search_fields = (
        'detalhes', 'acao', 'email', 'perfil_usuario', 'unidade_usuario',
        'entidade', 'objeto', 'objeto_id', 'unidade_objeto', 'ip',
    )
    search_help_text = (
        'Busca por qualquer parte do texto (contém), em detalhes, ação, e-mail, '
        'nome do registro, unidade e IP. Várias palavras = todas precisam aparecer.'
    )
    ordering = ('-criado_em',)
    readonly_fields = (
        'painel_resumo', 'painel_alteracoes', 'painel_autor', 'painel_operacao',
        'criado_em', 'usuario', 'email', 'perfil_usuario', 'unidade_usuario',
        'categoria', 'acao', 'entidade', 'objeto', 'objeto_id', 'unidade_objeto',
        'detalhes', 'caminho', 'operacao', 'ip', 'user_agent',
    )
    fieldsets = (
        ('O que aconteceu', {'fields': ('painel_resumo',)}),
        ('O que mudou (antes → depois)', {'fields': ('painel_alteracoes',)}),
        ('Quem fez e de onde', {'fields': ('painel_autor',)}),
        ('Outros registros da mesma operação', {'fields': ('painel_operacao',)}),
        ('Dados técnicos', {
            'fields': (
                'criado_em', 'acao', 'categoria', 'entidade', 'objeto', 'objeto_id',
                'unidade_objeto', 'usuario', 'email', 'perfil_usuario', 'unidade_usuario',
                'ip', 'caminho', 'operacao', 'user_agent', 'detalhes',
            ),
            'classes': ('collapse',),
        }),
    )

    # ---- exportação -------------------------------------------------------

    actions = ['exportar_csv']

    @admin.action(description='Exportar selecionados em CSV (abre no Excel)', permissions=['view'])
    def exportar_csv(self, request, queryset):
        """Planilha com uma linha por registro, incluindo o antes → depois de cada campo."""
        agora = timezone.localtime()
        resposta = HttpResponse(content_type='text/csv; charset=utf-8')
        resposta['Content-Disposition'] = f'attachment; filename="auditoria-{agora:%Y%m%d-%H%M}.csv"'
        resposta.write('\ufeff')  # BOM: o Excel reconhece os acentos
        escritor = csv.writer(resposta, delimiter=';')
        escritor.writerow([
            'Data e hora', 'O que aconteceu', 'Código da ação', 'Tipo', 'Quem fez', 'Perfil',
            'Unidade de quem fez', 'Registro afetado', 'Tipo de registro', 'Unidade do registro',
            'O que mudou (campo: antes → depois)', 'Tela', 'IP', 'Operação',
        ])
        total = 0
        for linha in queryset.order_by('-criado_em', '-pk').iterator(chunk_size=500):
            alteracoes = ' | '.join(
                f"{campo.get('campo', '')}: {campo.get('antes', '—')} → {campo.get('depois', '—')}"
                for campo in _campos_da_linha(linha)
            )
            escritor.writerow([
                _csv_seguro(valor) for valor in (
                    timezone.localtime(linha.criado_em).strftime('%d/%m/%Y %H:%M:%S'),
                    titulo_da_acao(linha.acao), linha.acao, linha.get_categoria_display(),
                    linha.email, linha.perfil_usuario, linha.unidade_usuario,
                    linha.objeto, linha.entidade, linha.unidade_objeto,
                    alteracoes or linha.detalhes, linha.caminho, linha.ip or '', linha.operacao,
                )
            ])
            total += 1
        # Quem exportou o log também fica registrado (depois de montar o arquivo, para não entrar nele).
        registrar(
            request, 'AUDITORIA_EXPORTADA', f'{total} registro(s) da auditoria exportados em CSV.',
            categoria=AuditoriaGlobal.Categoria.OUTRO, entidade='Auditoria', absorver=False,
        )
        return resposta

    # ---- colunas da lista -------------------------------------------------

    @admin.display(description='Data e hora', ordering='criado_em')
    def quando(self, obj):
        return format_html(
            '<span class="sa-nowrap">{}</span>',
            timezone.localtime(obj.criado_em).strftime('%d/%m/%Y %H:%M:%S'),
        )

    @admin.display(description='O que aconteceu', ordering='categoria')
    def o_que_aconteceu(self, obj):
        return format_html(
            '{}<div class="sa-cell-main">{}</div>', _selo(obj), titulo_da_acao(obj.acao),
        )

    @admin.display(description='Quem fez', ordering='email')
    def quem(self, obj):
        email = obj.email or (obj.usuario.email if obj.usuario_id else '—')
        complemento = ' · '.join(p for p in (obj.perfil_usuario, obj.unidade_usuario) if p)
        return format_html(
            '<div class="sa-cell-main">{}</div><div class="sa-cell-sub">{}</div>',
            email, complemento,
        )

    @admin.display(description='Registro afetado')
    def registro_afetado(self, obj):
        if not (obj.entidade or obj.objeto):
            return mark_safe('<span class="sa-muted">—</span>')
        return format_html(
            '<div class="sa-cell-sub">{}</div><div class="sa-cell-main">{}</div>'
            '<div class="sa-cell-sub">{}</div>',
            obj.entidade, obj.objeto or '—', obj.unidade_objeto,
        )

    @admin.display(description='Resumo')
    def resumo(self, obj):
        linhas = _linhas_texto(obj.detalhes)
        texto = linhas[0] if linhas else ''
        if len(texto) > 160:
            texto = texto[:159].rstrip() + '…'
        quantidade = len(obj.mudancas or [])
        dica = (
            f'{quantidade} campo(s) — clique para ver antes e depois'
            if quantidade else ('clique para ver os detalhes' if len(linhas) > 1 else '')
        )
        return format_html(
            '<div class="sa-resumo">{}</div><div class="sa-cell-sub">{}</div>', texto, dica,
        )

    # ---- painéis da página de detalhe -------------------------------------

    @admin.display(description='Resumo')
    def painel_resumo(self, obj):
        linhas = _linhas_texto(obj.detalhes)
        if linhas:
            texto = format_html_join('', '<p class="sa-audit__linha">{}</p>', ((l,) for l in linhas))
        else:
            texto = mark_safe('<p class="sa-muted">Este registro não tem texto descritivo.</p>')
        return format_html(
            '<div class="sa-audit">{}<h3 class="sa-audit__titulo">{}</h3>{}{}</div>',
            _selo(obj), titulo_da_acao(obj.acao),
            _pares([
                ('Quando', timezone.localtime(obj.criado_em).strftime('%d/%m/%Y às %H:%M:%S')),
                ('O que foi mexido', obj.entidade),
                ('Nome do registro', obj.objeto),
                ('Unidade do registro', obj.unidade_objeto),
            ]),
            texto,
        )

    @admin.display(description='Campos')
    def painel_alteracoes(self, obj):
        campos = _campos_da_linha(obj)
        if not campos:
            if obj.categoria in ('ACESSO', 'SEGURANCA'):
                return mark_safe(
                    '<p class="sa-muted">Este tipo de registro não altera dados de cadastro. '
                    'Veja o resumo acima.</p>'
                )
            return mark_safe(
                '<p class="sa-muted">Sem lista de campos para este registro (feito antes do '
                'detalhamento ser ativado, ou ação que não altera campos). Veja o texto do resumo '
                'e os outros registros da mesma operação, abaixo.</p>'
            )
        if obj.categoria == 'CRIACAO':
            cabecalho, linhas = ('Campo', 'Valor informado'), [(c['campo'], c['depois']) for c in campos]
        elif obj.categoria == 'EXCLUSAO':
            cabecalho, linhas = (
                ('Campo', 'Valor no momento da exclusão'), [(c['campo'], c['antes']) for c in campos],
            )
        else:
            return format_html(
                '<div class="sa-table-wrap"><table class="sa-diff">'
                '<thead><tr><th>Campo</th><th>Antes</th><th>Depois</th></tr></thead><tbody>{}</tbody>'
                '</table></div>',
                format_html_join(
                    '',
                    '<tr><td class="sa-diff__campo">{}</td><td class="sa-diff__antes">{}</td>'
                    '<td class="sa-diff__depois">{}</td></tr>',
                    ((c['campo'], c['antes'], c['depois']) for c in campos),
                ),
            )
        return format_html(
            '<div class="sa-table-wrap"><table class="sa-diff"><thead><tr><th>{}</th><th>{}</th>'
            '</tr></thead><tbody>{}</tbody></table></div>',
            cabecalho[0], cabecalho[1],
            format_html_join(
                '', '<tr><td class="sa-diff__campo">{}</td><td class="sa-diff__depois">{}</td></tr>',
                linhas,
            ),
        )

    @admin.display(description='Autor')
    def painel_autor(self, obj):
        email = obj.email or (obj.usuario.email if obj.usuario_id else '')
        return _pares([
            ('E-mail', email),
            ('Perfil', obj.perfil_usuario),
            ('Unidade de quem fez', obj.unidade_usuario),
            ('Endereço de IP', obj.ip),
            ('Tela / endereço', obj.caminho),
            ('Navegador', (obj.user_agent or '')[:160]),
        ])

    @admin.display(description='Operação')
    def painel_operacao(self, obj):
        if not obj.operacao:
            return mark_safe(
                '<p class="sa-muted">Registro anterior ao agrupamento por operação.</p>'
            )
        irmaos = list(
            type(obj).objects.filter(operacao=obj.operacao)
            .exclude(pk=obj.pk).order_by('criado_em', 'pk')[:50]
        )
        if not irmaos:
            return mark_safe(
                '<p class="sa-muted">A mesma ação do usuário não gerou outros registros.</p>'
            )
        nome_site = self.admin_site.name
        linhas = format_html_join(
            '',
            '<tr><td class="sa-nowrap">{}</td><td>{}</td><td>{}</td><td><a href="{}">Abrir</a></td></tr>',
            (
                (
                    timezone.localtime(o.criado_em).strftime('%H:%M:%S'),
                    titulo_da_acao(o.acao),
                    f'{o.entidade}: {o.objeto}' if o.objeto else o.entidade,
                    reverse(f'{nome_site}:core_auditoriaglobal_change', args=[o.pk]),
                )
                for o in irmaos
            ),
        )
        lista = reverse(f'{nome_site}:core_auditoriaglobal_changelist')
        return format_html(
            '<p class="sa-muted">A mesma ação do usuário gerou também estes registros '
            '(<a href="{}?operacao={}">ver todos na lista</a>):</p>'
            '<div class="sa-table-wrap"><table class="sa-diff"><thead><tr><th>Hora</th>'
            '<th>O que aconteceu</th><th>Registro</th><th></th></tr></thead><tbody>{}</tbody>'
            '</table></div>',
            lista, obj.operacao, linhas,
        )

    # O log é prova de auditoria: ninguém cria, edita ou apaga linhas pelo painel.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class ErroPeriodoFilter(DropdownFilter):
    title = 'Período'
    parameter_name = 'periodo'
    _janelas = {'24h': timedelta(hours=24), '7d': timedelta(days=7), '30d': timedelta(days=30)}

    def lookups(self, request, model_admin):
        return [['24h', 'Últimas 24 horas'], ['7d', 'Últimos 7 dias'], ['30d', 'Últimos 30 dias']]

    def queryset(self, request, queryset):
        janela = self._janelas.get(self.value())
        if janela:
            return queryset.filter(criado_em__gte=timezone.now() - janela)
        return queryset


class ErroSistemaAdmin(HarpiaModelAdmin):
    list_display = ('quando', 'gravidade', 'erro', 'onde', 'quem')
    list_display_links = ('quando', 'erro')
    list_filter = (ErroPeriodoFilter, 'status_http', 'tipo_erro', 'perfil_usuario')
    search_fields = (
        'request_id', 'email_usuario', 'caminho', 'tipo_erro',
        'mensagem', 'fingerprint',
    )
    search_help_text = 'Busca por tipo de erro, mensagem, tela, e-mail do usuário ou ID da requisição.'
    readonly_fields = (
        'criado_em', 'status_http', 'tipo_erro', 'mensagem', 'traceback',
        'metodo', 'caminho', 'usuario', 'email_usuario', 'perfil_usuario',
        'unidade_usuario', 'ip', 'user_agent', 'request_id', 'fingerprint',
    )
    ordering = ('-criado_em',)
    list_per_page = 50

    @admin.display(description='Data e hora', ordering='criado_em')
    def quando(self, obj):
        return format_html(
            '<span class="sa-nowrap">{}</span>',
            timezone.localtime(obj.criado_em).strftime('%d/%m/%Y %H:%M:%S'),
        )

    @admin.display(description='Gravidade', ordering='status_http')
    def gravidade(self, obj):
        if obj.status_http >= 500:
            classe, rotulo = 'exclusao', 'Erro do sistema'
        elif obj.status_http == 404:
            classe, rotulo = 'outro', 'Página não encontrada'
        else:
            classe, rotulo = 'alteracao', 'Pedido recusado'
        return format_html(
            '<span class="sa-badge sa-badge--{}">{} · {}</span>', classe, obj.status_http, rotulo,
        )

    @admin.display(description='O que deu errado', ordering='tipo_erro')
    def erro(self, obj):
        mensagem = Truncator(obj.mensagem or '').chars(140)
        return format_html(
            '<span class="sa-cell-main">{}</span><span class="sa-cell-sub">{}</span>',
            obj.tipo_erro, mensagem or 'Sem mensagem registrada.',
        )

    @admin.display(description='Onde aconteceu', ordering='caminho')
    def onde(self, obj):
        return format_html(
            '<span class="sa-cell-main">{}</span><span class="sa-cell-sub">{}</span>',
            obj.caminho, obj.metodo,
        )

    @admin.display(description='Quem estava usando', ordering='email_usuario')
    def quem(self, obj):
        return obj.email_usuario or '—'

    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class TipoCargoDiretivoAdmin(HarpiaModelAdmin):
    list_display = ('nome', 'codigo', 'exige_curso', 'permite_multiplos', 'ativo', 'ordem')
    list_filter = ('ativo', 'exige_curso', 'permite_multiplos')
    search_fields = ('nome', 'codigo')
    readonly_fields = ('codigo', 'permite_multiplos', 'criado_em', 'atualizado_em')


class OcupacaoEquipeDiretivaAdmin(HarpiaModelAdmin):
    list_display = ('unidade', 'cargo', 'professor', 'curso', 'data_inicio', 'data_fim', 'carga_reducao_horas')
    list_filter = ('unidade', 'cargo', 'data_inicio', 'data_fim')
    search_fields = ('professor__rh_nome', 'unidade__nome', 'cargo__nome')
    readonly_fields = ('criado_em', 'atualizado_em')

    def save_model(self, request, obj, form, change):
        if 'carga_reducao_horas' in form.changed_data:
            obj.reducao_personalizada = True
        super().save_model(request, obj, form, change)


class AtividadeEstagioSupervisaoAdmin(HarpiaModelAdmin):
    list_display = (
        'unidade', 'tipo', 'professor', 'curso', 'semestre',
        'num_estudantes', 'carga_horaria_semanal', 'carga_reducao_horas', 'data_inicio', 'data_fim',
    )
    list_filter = ('unidade', 'tipo', 'semestre', 'data_inicio', 'data_fim')
    search_fields = ('professor__rh_nome', 'unidade__nome', 'observacoes')
    readonly_fields = ('criado_em', 'atualizado_em')


class SolicitacaoProfessorExternoAdmin(HarpiaModelAdmin):
    list_display = ('professor', 'unidade_origem', 'unidade_solicitante', 'semestre', 'status', 'criado_em')
    list_filter = ('status', 'semestre', 'unidade_origem', 'unidade_solicitante')
    search_fields = ('professor__rh_nome', 'justificativa', 'motivo_decisao')
    readonly_fields = ('criado_em', 'decidido_em')


class LimiteCargaUnidadeAdmin(HarpiaModelAdmin):
    list_display = ('unidade', 'limite_horas_semanais', 'data_inicio', 'data_fim')
    list_filter = ('unidade', 'data_inicio', 'data_fim')
    readonly_fields = ('criado_em', 'atualizado_em')


class ExcecaoCargaUnidadeAdmin(HarpiaModelAdmin):
    list_display = ('unidade', 'professor', 'horas_adicionais', 'data_inicio', 'data_fim', 'status')
    list_filter = ('status', 'unidade', 'data_inicio', 'data_fim')
    search_fields = ('professor__rh_nome', 'justificativa', 'motivo_decisao')
    readonly_fields = ('criado_em', 'decidido_em')


class ReadaptacaoProfessorAdmin(HarpiaModelAdmin):
    list_display = ('professor', 'data_inicio', 'data_fim', 'criado_por')
    list_filter = ('data_inicio', 'data_fim')
    search_fields = ('professor__rh_nome', 'professor__id_funcional')
    readonly_fields = ('criado_em', 'atualizado_em')

admin_site.register(Unidade, UnidadeAdmin)
admin_site.register(JanelaEntrega, JanelaEntregaAdmin)
admin_site.register(Notificacao, NotificacaoAdmin)
admin_site.register(AuditoriaGlobal, AuditoriaGlobalAdmin)
admin_site.register(ErroSistema, ErroSistemaAdmin)
admin_site.register(TipoCargoDiretivo, TipoCargoDiretivoAdmin)
admin_site.register(OcupacaoEquipeDiretiva, OcupacaoEquipeDiretivaAdmin)
admin_site.register(AtividadeEstagioSupervisao, AtividadeEstagioSupervisaoAdmin)
admin_site.register(SolicitacaoProfessorExterno, SolicitacaoProfessorExternoAdmin)
admin_site.register(LimiteCargaUnidade, LimiteCargaUnidadeAdmin)
admin_site.register(ExcecaoCargaUnidade, ExcecaoCargaUnidadeAdmin)
admin_site.register(ReadaptacaoProfessor, ReadaptacaoProfessorAdmin)
