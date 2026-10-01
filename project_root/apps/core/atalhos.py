"""Catálogo de destinos permitidos para os atalhos dos dashboards.

Guardar apenas a *chave* do atalho (não a URL crua) e validar contra este catálogo
funciona como whitelist: imuniza contra reverse quebrado e contra URL/redirect arbitrário.
Cada entrada também declara os perfis que realmente podem abrir o destino. Só entram
names reversíveis SEM kwargs.
"""

from django.urls import reverse


DESUP = 'DESUP'
UNIDADE = 'COORDENADOR_UNIDADE'
BOTH = (DESUP, UNIDADE)

ATALHOS_CATALOGO = {
    'matrix_list':      {'label': 'Matrizes Curriculares',      'url_name': 'courses:matrix_list',             'icon': 'ph-squares-four',       'profiles': BOTH},
    'matrix_create':    {'label': 'Nova Matriz',                'url_name': 'courses:matrix_create',           'icon': 'ph-plus-square',         'profiles': (DESUP,)},
    'component_list':   {'label': 'Componentes Curriculares',   'url_name': 'courses:component_list',          'icon': 'ph-list-bullets',        'profiles': (DESUP,)},
    'component_create': {'label': 'Novo Componente',            'url_name': 'courses:component_create',        'icon': 'ph-plus',                'profiles': (DESUP,)},
    'classgroup_list':  {'label': 'Turmas',                     'url_name': 'courses:classgroup_list',         'icon': 'ph-users-three',         'profiles': BOTH},
    'professor_list':   {'label': 'Professores',                'url_name': 'professors:professor_list',       'icon': 'ph-chalkboard-teacher',  'profiles': BOTH},
    'professor_create': {'label': 'Adicionar Professor',        'url_name': 'professors:professor_create',     'icon': 'ph-user-plus',           'profiles': (DESUP,)},
    'alloc_curricular': {'label': 'Alocação Curricular',        'url_name': 'alloc_curricular',                'icon': 'ph-git-branch',           'profiles': BOTH},
    'pendencia_list':   {'label': 'Pendências Extracurriculares','url_name': 'extra_curricular:pendencia_list','icon': 'ph-books',                'profiles': BOTH},
    'pendencia_create': {'label': 'Nova Pendência',             'url_name': 'extra_curricular:pendencia_create','icon': 'ph-note-pencil',        'profiles': (UNIDADE,)},
    'janela_list':      {'label': 'Janelas de Entrega',         'url_name': 'core:janela_list',                'icon': 'ph-calendar',             'profiles': (DESUP,)},
    'janela_create':    {'label': 'Nova Janela de Entrega',     'url_name': 'core:janela_create',              'icon': 'ph-calendar-plus',        'profiles': (DESUP,)},
    'unidade_list':     {'label': 'Unidades',                   'url_name': 'core:unidade_list',               'icon': 'ph-buildings',            'profiles': (DESUP,)},
    # "Adicionar Curso" aponta para a lista de unidades (cadastro de curso exige escolher a unidade).
    'adicionar_curso':  {'label': 'Adicionar Curso',            'url_name': 'core:unidade_list',               'icon': 'ph-graduation-cap',       'profiles': (DESUP,)},
    'exportar_logs':    {'label': 'Exportar Logs',              'url_name': 'core:exportar_logs',              'icon': 'ph-download-simple',      'profiles': (DESUP,)},
    'dashboard_desup':  {'label': 'Dashboard DESUP',            'url_name': 'dashboard_desup',                 'icon': 'ph-gauge',                'profiles': (DESUP,)},
    'dashboard_unidade':{'label': 'Dashboard da Unidade',       'url_name': 'dashboard_unidade',               'icon': 'ph-gauge',                'profiles': (UNIDADE,)},
}


def _perfis_efetivos(user):
    perfis = {getattr(user, 'perfil', None)}
    if getattr(user, 'is_superuser', False):
        perfis.add(DESUP)
    if getattr(user, 'is_authenticated', False):
        nomes_grupos = set(user.groups.values_list('name', flat=True))
        if 'Admin DESUP' in nomes_grupos:
            perfis.add(DESUP)
        if 'Gestor Unidade' in nomes_grupos:
            perfis.add(UNIDADE)
    return perfis


def catalogo_atalhos_para(user):
    """Retorna somente atalhos cujos destinos o perfil pode acessar."""
    perfis = _perfis_efetivos(user)
    return {
        chave: dados
        for chave, dados in ATALHOS_CATALOGO.items()
        if perfis.intersection(dados['profiles'])
    }


def _href(url_name, default=None):
    try:
        return reverse(url_name)
    except Exception:
        return default


def resolver_atalho(chave):
    """Chave do catálogo → {label, href, icon}. None se inválida/irreversível."""
    entrada = ATALHOS_CATALOGO.get(chave)
    if not entrada:
        return None
    href = _href(entrada['url_name'])
    if href is None:
        return None
    return {'label': entrada['label'], 'href': href, 'icon': entrada['icon']}
