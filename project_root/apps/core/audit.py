"""Auditoria detalhada do HARPIA DESUP.

O que este módulo faz
---------------------
* Guarda a requisição em andamento (middleware) para saber **quem** fez a ação.
* Escuta criação, alteração e exclusão dos cadastros principais (professor,
  unidade, curso, matriz, alocação, usuário, equipe diretiva...) e grava uma linha
  em ``AuditoriaGlobal`` dizendo **o quê**, **em qual registro** (ex.: o nome do
  professor), **em qual unidade**, **quem fez** e **quando** (data e hora).
* Nas alterações, lista campo a campo o valor de antes e o de depois.
* Registra acessos (login, logout e tentativas de login inválidas).

Regras importantes
------------------
* Só audita quando há uma requisição web ativa. Comandos de manutenção, importações
  em lote, seeds e testes unitários sem requisição não geram linhas (evita ruído).
* Alterações feitas por ``QuerySet.update()`` e ``bulk_create()`` não disparam
  sinais do Django e, por isso, não entram aqui.
* Nenhuma falha de auditoria pode derrubar a ação do usuário: tudo é protegido por
  ``try/except`` e por um savepoint.
* Nunca grava senha, token ou ``last_login``.
"""
import datetime
import ipaddress
import logging
import threading
import uuid
from decimal import Decimal

from django.apps import apps as django_apps
from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.db import models, transaction
from django.db.models.signals import m2m_changed, post_delete, post_save, pre_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger(__name__)

_local = threading.local()

# Acima disso, o restante vira uma única linha-resumo (ex.: exclusão em cascata ou
# formulário em lote com centenas de linhas) para o log não explodir.
MAX_LINHAS_POR_REQUISICAO = 200

CAMPOS_IGNORADOS = {'password', 'last_login', 'token_hash'}
LIMITE_TEXTO_VALOR = 300
LIMITE_TEXTO_DADOS = 1800

CRIACAO, ALTERACAO, EXCLUSAO, ACESSO, SEGURANCA, OUTRO = (
    'CRIACAO', 'ALTERACAO', 'EXCLUSAO', 'ACESSO', 'SEGURANCA', 'OUTRO',
)


# ---------------------------------------------------------------------------
# Utilidades de texto
# ---------------------------------------------------------------------------

def inferir_categoria(acao):
    """Classifica o código de ação (ex.: ``CARGO_DIRETIVO_CRIADO``) em um tipo simples."""
    acao = (acao or '').upper()
    if acao.startswith(('LOGIN', 'LOGOUT')):
        return ACESSO
    if 'PASSWORD' in acao or 'SENHA' in acao:
        return SEGURANCA
    if any(chave in acao for chave in ('EXCLUID', 'REMOVID', 'DELETE')):
        return EXCLUSAO
    if any(chave in acao for chave in ('CRIAD', 'CADASTRAD', 'CREATED')):
        return CRIACAO
    if any(chave in acao for chave in (
        'ATUALIZAD', 'ALTERAD', 'DECIDID', 'ARQUIVAD', 'REATIVAD', 'PAUSAD', 'ENCERRAD',
    )):
        return ALTERACAO
    return OUTRO


def _cortar(texto, limite):
    texto = str(texto)
    return texto if len(texto) <= limite else texto[: limite - 1].rstrip() + '…'


def _nome_unidade(unidade):
    if unidade is None:
        return ''
    nome = getattr(unidade, 'nome', '') or str(unidade)
    sigla = getattr(unidade, 'sigla', '') or ''
    return f'{nome} ({sigla})' if sigla and sigla != nome else nome


def _ip(request):
    if request is None:
        return None
    meta = getattr(request, 'META', {}) or {}
    forwarded = meta.get('HTTP_X_FORWARDED_FOR', '')
    candidatos = [forwarded.split(',', 1)[0].strip(), meta.get('REMOTE_ADDR')]
    for candidato in candidatos:
        if not candidato:
            continue
        try:
            return str(ipaddress.ip_address(candidato))
        except ValueError:
            continue
    return None


def _perfil_texto(user):
    if getattr(user, '_harpia_superadmin_original', False):
        modo = {'DESUP': 'DESUP', 'COORDENADOR_UNIDADE': 'Unidade'}.get(
            getattr(user, '_harpia_visualization_mode', ''), '',
        )
        return f'Superadmin (visualizando como {modo})' if modo else 'Superadmin'
    if getattr(user, 'is_superuser', False):
        return 'Superadmin'
    try:
        return user.get_perfil_display() or getattr(user, 'perfil', '') or ''
    except Exception:  # pragma: no cover - defensivo
        return getattr(user, 'perfil', '') or ''


