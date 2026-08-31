"""Catálogo de destinos permitidos para os atalhos do dashboard DESUP.

Guardar apenas a *chave* do atalho (não a URL crua) e validar contra este catálogo
funciona como whitelist: imuniza contra reverse quebrado e contra URL/redirect arbitrário.
Só entram names reversíveis SEM kwargs.
"""

from django.urls import reverse

ATALHOS_CATALOGO = {
    'matrix_list':      {'label': 'Matrizes Curriculares',      'url_name': 'courses:matrix_list',            'icon': 'ph-squares-four'},
    'matrix_create':    {'label': 'Nova Matriz',                'url_name': 'courses:matrix_create',          'icon': 'ph-plus-square'},
    'component_list':   {'label': 'Componentes Curriculares',   'url_name': 'courses:component_list',         'icon': 'ph-list-bullets'},
    'component_create': {'label': 'Novo Componente',            'url_name': 'courses:component_create',       'icon': 'ph-plus'},
    'classgroup_list':  {'label': 'Turmas',                     'url_name': 'courses:classgroup_list',        'icon': 'ph-users-three'},
    'professor_list':   {'label': 'Professores',                'url_name': 'professors:professor_list',      'icon': 'ph-chalkboard-teacher'},
    'professor_create': {'label': 'Adicionar Professor',        'url_name': 'professors:professor_create',    'icon': 'ph-user-plus'},
    'alloc_curricular': {'label': 'Alocação Curricular',        'url_name': 'alloc_curricular',               'icon': 'ph-git-branch'},
    'pendencia_list':   {'label': 'Pendências Extracurriculares','url_name': 'extra_curricular:pendencia_list','icon': 'ph-books'},
    'pendencia_create': {'label': 'Nova Pendência',             'url_name': 'extra_curricular:pendencia_create','icon': 'ph-note-pencil'},
    'janela_list':      {'label': 'Janelas de Entrega',         'url_name': 'core:janela_list',               'icon': 'ph-calendar'},
    'janela_create':    {'label': 'Nova Janela de Entrega',     'url_name': 'core:janela_create',             'icon': 'ph-calendar-plus'},
    'unidade_list':     {'label': 'Unidades',                   'url_name': 'core:unidade_list',              'icon': 'ph-buildings'},
    # "Adicionar Curso" aponta para a lista de unidades (cadastro de curso exige escolher a unidade).
    'adicionar_curso':  {'label': 'Adicionar Curso',            'url_name': 'core:unidade_list',              'icon': 'ph-graduation-cap'},
    'exportar_logs':    {'label': 'Exportar Logs',              'url_name': 'core:exportar_logs',             'icon': 'ph-download-simple'},
    'dashboard_desup':  {'label': 'Dashboard DESUP',            'url_name': 'dashboard_desup',                'icon': 'ph-gauge'},
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