def _ator(request, usuario=None):
    """Devolve (usuário, e-mail, perfil, nome da unidade) de quem fez a ação."""
    user = usuario
    if user is None and request is not None:
        user = getattr(request, 'user', None)
    if user is None or not getattr(user, 'is_authenticated', False):
        return None, '', '', ''
    try:
        unidade = _nome_unidade(getattr(user, 'unidade', None))
    except Exception:  # pragma: no cover - defensivo
        unidade = ''
    return user, getattr(user, 'email', '') or '', _perfil_texto(user), unidade


# ---------------------------------------------------------------------------
# Contexto da requisição (quem está agindo)
# ---------------------------------------------------------------------------

def _request_ativo():
    return getattr(_local, 'request', None)


def _estado(request):
    estado = getattr(request, '_harpia_audit', None)
    if estado is None:
        estado = {
            'pendentes': [], 'total': 0, 'excedentes': {}, 'linhas': {},
            # Mesmo código em todas as linhas geradas por esta requisição: permite ver,
            # a partir de uma linha, tudo o que a mesma ação do usuário alterou.
            'operacao': uuid.uuid4().hex,
        }
        request._harpia_audit = estado
    return estado


def _caminho(request):
    if request is None:
        return ''
    metodo = getattr(request, 'method', '') or ''
    caminho = getattr(request, 'path', '') or ''
    return f'{metodo} {caminho}'.strip()[:255]


class AuditContextMiddleware:
    """Guarda a requisição atual e, ao final, grava o que ficou pendente."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _local.request = request
        try:
            return self.get_response(request)
        finally:
            try:
                finalizar_requisicao(request)
            except Exception:
                logger.exception('Falha ao finalizar a auditoria da requisição.')
            _local.request = None


# ---------------------------------------------------------------------------
# Gravação
# ---------------------------------------------------------------------------

# Prefixos de códigos de ação que não vêm de um modelo de `CONFIG` (eventos explícitos).
ENTIDADES_EXTRAS = {
    'EXTRACURRICULAR': 'Atividade extracurricular',
    'LOGIN': 'Acesso ao sistema',
    'LOGOUT': 'Acesso ao sistema',
    'PASSWORD': 'Senha de usuário',
    'DESUP_PASSWORD': 'Senha de usuário',
    'ADMIN_FORCE_PASSWORD': 'Senha de usuário',
    'OPERACAO_EM_LOTE': 'Operação em lote',
    'AUDITORIA': 'Auditoria',
}

# Nomes em português para códigos de ação que não seguem o padrão `<MODELO>_<VERBO>`.
TITULOS_ACAO = {
    'LOGIN': 'Entrou no sistema',
    'LOGOUT': 'Saiu do sistema',
    'LOGIN_FALHOU': 'Tentativa de acesso recusada',
    'PASSWORD_RESET_EMAIL_REQUESTED': 'Link de redefinição de senha enviado por e-mail',
    'PASSWORD_RESET_COMPLETED_BY_EMAIL': 'Senha redefinida pelo link enviado por e-mail',
    'DESUP_PASSWORD_FORCE_RESET': 'Senha redefinida pela DESUP (troca obrigatória)',
    'ADMIN_FORCE_PASSWORD_RESET': 'Senha redefinida pelo superadmin (troca obrigatória)',
    'MATRIZ_VIGENTE_EDITADA': 'Matriz vigente editada',
    'MATRIZ_ARQUIVADA': 'Matriz arquivada',
    'MATRIZ_REATIVADA': 'Matriz reativada',
    'EXTRACURRICULAR_EXCLUIDO': 'Item extracurricular excluído',
    'OPERACAO_EM_LOTE': 'Operação em lote (resumo)',
    'AUDITORIA_EXPORTADA': 'Auditoria exportada em CSV',
    'USUARIO_ATIVADO': 'Contas de usuário ativadas',
    'USUARIO_DESATIVADO': 'Contas de usuário desativadas',
}


def inferir_entidade(acao):
    """Descobre "o que foi mexido" a partir do prefixo do código da ação."""
    codigo = (acao or '').upper()
    candidatos = [(cfg['codigo'], cfg['label']) for cfg in CONFIG.values()]
    candidatos += list(ENTIDADES_EXTRAS.items())
    for prefixo, rotulo in sorted(candidatos, key=lambda par: -len(par[0])):
        if codigo == prefixo or codigo.startswith(prefixo + '_'):
            return rotulo
    return ''


def titulo_da_acao(acao):
    """Nome legível da ação (ex.: ``PROFESSOR_ALTERADO`` → "Professor alterado")."""
    codigo = (acao or '').upper()
    if codigo in TITULOS_ACAO:
        return TITULOS_ACAO[codigo]
    for cfg in CONFIG.values():
        for categoria, sufixo in _SUFIXO_ACAO.items():
            if codigo == f"{cfg['codigo']}_{sufixo}":
                return f"{cfg['label']} {_VERBOS[cfg['g']][categoria]}"
    texto = codigo.replace('_', ' ').strip().capitalize()
    return texto or '—'


def _campos_do_item(item, primeiro):
    """Campos alterados de uma pendência; identifica o registro quando difere do primeiro."""
    campos = list(item.get('campos') or [])
    if (item['modelo'], item['pk']) == (primeiro['modelo'], primeiro['pk']):
        return campos
    origem = f"{item['entidade']} {item['objeto']}".strip()
    return [{**campo, 'campo': f"{origem} — {campo['campo']}"} for campo in campos]


def registrar(
    request, acao, detalhes='', *, categoria=None, entidade='', objeto='', objeto_id='',
    unidade_objeto='', usuario=None, email='', absorver=True, mudancas=None,
):
    """Grava uma linha de auditoria. Nunca levanta exceção para quem chamou.

    Quando `absorver` é verdadeiro, as alterações de cadastro feitas na mesma
    requisição por modelos de "evento explícito" (equipe diretiva, cargos, limites,
    readaptações, matrizes, usuários...) são anexadas ao texto deste evento, que
    passa a dizer exatamente o que mudou. Se, mesmo assim, o evento não souber qual
    registro foi mexido, ele herda o primeiro registro gravado na mesma requisição
    (ex.: o item extracurricular excluído) e, por fim, deduz o tipo pelo código da ação.

    `mudancas` é a lista estruturada ``[{campo, antes, depois}]`` exibida como tabela
    no painel de auditoria.
    """
    from .models import AuditoriaGlobal

    try:
        campos = list(mudancas or [])
        if absorver and request is not None:
            estado = getattr(request, '_harpia_audit', None)
            if estado and estado['pendentes']:
                itens, estado['pendentes'] = estado['pendentes'], []
                bloco = '\n'.join(f"• {item['texto']}" for item in itens)
                detalhes = f'{detalhes}\n{bloco}' if detalhes else bloco
                primeiro = itens[0]
                entidade = entidade or primeiro['entidade']
                objeto = objeto or primeiro['objeto']
                objeto_id = objeto_id or primeiro['objeto_id']
                unidade_objeto = unidade_objeto or primeiro['unidade']
                for item in itens:
                    campos.extend(_campos_do_item(item, primeiro))

        if absorver and request is not None and not objeto:
            estado = getattr(request, '_harpia_audit', None)
            if estado and estado['linhas']:
                anterior = next(iter(estado['linhas'].values()))
                entidade = entidade or anterior.entidade
                objeto = anterior.objeto
                objeto_id = objeto_id or anterior.objeto_id
                unidade_objeto = unidade_objeto or anterior.unidade_objeto

        user, email_ator, perfil, unidade_ator = _ator(request, usuario)
        categoria_final = categoria or inferir_categoria(acao)
        entidade = entidade or inferir_entidade(acao)
        if not objeto and entidade in ('Senha de usuário', 'Acesso ao sistema'):
            objeto = email or email_ator
        operacao = _estado(request)['operacao'] if request is not None else ''
        linha = AuditoriaGlobal(
            usuario=user,
            email=(email or email_ator or '')[:254],
            perfil_usuario=perfil[:80],
            unidade_usuario=unidade_ator[:255],
            acao=str(acao)[:120],
            categoria=categoria_final,
            entidade=str(entidade or '')[:80],
            objeto=str(objeto or '')[:255],
            objeto_id=str(objeto_id or '')[:40],
            unidade_objeto=str(unidade_objeto or '')[:255],
            detalhes=detalhes or '',
            mudancas=campos,
            operacao=operacao,
            caminho=_caminho(request),
            ip=_ip(request),
            user_agent=((getattr(request, 'META', {}) or {}).get('HTTP_USER_AGENT') or '')[:1000],
        )
        with transaction.atomic():
            linha.save()
        return linha
    except Exception:
        logger.exception('Não foi possível gravar o evento de auditoria %s.', acao)
        return None


def finalizar_requisicao(request):
    """Grava o que ficou pendente e a linha-resumo de operações muito grandes."""
    estado = getattr(request, '_harpia_audit', None)
    if not estado:
        return
    pendentes, estado['pendentes'] = estado['pendentes'], []
    for mudanca in pendentes:
        _gravar_mudanca(request, mudanca)
    excedentes = estado['excedentes']
    if excedentes:
        estado['excedentes'] = {}
        resumo = ', '.join(f'{qtd}× {chave}' for chave, qtd in sorted(excedentes.items()))
        registrar(
            request, 'OPERACAO_EM_LOTE',
            'Operação com muitos registros. Além das primeiras '
            f'{MAX_LINHAS_POR_REQUISICAO} linhas do log, também foram afetados: {resumo}.',
            categoria=OUTRO, absorver=False,
        )


# ---------------------------------------------------------------------------
# Descrição dos modelos auditados
# ---------------------------------------------------------------------------

def _un(obj, *caminhos):
    """Primeiro caminho (``a.b.c``) que levar a uma unidade."""
    for caminho in caminhos:
        atual = obj
        for parte in caminho.split('.'):
            atual = getattr(atual, parte, None)
            if atual is None:
                break
        if atual is not None:
            return _nome_unidade(atual)
    return ''


def _unidades_m2m(obj, campo='unidades'):
    try:
        if not obj.pk:
            return ''
        return ' | '.join(_nome_unidade(u) for u in getattr(obj, campo).all())
    except Exception:
        return ''


def _un_professor(prof):
    nomes = []
    if getattr(prof, 'unidade_principal_id', None):
        nomes.append(_nome_unidade(prof.unidade_principal))
    try:
        if prof.pk:
            nomes.extend(_nome_unidade(u) for u in prof.unidades.all())
    except Exception:
        pass
    return ' | '.join(dict.fromkeys(n for n in nomes if n))


def _nome_prof(prof):
    try:
        return prof.nome
    except Exception:
        return ''


def _obj_professor(prof):
    base = prof.nome or 'Sem nome'
    return f'{base} (ID funcional {prof.id_funcional})' if prof.id_funcional else base


def _obj_ocupacao(o):
    partes = [_nome_prof(o.professor), getattr(o.cargo, 'nome', '')]
    return ' — '.join(p for p in partes if p) or str(o)


def _obj_atividade_estagio(a):
    return f'{a.get_tipo_display()} — {_nome_prof(a.professor)}'


def _obj_solicitacao_externo(s):
    nome = s.professor_nome or (_nome_prof(s.professor) if s.professor_id else '')
    return f'{s.get_tipo_display()} — {nome}' if nome else str(s)


# Cada entrada: label (texto), g (gênero: m/f), codigo (prefixo do código da ação),
# objeto (como chamar o registro), unidade (a que unidade pertence),
# defer (True = evento explícito costuma acompanhar; o texto é anexado a ele),
# m2m (campos many-to-many que também devem ser acompanhados).
CONFIG = {
    'professors.professor': dict(
        label='Professor', g='m', codigo='PROFESSOR', objeto=_obj_professor,
        unidade=_un_professor, m2m=('unidades', 'cursos'),
    ),
    'professors.contracttype': dict(label='Tipo de contrato', g='m', codigo='TIPO_CONTRATO'),
    'professors.availability': dict(
        label='Disponibilidade de professor', g='f', codigo='DISPONIBILIDADE',
        unidade=lambda o: _un_professor(o.professor),
    ),
    'professors.absencerecord': dict(
        label='Ausência de professor', g='f', codigo='AUSENCIA',
        unidade=lambda o: _un_professor(o.professor),
    ),
    'core.unidade': dict(
        label='Unidade', g='f', codigo='UNIDADE', objeto=lambda u: _nome_unidade(u),
        unidade=lambda u: _nome_unidade(u),
    ),
    'core.janelaentrega': dict(
        label='Janela de entrega', g='f', codigo='JANELA_ENTREGA',
        unidade=lambda o: _un(o, 'unidade') or 'Todas as unidades',
    ),
    'core.tipocargodiretivo': dict(
        label='Cargo diretivo', g='m', codigo='CARGO_DIRETIVO', defer=True,
    ),
    'core.configuracaocargodiretivounidade': dict(
        label='Redução de cargo diretivo na unidade', g='f', codigo='REDUCAO_CARGO_UNIDADE',
        unidade=lambda o: _un(o, 'unidade'), defer=True,
    ),
    'core.ocupacaoequipediretiva': dict(
        label='Ocupação de cargo diretivo', g='f', codigo='OCUPACAO_DIRETIVA',
        objeto=_obj_ocupacao, unidade=lambda o: _un(o, 'unidade'), defer=True,
    ),
    'core.atividadeestagiosupervisao': dict(
        label='Atividade de estágio/supervisão', g='f', codigo='ATIVIDADE_ESTAGIO',
        objeto=_obj_atividade_estagio, unidade=lambda o: _un(o, 'unidade'), defer=True,
    ),
    'core.solicitacaoprofessorexterno': dict(
        label='Solicitação de professor externo', g='f', codigo='SOLICITACAO_PROFESSOR',
        objeto=_obj_solicitacao_externo, unidade=lambda o: _un(o, 'unidade_solicitante'),
        defer=True,
    ),
    'core.limitecargaunidade': dict(
        label='Teto semanal de carga da unidade', g='m', codigo='LIMITE_CARGA',
        unidade=lambda o: _un(o, 'unidade'), defer=True,
    ),
    'core.excecaocargaunidade': dict(
        label='Exceção de carga', g='f', codigo='EXCECAO_CARGA',
        objeto=lambda o: f'Exceção de {_nome_prof(o.professor)}',
        unidade=lambda o: _un(o, 'unidade'), defer=True,
    ),
    'core.readaptacaoprofessor': dict(
        label='Readaptação de professor', g='f', codigo='READAPTACAO',
        objeto=lambda o: f'Readaptação de {_nome_prof(o.professor)}',
        unidade=lambda o: _un_professor(o.professor), defer=True,
    ),
    'courses.course': dict(label='Curso', g='m', codigo='CURSO'),
    'courses.courseunit': dict(
        label='Curso na unidade', g='m', codigo='CURSO_UNIDADE',
        unidade=lambda o: _un(o, 'unidade'),
    ),
    'courses.curricularcomponent': dict(
        label='Componente curricular', g='m', codigo='COMPONENTE_CURRICULAR',
    ),
    'courses.curriculummatrix': dict(
        label='Matriz curricular', g='f', codigo='MATRIZ', unidade=_unidades_m2m,
        m2m=('unidades',), defer=True,
    ),
    'courses.matrixcomponent': dict(
        label='Componente da matriz', g='m', codigo='COMPONENTE_MATRIZ',
        unidade=lambda o: _unidades_m2m(o.matriz),
    ),
    'courses.classgroup': dict(
        label='Turma', g='f', codigo='TURMA',
        unidade=lambda o: _unidades_m2m(o.matriz_curricular),
    ),
    'allocations.alocacaocurricular': dict(
        label='Alocação curricular', g='f', codigo='ALOCACAO_CURRICULAR',
        unidade=lambda o: _un(o, 'unidade'),
    ),
    'allocations.alocacaoturmadocente': dict(
        label='Alocação de professor em turma', g='f', codigo='ALOCACAO_DOCENTE',
        unidade=lambda o: _un(o, 'alocacao_curricular.unidade'),
    ),
    'allocations.carencia': dict(
        label='Carência', g='f', codigo='CARENCIA',
        unidade=lambda o: _un(o, 'alocacao_turma_docente.alocacao_curricular.unidade'),
    ),
    'allocations.solicitacaorat': dict(
        label='Solicitação de RAT', g='f', codigo='RAT',
        unidade=lambda o: _un(
            o, 'carencia.alocacao_turma_docente.alocacao_curricular.unidade', 'solicitado_por.unidade',
        ),
    ),
    'extra_curricular.pendenciaextra': dict(
        label='Justificativa extracurricular', g='f', codigo='PENDENCIA_EXTRA',
        unidade=lambda o: _un(o, 'unidade'),
    ),
    'extra_curricular.orientacaotcc': dict(
        label='Orientação de TCC', g='f', codigo='ORIENTACAO_TCC',
        unidade=lambda o: _un(o, 'pendencia.unidade'),
    ),
    'extra_curricular.atividadeextensionista': dict(
        label='Atividade extensionista', g='f', codigo='ATIVIDADE_EXTENSIONISTA',
        unidade=lambda o: _un(o, 'pendencia.unidade'),
    ),
    'extra_curricular.reducaocargahoraria': dict(
        label='Redução de carga horária', g='f', codigo='REDUCAO_CARGA_HORARIA',
        unidade=lambda o: _un(o, 'pendencia.unidade'),
    ),
    'extra_curricular.licencadocente': dict(
        label='Licença de docente', g='f', codigo='LICENCA_DOCENTE',
        unidade=lambda o: _un(o, 'pendencia.unidade'),
    ),
    'accounts.user': dict(
        label='Usuário', g='m', codigo='USUARIO', objeto=lambda u: u.email or str(u),
        unidade=lambda o: _un(o, 'unidade'), defer=True,
    ),
}

_VERBOS = {
    'm': {CRIACAO: 'cadastrado', ALTERACAO: 'alterado', EXCLUSAO: 'excluído'},
    'f': {CRIACAO: 'cadastrada', ALTERACAO: 'alterada', EXCLUSAO: 'excluída'},
}
_SUFIXO_ACAO = {CRIACAO: 'CRIADO', ALTERACAO: 'ALTERADO', EXCLUSAO: 'EXCLUIDO'}


def _rotulo(obj):
    """Nome legível de um registro (ex.: o nome do professor)."""
    try:
        cfg = CONFIG.get(obj._meta.label_lower) or {}
        if cfg.get('objeto'):
            return str(cfg['objeto'](obj))
        return str(obj)
    except Exception:
        return f'{obj._meta.verbose_name} #{obj.pk}'


def _unidade_do_registro(obj):
    try:
        cfg = CONFIG.get(obj._meta.label_lower) or {}
        resolver = cfg.get('unidade')
        return resolver(obj) if resolver else ''
    except Exception:
        return ''


def _campos_auditados(model, update_fields=None):
    campos = []
    nomes = set(update_fields) if update_fields is not None else None
    for campo in model._meta.concrete_fields:
        if campo.primary_key or campo.name in CAMPOS_IGNORADOS:
            continue
        if isinstance(campo, (models.DateTimeField, models.DateField)) and (
            getattr(campo, 'auto_now', False) or getattr(campo, 'auto_now_add', False)
        ):
            continue
        if nomes is not None and campo.name not in nomes and campo.attname not in nomes:
            continue
        campos.append(campo)
    return campos


def _formatar_valor(campo, valor):
    if valor is None or valor == '':
        return '—'
    try:
        if campo.is_relation and (campo.many_to_one or campo.one_to_one):
            relacionado = campo.remote_field.model._base_manager.filter(pk=valor).first()
            return _rotulo(relacionado) if relacionado is not None else f'#{valor}'
        if campo.choices:
            return str(dict(campo.flatchoices).get(valor, valor))
        if isinstance(valor, bool):
            return 'Sim' if valor else 'Não'
        if isinstance(valor, datetime.datetime):
            if timezone.is_aware(valor):
                valor = timezone.localtime(valor)
            return valor.strftime('%d/%m/%Y %H:%M')
        if isinstance(valor, datetime.date):
            return valor.strftime('%d/%m/%Y')
        if isinstance(valor, Decimal):
            return format(valor.normalize(), 'f').replace('.', ',')
        return _cortar(' '.join(str(valor).split()), LIMITE_TEXTO_VALOR)
    except Exception:
        return _cortar(valor, LIMITE_TEXTO_VALOR)


def _rotulo_campo(campo):
    nome = str(campo.verbose_name)
    return nome[:1].upper() + nome[1:]


def _pares_do_registro(instance):
    """Lista (rótulo, valor formatado) de tudo o que está preenchido no registro."""
    pares = []
    for campo in _campos_auditados(type(instance)):
        valor = getattr(instance, campo.attname, None)
        if valor is None or valor == '':
            continue
        pares.append((_rotulo_campo(campo), _formatar_valor(campo, valor)))
    return pares


def _dados_do_registro(instance):
    """Texto 'Campo: valor' de tudo o que está preenchido (para criação e exclusão)."""
    partes = [f'{rotulo}: {valor}' for rotulo, valor in _pares_do_registro(instance)]
    return _cortar('; '.join(partes), LIMITE_TEXTO_DADOS)


def _campos_de_criacao_ou_exclusao(instance, categoria):
    """Versão estruturada de `_dados_do_registro`: antes/depois por campo preenchido."""
    if categoria == EXCLUSAO:
        return [
            {'campo': rotulo, 'antes': valor, 'depois': '—'}
            for rotulo, valor in _pares_do_registro(instance)
        ]
    return [
        {'campo': rotulo, 'antes': '—', 'depois': valor}
        for rotulo, valor in _pares_do_registro(instance)
    ]


def _montar_mudanca(
    instance, categoria, *, dados='', diffs=None, objeto=None, unidade=None, campos=None,
):
    label_model = instance._meta.label_lower
    cfg = CONFIG[label_model]
    objeto = objeto if objeto is not None else _rotulo(instance)
    unidade = unidade if unidade is not None else _unidade_do_registro(instance)
    verbo = _VERBOS[cfg['g']][categoria]
    texto = f"{cfg['label']} {verbo}: {objeto}."
    if unidade and unidade != objeto:
        texto += f' Unidade: {unidade}.'
    if diffs:
        texto += ' Alterações: ' + '; '.join(diffs) + '.'
    elif dados:
        rotulo_dados = 'Dados no momento da exclusão' if categoria == EXCLUSAO else 'Dados informados'
        texto += f' {rotulo_dados}: {dados}.'
    return {
        'modelo': label_model,
        'pk': instance.pk,
        'acao': f"{cfg['codigo']}_{_SUFIXO_ACAO[categoria]}",
        'categoria': categoria,
        'entidade': cfg['label'],
        'objeto': objeto,
        'objeto_id': str(instance.pk or ''),
        'unidade': unidade,
        'texto': texto,
        'campos': list(campos or []),
    }


def _gravar_mudanca(request, mudanca):
    estado = _estado(request)
    if estado['total'] >= MAX_LINHAS_POR_REQUISICAO:
        chave = f"{mudanca['entidade']} ({_rotulo_categoria(mudanca['categoria'])})"
        estado['excedentes'][chave] = estado['excedentes'].get(chave, 0) + 1
        return None
    estado['total'] += 1
    linha = registrar(
        request, mudanca['acao'], mudanca['texto'], categoria=mudanca['categoria'],
        entidade=mudanca['entidade'], objeto=mudanca['objeto'], objeto_id=mudanca['objeto_id'],
        unidade_objeto=mudanca['unidade'], mudancas=mudanca.get('campos'), absorver=False,
    )
    if linha is not None:
        estado['linhas'][(mudanca['modelo'], mudanca['pk'])] = linha
    return linha


def _rotulo_categoria(categoria):
    return {
        CRIACAO: 'cadastros', ALTERACAO: 'alterações', EXCLUSAO: 'exclusões',
    }.get(categoria, 'registros')


def _enviar(request, mudanca):
    if CONFIG[mudanca['modelo']].get('defer'):
        _estado(request)['pendentes'].append(mudanca)
    else:
        _gravar_mudanca(request, mudanca)


def _anexar_texto(request, modelo, pk, texto, unidade=None, campos_estruturados=None):
    """Anexa `texto` (e os campos estruturados) à linha/pendência do mesmo registro."""
    estado = _estado(request)
    novos = list(campos_estruturados or [])
    for mudanca in estado['pendentes']:
        if mudanca['modelo'] == modelo and mudanca['pk'] == pk:
            mudanca['texto'] += f'\n{texto}'
            mudanca.setdefault('campos', []).extend(novos)
            if unidade:
                mudanca['unidade'] = unidade
            return True
    linha = estado['linhas'].get((modelo, pk))
    if linha is None:
        return False
    linha.detalhes = f'{linha.detalhes}\n{texto}' if linha.detalhes else texto
    campos = ['detalhes']
    if novos:
        linha.mudancas = list(linha.mudancas or []) + novos
        campos.append('mudancas')
    if unidade:
        linha.unidade_objeto = unidade[:255]
        campos.append('unidade_objeto')
    try:
        with transaction.atomic():
            linha.save(update_fields=campos)
    except Exception:
        logger.exception('Não foi possível complementar o evento de auditoria %s.', linha.pk)
    return True


# ---------------------------------------------------------------------------
# Receivers de modelos
# ---------------------------------------------------------------------------

def _pre_save(sender, instance, raw=False, update_fields=None, **kwargs):
    instance._audit_antes = None
    if raw or _request_ativo() is None or instance._state.adding or not instance.pk:
        return
    try:
        campos = _campos_auditados(sender, update_fields)
        if not campos:
            return
        antigo = sender._base_manager.filter(pk=instance.pk).first()
        if antigo is None:
            return
        instance._audit_antes = {campo.attname: getattr(antigo, campo.attname) for campo in campos}
        instance._audit_campos = campos
    except Exception:
        logger.exception('Falha ao ler o estado anterior de %s.', sender.__name__)


def _post_save(sender, instance, created, raw=False, update_fields=None, **kwargs):
    request = _request_ativo()
    if request is None or raw:
        return
    try:
        if created:
            mudanca = _montar_mudanca(
                instance, CRIACAO, dados=_dados_do_registro(instance),
                campos=_campos_de_criacao_ou_exclusao(instance, CRIACAO),
            )
        else:
            antes = getattr(instance, '_audit_antes', None)
            if not antes:
                return
            diffs = []
            campos_diff = []
            for campo in getattr(instance, '_audit_campos', []):
                antigo = antes.get(campo.attname)
                novo = getattr(instance, campo.attname, None)
                if (antigo in (None, '')) and (novo in (None, '')):
                    continue
                if antigo == novo:
                    continue
                valor_antes = _formatar_valor(campo, antigo)
                valor_depois = _formatar_valor(campo, novo)
                diffs.append(f'{_rotulo_campo(campo)}: {valor_antes} → {valor_depois}')
                campos_diff.append({
                    'campo': _rotulo_campo(campo), 'antes': valor_antes, 'depois': valor_depois,
                })
            if not diffs:
                return
            mudanca = _montar_mudanca(instance, ALTERACAO, diffs=diffs, campos=campos_diff)
        _enviar(request, mudanca)
    except Exception:
        logger.exception('Falha ao auditar %s #%s.', sender.__name__, instance.pk)
    finally:
        instance._audit_antes = None


def _pre_delete(sender, instance, **kwargs):
    if _request_ativo() is None:
        return
    try:
        instance._audit_instantaneo = _montar_mudanca(
            instance, EXCLUSAO, dados=_dados_do_registro(instance),
            campos=_campos_de_criacao_ou_exclusao(instance, EXCLUSAO),
        )
    except Exception:
        instance._audit_instantaneo = None
        logger.exception('Falha ao registrar o estado de %s antes da exclusão.', sender.__name__)


def _post_delete(sender, instance, **kwargs):
    request = _request_ativo()
    mudanca = getattr(instance, '_audit_instantaneo', None)
    if request is None or not mudanca:
        return
    instance._audit_instantaneo = None
    try:
        _enviar(request, mudanca)
    except Exception:
        logger.exception('Falha ao auditar a exclusão de %s.', sender.__name__)


def _criar_handler_m2m(modelo, campo):
    def _handler(sender, instance, action, reverse, model, pk_set, **kwargs):
        request = _request_ativo()
        if request is None or reverse:
            return
        try:
            if action == 'pre_clear':
                instance.__dict__.setdefault('_audit_clear', {})[campo] = [
                    _rotulo(o) for o in getattr(instance, campo).all()
                ]
                return
            if action not in ('post_add', 'post_remove', 'post_clear'):
                return
            if action == 'post_clear':
                nomes = instance.__dict__.get('_audit_clear', {}).pop(campo, [])
            else:
                if not pk_set:
                    return
                nomes = [_rotulo(o) for o in model._base_manager.filter(pk__in=pk_set)]
            if not nomes:
                return
            adicionou = action == 'post_add'
            rotulo_campo = str(instance._meta.get_field(campo).verbose_name)
            rotulo_campo = rotulo_campo[:1].upper() + rotulo_campo[1:]
            texto = (
                f"{rotulo_campo} — "
                f"{'adicionado(s)' if adicionou else 'removido(s)'}: {', '.join(nomes)}."
            )
            lista_nomes = ', '.join(nomes)
            campos_m2m = [{
                'campo': f"{rotulo_campo} ({'adicionado(s)' if adicionou else 'removido(s)'})",
                'antes': '—' if adicionou else lista_nomes,
                'depois': lista_nomes if adicionou else '—',
            }]
            cfg = CONFIG[modelo]
            unidade = _unidade_do_registro(instance)
            if _anexar_texto(
                request, modelo, instance.pk, texto, unidade or None,
                campos_estruturados=campos_m2m,
            ):
                return
            objeto = _rotulo(instance)
            mudanca = {
                'modelo': modelo,
                'pk': instance.pk,
                'acao': f"{cfg['codigo']}_ALTERADO",
                'categoria': ALTERACAO,
                'entidade': cfg['label'],
                'objeto': objeto,
                'objeto_id': str(instance.pk or ''),
                'unidade': unidade,
                'texto': (
                    f"{cfg['label']} {_VERBOS[cfg['g']][ALTERACAO]}: {objeto}."
                    + (f' Unidade: {unidade}.' if unidade else '')
                    + f' {texto}'
                ),
                'campos': campos_m2m,
            }
            _enviar(request, mudanca)
        except Exception:
            logger.exception('Falha ao auditar a relação %s de %s.', campo, modelo)

    return _handler


def conectar_sinais():
    """Liga os receivers aos modelos de `CONFIG`. Chamado em `CoreConfig.ready()`."""
    for label in CONFIG:
        try:
            modelo = django_apps.get_model(label)
        except LookupError:
            logger.warning('Auditoria: modelo %s não encontrado; ignorado.', label)
            continue
        uid = f'harpia-audit-{label}'
        pre_save.connect(_pre_save, sender=modelo, weak=False, dispatch_uid=f'{uid}-pre-save')
        post_save.connect(_post_save, sender=modelo, weak=False, dispatch_uid=f'{uid}-post-save')
        pre_delete.connect(_pre_delete, sender=modelo, weak=False, dispatch_uid=f'{uid}-pre-delete')
        post_delete.connect(_post_delete, sender=modelo, weak=False, dispatch_uid=f'{uid}-post-delete')
        for campo in CONFIG[label].get('m2m', ()):
            through = getattr(modelo, campo).through
            m2m_changed.connect(
                _criar_handler_m2m(label, campo), sender=through, weak=False,
                dispatch_uid=f'{uid}-m2m-{campo}',
            )


# ---------------------------------------------------------------------------
# Acessos
# ---------------------------------------------------------------------------

def _request_real(request):
    """Ignora o HttpRequest vazio que o `client.force_login` dos testes cria."""
    return request is not None and bool((getattr(request, 'META', {}) or {}).get('REMOTE_ADDR'))


@receiver(user_logged_in, dispatch_uid='harpia-audit-login')
def _registrar_login(sender, request, user, **kwargs):
    if not _request_real(request):
        return
    registrar(
        request, 'LOGIN', f'{user.email} entrou no sistema.', categoria=ACESSO,
        usuario=user, absorver=False,
    )


@receiver(user_logged_out, dispatch_uid='harpia-audit-logout')
def _registrar_logout(sender, request, user, **kwargs):
    if user is None or not _request_real(request):
        return
    registrar(
        request, 'LOGOUT', f'{user.email} saiu do sistema.', categoria=ACESSO,
        usuario=user, absorver=False,
    )


@receiver(user_login_failed, dispatch_uid='harpia-audit-login-failed')
def _registrar_login_falho(sender, credentials, request=None, **kwargs):
    if not _request_real(request):
        return
    tentativa = str(credentials.get('username') or credentials.get('email') or '')[:254]
    registrar(
        request, 'LOGIN_FALHOU',
        f'Tentativa de acesso recusada (e-mail ou senha inválidos) para "{tentativa}".',
        categoria=ACESSO, email=tentativa if '@' in tentativa else '', absorver=False,
    )
