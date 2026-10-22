"""Conteúdo do tutorial guiado ("?") das páginas da DESUP e das unidades.

Cada entrada é indexada pelo nome da rota (`request.resolver_match.view_name`) e
alimenta o tutorial exibido por `apps.core.context_processors.ajuda_pagina`.
Ao criar ou alterar uma função da tela, atualize o passo correspondente.

Todo passo aponta para um elemento real da tela e, quando a função vive em um
popup, o tutorial abre esse popup de verdade e o fecha ao sair do passo:

- `alvo`: seletores CSS tentados em ordem (o primeiro visível é destacado). Um item
  `rota:<nome da url>` vira o link que aponta para essa rota.
- `abrir`: seletores clicados em sequência antes de destacar (abre popup, aba ou filtro).
- `fechar`: o que desfazer ao sair do passo. Um seletor simples esconde o popup;
  `clicar:<seletor>` clica no elemento; `alternar:<seletor>` clica só se ele estiver
  expandido (`aria-expanded="true"`).
- `requisito`: aviso exibido quando o destaque principal não existe na tela agora
  (ex.: ainda não há dados).
"""


def _passo(titulo, texto, alvo, abrir=(), fechar=(), requisito=''):
    return {
        'titulo': titulo,
        'texto': texto,
        'alvo': [alvo] if isinstance(alvo, str) else list(alvo),
        'abrir': [abrir] if isinstance(abrir, str) else list(abrir),
        'fechar': [fechar] if isinstance(fechar, str) else list(fechar),
        'requisito': requisito,
    }


_ABA_VISAO = 'clicar:.aba-btn[data-aba="visao"]'
_MODAL_ABERTO = ':not(.hidden) > div'

AJUDA_PAGINAS = {
    'dashboard_desup': {
        'titulo': 'Dashboard',
        'resumo': 'Visão institucional com a conformidade das unidades, a consulta de professores e os seus atalhos pessoais.',
        'funcionalidades': [
            'Acompanhar a conformidade geral e quantas unidades estão conformes ou com pendências.',
            'Consultar professores, com unidade, disciplinas e carga horária.',
            'Criar atalhos pessoais para as páginas que você mais usa.',
        ],
        'passos': [
            _passo('Leia os indicadores', 'Total de docentes, percentual de conformidade e unidades conformes. Passe o mouse em "Unidades Conformes" para ver quais têm pendências.',
                   ['[data-tour="dash-resumo"]']),
            _passo('Consulte um professor', 'Digite no campo "Buscar..." para localizar um docente na tabela e ver unidade, disciplinas e carga.',
                   ['input[placeholder^="Buscar"]', '#dashboard-professor-table']),
            _passo('Adicione atalhos', 'Clique em "Adicionar atalho", marque as páginas desejadas e confirme. Elas ficam no topo do dashboard.',
                   '#modalAddAtalho > div', abrir='button[onclick="abrirAdicionarAtalho()"]', fechar='#modalAddAtalho'),
            _passo('Remova um atalho', 'Use o ícone de remoção (X) sobre o atalho para retirá-lo diretamente do seu painel. Os atalhos são só seus e não afetam outros usuários.',
                   'button[title="Remover atalho"]',
                   requisito='Este passo aparece depois que você adicionar algum atalho.'),
        ],
    },
    'core:unidade_list': {
        'titulo': 'Unidades',
        'resumo': 'Cadastro das unidades de ensino que usam o sistema.',
        'funcionalidades': [
            'Ver o resumo de unidades ativas, inativas e cursos.',
            'Buscar unidades e filtrar por situação.',
            'Cadastrar e editar unidades e abrir os cursos de cada uma.',
        ],
        'passos': [
            _passo('Busque a unidade', 'Digite parte do nome ou da sigla para localizar uma unidade.', '#unidade-busca'),
            _passo('Filtre por situação', 'Mostre só as unidades ativas ou só as inativas.', '#unidade-status'),
            _passo('Cadastre uma unidade', 'Clique em "Adicionar Unidade", preencha nome e sigla e salve.', 'rota:core:unidade_create'),
            _passo('Abra os cursos', 'O botão "Cursos" leva aos cursos vinculados à unidade.', ['[data-tour="unidade-cursos"]', 'table']),
            _passo('Edite os dados', 'Use "Editar" para corrigir nome, sigla ou situação da unidade.', ['[data-tour="unidade-editar"]', 'table']),
        ],
    },
    'desup_user_list': {
        'titulo': 'Usuários',
        'resumo': 'Contas do sistema: criação de usuários e redefinição de senha.',
        'funcionalidades': [
            'Pesquisar contas por e-mail, nome ou unidade.',
            'Ver perfil, unidade, último acesso e status de cada conta.',
            'Criar usuários e redefinir a senha de quem perdeu o acesso.',
        ],
        'passos': [
            _passo('Pesquise a conta', 'Digite o e-mail, o nome ou a unidade no campo de busca.', 'input[placeholder^="E-mail, nome"]'),
            _passo('Confira os dados', 'Cada linha mostra perfil, unidade, último acesso e status da conta.', 'table'),
            _passo('Crie um usuário', 'Clique em "Criar usuário", informe os dados e o perfil e salve.', 'rota:desup_user_create'),
            _passo('Redefina a senha', 'Em "Redefinir senha", confirme na tela seguinte para gerar o acesso novo.',
                   ['a[href$="/redefinir-senha/"]', 'table'],
                   requisito='Este botão aparece na linha de cada conta.'),
        ],
    },
    'core:equipe_diretiva_desup': {
        'titulo': 'Equipe diretiva',
        'resumo': 'Cargos da equipe diretiva de cada unidade e a redução de carga horária de quem os ocupa.',
        'funcionalidades': [
            'Cadastrar, editar e excluir cargos da equipe diretiva.',
            'Registrar quem ocupa cada cargo em cada unidade.',
            'Informar e ajustar a redução de carga horária dos ocupantes.',
            'Consultar o histórico de ocupações.',
        ],
        'passos': [
            _passo('Escolha a unidade', 'Selecione a unidade para ver os cargos e a redução de carga dela.', '#equipe-unidade'),
            _passo('Veja a redução total', 'O total de horas semanais de redução da unidade aparece ao lado.',
                   ['[title="Redução total de carga horária da unidade"]', '#equipe-unidade'],
                   requisito='Escolha uma unidade para ver o total.'),
            _passo('Abra um cargo', 'Clique no cargo para ver os ocupantes, a redução de cada um e as ações.',
                   ['div[id^="modalDetalhe"]' + _MODAL_ABERTO, '#equipe-unidade'],
                   abrir='button[data-tour-ocupado] || button[onclick^="abrirModal(\'modalDetalhe"]', fechar='div[id^="modalDetalhe"]',
                   requisito='Escolha uma unidade para listar os cargos.'),
            _passo('Preencha o cargo', 'Em "Preencher cargo" ou "Adicionar ocupante", escolha o professor e informe as datas e a redução.',
                   ['div[id^="modalPreencher"]' + _MODAL_ABERTO, '#equipe-unidade'],
                   abrir=['button[data-tour-vago] || button[onclick^="abrirModal(\'modalDetalhe"]', 'div[id^="modalDetalhe"]:not(.hidden) button[onclick^="trocarModal"][class*="min-h-11"]'],
                   fechar=['div[id^="modalPreencher"]', 'div[id^="modalDetalhe"]'],
                   requisito='Escolha uma unidade; só cargos que aceitam novo ocupante têm este botão.'),
            _passo('Ajuste a redução', 'Mova a barra de 0 a 20 h ou use "Redução total" para marcar 20 h.',
                   ['div[id^="modalReducao"]' + _MODAL_ABERTO, '#equipe-unidade'],
                   abrir=['button[data-tour-ocupado]', 'div[id^="modalDetalhe"]:not(.hidden) button[title="Ajustar redução"]'],
                   fechar=['div[id^="modalReducao"]', 'div[id^="modalDetalhe"]'],
                   requisito='Este passo aparece quando um cargo já tem ocupante.'),
            _passo('Cadastre e exclua cargos', 'Use "Adicionar cargo" para criar. Para editar ou excluir, abra o cargo e clique no lápis; a exclusão remove também os ocupantes e o histórico.',
                   ['#modalNovoCargo > div', '#equipe-unidade'],
                   abrir='button[onclick="abrirModal(\'modalNovoCargo\')"]', fechar='#modalNovoCargo',
                   requisito='Escolha uma unidade para ver "Adicionar cargo".'),
            _passo('Consulte o histórico', 'Veja as ocupações anteriores e encerradas da unidade.',
                   ['#modalHistorico > div', '#equipe-unidade'],
                   abrir='button[onclick="abrirModal(\'modalHistorico\')"]', fechar='#modalHistorico',
                   requisito='O histórico aparece quando a unidade já teve ocupações.'),
        ],
    },
    'core:solicitacao_professor_list': {
        'titulo': 'Solicitações',
        'resumo': 'Pedidos das unidades para cadastrar um professor novo ou usar (ceder) professores de outras unidades.',
        'funcionalidades': [
            'Ver quantas solicitações estão pendentes, aprovadas e recusadas.',
            'Filtrar por situação, tipo (cessão ou cadastro) e unidade solicitante.',
            'Aprovar ou recusar cada pedido.',
        ],
        'passos': [
            _passo('Filtre os pedidos', 'Escolha a situação e a unidade solicitante; a lista se atualiza.', '#solicitacao-status'),
            _passo('Leia a lista', 'Cada linha mostra professor, origem e unidade solicitante, semestre, situação e data.', 'table'),
            _passo('Abra um pedido', 'Clique em "Decidir" para ver a justificativa e quem solicitou.',
                   ['div[id^="modalSolicitacao"]' + _MODAL_ABERTO, 'table'],
                   abrir='button[onclick^="abrirModal(\'modalSolicitacao"]', fechar='div[id^="modalSolicitacao"]',
                   requisito='Aparece quando houver solicitações na lista.'),
            _passo('Aprove ou recuse', 'Escolha a decisão e registre. A recusa exige motivo; a aprovação cria o novo vínculo sem remover os existentes e gera auditoria, notificação e e-mail.',
                   ['div[id^="modalSolicitacao"]:not(.hidden) form', 'table'],
                   abrir='button[onclick^="abrirModal(\'modalSolicitacao"]', fechar='div[id^="modalSolicitacao"]',
                   requisito='Aparece quando houver solicitações pendentes.'),
        ],
    },
    'core:alertas_carga_desup': {
        'titulo': 'Alertas e Limites de Carga',
        'resumo': 'Supervisão da carga horária dos professores e das disciplinas sem docente.',
        'funcionalidades': [
            'Ver quantas disciplinas estão sem professor e como os professores se situam em relação ao limite de carga.',
            'Abrir a lista por trás de cada número.',
            'Registrar readaptações de professores.',
            'Analisar pedidos de exceção de limite feitos pelas unidades.',
        ],
        'passos': [
            _passo('Filtre', 'Escolha unidade, curso, ano (semestre) e turno. Os números se atualizam ao escolher.', '#alertaFiltros'),
            _passo('Leia os cartões', 'Disciplinas sem professor, professores com horas livres, exatamente no limite e acima do limite.', '#alertaCartoes'),
            _passo('Abra uma lista', 'A seta de cada cartão abre a lista de disciplinas ou professores daquele número.',
                   '#modalDetalheDisciplinas > div', abrir='button[aria-labelledby="kpi-disciplinas"]', fechar='#modalDetalheDisciplinas'),
            _passo('Veja os pontos de atenção', 'Situações irregulares, como equipe diretiva dando aula. Clique no número para ver quem são.',
                   '#pontosLista', abrir='#pontosToggle', fechar='alternar:#pontosToggle'),
            _passo('Use a aba Readaptações', 'Lista os professores readaptados e permite editar ou encerrar a readaptação vigente.',
                   '[data-painel="readaptacoes"]', abrir='.aba-btn[data-aba="readaptacoes"]', fechar=_ABA_VISAO),
            _passo('Registre uma readaptação', 'Clique em "Registrar" para cadastrar um professor com restrição funcional.',
                   '#modalNovaReadaptacao > div',
                   abrir=['.aba-btn[data-aba="readaptacoes"]', 'button[onclick="abrirModal(\'modalNovaReadaptacao\')"]'],
                   fechar=['#modalNovaReadaptacao', _ABA_VISAO]),
            _passo('Use a aba Exceções', 'Pedidos das unidades para ultrapassar temporariamente o limite de carga.',
                   '[data-painel="excecoes"]', abrir='.aba-btn[data-aba="excecoes"]', fechar=_ABA_VISAO),
            _passo('Analise um pedido', 'Aprovar libera as horas adicionais durante a vigência; recusar exige motivo.',
                   ['div[id^="modalExcecao"]' + _MODAL_ABERTO, '[data-painel="excecoes"]'],
                   abrir=['.aba-btn[data-aba="excecoes"]', 'button[onclick^="abrirModal(\'modalExcecao"]'],
                   fechar=['div[id^="modalExcecao"]', _ABA_VISAO],
                   requisito='Aparece quando houver pedido de exceção.'),
        ],
    },
    'professors:professor_list': {
        'titulo': 'Professores',
        'resumo': 'Cadastro e consulta de professores, com vínculos e carga horária.',
        'funcionalidades': [
            'Ver o resumo de professores no sistema, ativos e afastados.',
            'Pesquisar por nome, ID funcional ou matrícula e filtrar por unidade, carga horária e cargo.',
            'Cadastrar e editar professores e abrir os detalhes de cada um.',
        ],
        'passos': [
            _passo('Pesquise', 'Digite nome, ID ou matrícula no campo de busca.', 'input[placeholder^="Nome, ID"]'),
            _passo('Refine com filtros', 'Filtre por unidade, carga horária e cargo; "Limpar" volta ao início.', 'form.filter-grid'),
            _passo('Abra os detalhes', 'Clique no nome do professor para ver unidades, contrato, disciplinas e carga.',
                   ['#professorDetailModal > div', 'table'], abrir='button[onclick="abrirDetalhesProfessor()"]', fechar='#professorDetailModal',
                   requisito='Aparece quando há professores na lista.'),
            _passo('Cadastre', 'Use "Novo Professor", preencha as abas do formulário e salve.', 'rota:professors:professor_create'),
            _passo('Edite', 'No detalhe do professor, use "Editar" para corrigir dados ou vínculos.',
                   ['#professorDetailContent a[href$="/editar/"]', '#professorDetailModal > div', 'table'],
                   abrir='button[onclick="abrirDetalhesProfessor()"]', fechar='#professorDetailModal',
                   requisito='Aparece quando há professores na lista.'),
        ],
    },
    'alloc_curricular': {
        'titulo': 'Alocação Curricular',
        'resumo': 'Distribuição de professores nas disciplinas das matrizes vigentes de cada unidade.',
        'funcionalidades': [
            'Escolher o docente de cada disciplina, ou declarar "Sem professor" (carência) ou "Não oferecido".',
            'Acrescentar mais de um docente por disciplina, com o botão "+".',
            'Informar a quantidade de turmas de cada disciplina.',
            'Aprovar a alocação da unidade, ou desfazer a aprovação.',
        ],
        'passos': [
            _passo('Escolha a unidade', 'Selecione a unidade; as matrizes vigentes dela aparecem em tabelas.', 'select[name="unidade_id"]'),
            _passo('Defina o docente', 'Clique no campo "Docente" e digite para buscar. A escolha é salva automaticamente.',
                   ['.ac-dropdown:not(.hidden)', '.ac-docente', 'select[name="unidade_id"]'],
                   abrir='.ac-docente .ac-input-wrap', fechar='clicar:body',
                   requisito='Escolha uma unidade para ver as disciplinas.'),
            _passo('Declare carência ou não oferta', 'No mesmo campo, escolha "Sem professor (carência)" ou "Não oferecido".',
                   ['.ac-dropdown:not(.hidden) .ac-fixed-options', '.ac-docente', 'select[name="unidade_id"]'],
                   abrir='.ac-docente .ac-input-wrap', fechar='clicar:body',
                   requisito='Escolha uma unidade para ver as disciplinas.'),
            _passo('Acrescente docentes', 'Clique em "+" para outra linha de docente ou carência na mesma disciplina.',
                   ['.ac-add', 'select[name="unidade_id"]'], requisito='Escolha uma unidade para ver as disciplinas.'),
            _passo('Informe as turmas', 'Na coluna "Turmas", digite só números (o padrão é 1) e confirme; o número por extenso aparece ao lado.',
                   ['.ac-turmas-input', 'select[name="unidade_id"]'], requisito='Escolha uma unidade para ver as disciplinas.'),
            _passo('Aprove', 'Quando não houver pendências, clique em "Aprovar Alocação". "Desfazer aprovação" volta a permitir edição.',
                   ['#approveAllocBtn', 'select[name="unidade_id"]'], requisito='Escolha uma unidade para ver o botão de aprovação.'),
        ],
    },
    'extra_curricular:pendencia_list': {
        'titulo': 'Extracurriculares',
        'resumo': 'Justificativas de carga horária extracurricular (TCC, extensão e redução) dos professores.',
        'funcionalidades': [
            'Alternar entre as justificativas pendentes, reprovadas e aprovadas.',
            'Aprovar ou reprovar cada justificativa diretamente na visão geral.',
            'Filtrar por semestre, unidade e tipo, e buscar por docente.',
        ],
        'passos': [
            _passo('Pesquise nesta aba', 'A pesquisa consulta docente, ID, processo SEI, justificativa, status, unidade e valores de carga horária.',
                   '#search-extracurricular'),
            _passo('Use os filtros', 'Abra o modal para escolher semestre, unidade e tipo de justificativa.',
                   '#modalFiltrosExtracurriculares .extra-filter-modal-panel',
                   abrir='[data-extra-filter-open]', fechar='#modalFiltrosExtracurriculares'),
            _passo('Navegue pelos pareceres', 'Use as abas Pendentes, Reprovados e Aprovados para acompanhar cada grupo.',
                   ['.extra-tabs', '#pendencias-content']),
            _passo('Dê o parecer', 'Na própria linha, selecione Aprovado ou Reprovado, informe a justificativa e salve. A justificativa é obrigatória na reprovação.',
                   ['.desup-decision-form', '#pendencias-table', '#pendencias-content'],
                   requisito='Aparece quando houver justificativas na lista.'),
        ],
    },
    'courses:matrix_list': {
        'titulo': 'Matrizes',
        'resumo': 'Matrizes curriculares dos cursos: vigentes, rascunhos e histórico.',
        'funcionalidades': [
            'Ver o resumo de matrizes vigentes, rascunhos e histórico.',
            'Pesquisar por matriz, curso ou unidade e filtrar por status.',
            'Criar, editar e arquivar matrizes.',
        ],
        'passos': [
            _passo('Pesquise', 'Digite matriz, curso ou unidade no campo de pesquisa.',
                   ['input[placeholder^="Matriz, curso"]', '#matrix-secondary-filters'],
                   abrir='#matrix-secondary-filters:not([open]) > summary', fechar='clicar:#matrix-secondary-filters[open] > summary'),
            _passo('Filtre por status', 'Mostre só vigentes, rascunhos ou o histórico (anteriores).',
                   ['select[name="status"]', '#matrix-secondary-filters'],
                   abrir='#matrix-secondary-filters:not([open]) > summary', fechar='clicar:#matrix-secondary-filters[open] > summary'),
            _passo('Crie uma matriz', 'Clique em "Nova Matriz", informe curso, turno e unidades e adicione as disciplinas.', 'rota:courses:matrix_create'),
            _passo('Edite', 'Use "Editar Vigente" ou "Editar Rascunho" conforme o estado da matriz.',
                   ['a[href$="/edit/"]', 'table'], requisito='Aparece na linha de cada matriz.'),
            _passo('Arquive', 'Em uma matriz vigente, "Arquivar" a tira de Vigentes e a envia ao Histórico.',
                   ['form[action$="/arquivar/"] button', 'table'], requisito='Aparece nas matrizes vigentes.'),
        ],
    },
    'courses:component_list': {
        'titulo': 'Componentes',
        'resumo': 'Catálogo de componentes curriculares (disciplinas) usados nas matrizes.',
        'funcionalidades': [
            'Pesquisar por nome ou código.',
            'Cadastrar, editar e importar componentes por planilha.',
        ],
        'passos': [
            _passo('Pesquise', 'Digite o nome ou o código e clique em "Filtrar".', '#cc-filter-form'),
            _passo('Cadastre', 'Use "Novo Componente" e informe nome, código, carga horária e créditos.', 'rota:courses:component_create'),
            _passo('Importe em massa', 'Use "Importar Planilha" e envie o arquivo no modelo indicado.', 'rota:courses:component_import'),
            _passo('Edite', 'Clique em "Editar" na linha do componente para corrigir os dados.',
                   ['table a[href*="/editar/"]', 'table a[href*="/componentes/"]', 'table']),
        ],
    },
    'core:janela_list': {
        'titulo': 'Entrega',
        'resumo': 'Janelas de entrega: períodos em que as unidades podem alterar matrizes e alocações.',
        'funcionalidades': [
            'Abrir, fechar e reabrir janelas para todas as unidades ou para uma unidade específica.',
            'Pesquisar por semestre, unidade ou status.',
        ],
        'passos': [
            _passo('Pesquise', 'Filtre por semestre, unidade ou status.', 'form.filter-grid'),
            _passo('Consulte as janelas', 'Veja semestre, período, unidade e status (aberta, fechada ou reaberta).', 'table'),
            _passo('Crie uma janela', 'Clique em "Nova Janela", informe semestre e datas e, se quiser, a unidade.', 'rota:core:janela_create'),
            _passo('Reabra ou ajuste', 'Edite a janela para reabri-la, por exemplo após um chamado, ou para mudar as datas.',
                   ['table a[href$="/editar/"]', 'table']),
            _passo('Entenda o bloqueio', 'Fora de uma janela aberta, as unidades não conseguem alterar dados; a DESUP continua podendo.', 'table'),
        ],
    },
}


# O coordenador trabalha em algumas das mesmas URLs da DESUP, mas com ações e
# permissões diferentes. Manter um catálogo próprio evita orientar a unidade a
# usar botões que ela não possui (por exemplo, criar professor ou aprovar a
# alocação em nome da DESUP).
AJUDA_PAGINAS_COORDENADOR = {
    'dashboard_unidade': {
        'titulo': 'Dashboard da Unidade',
        'resumo': 'Página inicial da unidade, com identificação do vínculo e atalhos personalizados.',
        'funcionalidades': [
            'Confirmar a unidade vinculada ao seu acesso.',
            'Abrir rapidamente as páginas mais usadas.',
            'Adicionar ou remover atalhos pessoais.',
        ],
        'passos': [
            _passo('Confira a unidade', 'Este cartão identifica a unidade vinculada ao seu usuário.', '.dash-hero'),
            _passo('Use os atalhos', 'Os atalhos levam diretamente às áreas que você usa com mais frequência.', '[aria-labelledby="atalhos-unidade-titulo"]'),
            _passo('Adicione atalhos', 'Clique em "Adicionar atalho", selecione as páginas desejadas e salve.',
                   '#modalAddAtalho > div', abrir='button[onclick="abrirAdicionarAtalho()"]', fechar='#modalAddAtalho'),
            _passo('Remova um atalho', 'Use o ícone de remoção (X) para retirar um atalho diretamente do seu painel.',
                   'button[title="Remover atalho"]',
                   requisito='Este passo aparece quando já existe algum atalho salvo.'),
        ],
    },
    'core:equipe_diretiva_unidade': {
        'titulo': 'Equipe Diretiva e Coordenações',
        'resumo': 'Composição da equipe da unidade, ocupantes dos cargos, vigências e histórico.',
        'funcionalidades': [
            'Consultar a redução total definida pela DESUP.',
            'Preencher vagas e atualizar ocupações da própria unidade.',
            'Identificar integrantes que também estão alocados em sala.',
            'Pesquisar ocupações vigentes e encerradas.',
        ],
        'passos': [
            _passo('Confira a redução', 'A redução semanal total é calculada com os valores definidos pela DESUP.',
                   '[title^="Redução total semanal"]'),
            _passo('Veja a composição', 'Cada cartão representa um cargo e informa se ele está preenchido ou vago.',
                   '[aria-labelledby="sec-composicao-titulo"]'),
            _passo('Abra um cargo', 'Clique no cargo para consultar ocupantes, datas e ações disponíveis.',
                   ['div[id^="modalDetalheUnidade"]' + _MODAL_ABERTO, '[aria-labelledby="sec-composicao-titulo"]'],
                   abrir='button[onclick^="abrirModal(\'modalDetalheUnidade"]', fechar='div[id^="modalDetalheUnidade"]',
                   requisito='Este passo aparece quando há cargos cadastrados pela DESUP.'),
            _passo('Preencha uma vaga', 'No detalhe do cargo, use "Preencher cargo" ou "Adicionar ocupante" e informe a vigência.',
                   ['div[id^="modalPreencherUnidade"]' + _MODAL_ABERTO, '[aria-labelledby="sec-composicao-titulo"]'],
                   abrir=['button[onclick^="abrirModal(\'modalDetalheUnidade"]', 'div[id^="modalDetalheUnidade"]:not(.hidden) button[onclick*="modalPreencherUnidade"]'],
                   fechar=['div[id^="modalPreencherUnidade"]', 'div[id^="modalDetalheUnidade"]'],
                   requisito='A ação aparece quando o cargo aceita um novo ocupante.'),
            _passo('Consulte o histórico', 'Busque por servidor, cargo ou curso e filtre entre ocupações vigentes e encerradas.',
                   ['#filtro-busca-historico', '#historico-equipe-unidade-container']),
        ],
    },
    'professors:professor_list': {
        'titulo': 'Professores',
        'resumo': 'Consulta dos professores vinculados à unidade e solicitação de novos vínculos.',
        'funcionalidades': [
            'Pesquisar professores e consultar contrato, vínculos e carga horária.',
            'Solicitar o cadastro de um professor que ainda não está no sistema.',
            'Solicitar a atuação de um professor pertencente a outra unidade.',
        ],
        'passos': [
            _passo('Pesquise', 'Digite nome, ID funcional ou matrícula para localizar um professor.', 'input[placeholder^="Nome, ID"]'),
            _passo('Refine com filtros', 'Use os filtros de carga horária e cargo para reduzir a lista.', 'form.filter-grid'),
            _passo('Leia a situação', 'A tabela mostra contrato, unidades, carga total, horas ainda não alocadas e percentual alocado.', 'table'),
            _passo('Solicite um cadastro', 'Use "Solicitar Cadastro de Professor" quando o docente ainda não existir no sistema.',
                   'rota:professors:professor_solicitar_cadastro'),
            _passo('Solicite uma cessão', 'Use "Solicitar Professor de Outra Unidade" para pedir um vínculo adicional.',
                   'rota:professors:professor_solicitar_cessao'),
        ],
    },
    'alloc_curricular': {
        'titulo': 'Alocação Curricular',
        'resumo': 'Distribuição dos professores nas disciplinas das matrizes vigentes da unidade.',
        'funcionalidades': [
            'Definir o docente de cada disciplina ou registrar carência e não oferta.',
            'Acrescentar mais de um docente por disciplina.',
            'Informar a quantidade de turmas e salvar a alocação da unidade.',
        ],
        'passos': [
            _passo('Confira a unidade', 'A alocação exibida pertence à unidade vinculada ao seu acesso.', '.filter-grid'),
            _passo('Defina o docente', 'Clique no campo "Docente" e digite para buscar. A escolha é registrada na linha.',
                   ['.ac-dropdown:not(.hidden)', '.ac-docente', 'table'], abrir='.ac-docente .ac-input-wrap', fechar='clicar:body',
                   requisito='Este passo aparece quando há uma matriz vigente com disciplinas.'),
            _passo('Registre carência ou não oferta', 'No mesmo campo, escolha "Sem professor" ou "Não oferecido" quando for o caso.',
                   ['.ac-dropdown:not(.hidden) .ac-fixed-options', '.ac-docente', 'table'], abrir='.ac-docente .ac-input-wrap', fechar='clicar:body',
                   requisito='Este passo aparece quando há disciplinas para alocar.'),
            _passo('Acrescente docentes', 'Use o botão "+" para adicionar outro docente à mesma disciplina.',
                   ['.ac-add', 'table'], requisito='Este botão aparece nas linhas de disciplinas.'),
            _passo('Informe as turmas', 'Na coluna "Turmas", informe a quantidade ofertada para calcular corretamente a carga.',
                   ['.ac-turmas-input', 'table'], requisito='Este campo aparece nas linhas de disciplinas.'),
            _passo('Salve a alocação', 'Depois de revisar as linhas, clique em "Salvar Alocações".',
                   ['#saveAllocBtn', 'table'], requisito='O botão fica disponível durante uma janela de entrega aberta.'),
        ],
    },
    'extra_curricular:pendencia_list': {
        'titulo': 'Extracurriculares',
        'resumo': 'Pendências, rascunhos e justificativas de carga horária extracurricular da unidade.',
        'funcionalidades': [
            'Alternar entre visão geral, rascunhos, justificativas e supervisão de estágio.',
            'Pesquisar docentes e filtrar os registros do semestre.',
            'Criar justificativas e continuar os rascunhos antes do envio.',
        ],
        'passos': [
            _passo('Navegue pelas abas', 'Use as abas para abrir pendências, rascunhos, justificativas enviadas e supervisão de estágio.', '.extra-tabs'),
            _passo('Pesquise nesta aba', 'A pesquisa consulta docente, ID, processo SEI, justificativa, status e valores de carga horária.',
                   '#search-extracurricular'),
            _passo('Use os filtros', 'Abra o modal para escolher semestre, status e tipo de justificativa.',
                   '#modalFiltrosExtracurriculares .extra-filter-modal-panel',
                   abrir='[data-extra-filter-open]', fechar='#modalFiltrosExtracurriculares'),
            _passo('Crie uma justificativa', 'Clique em "Nova justificativa" para registrar as atividades extracurriculares dos docentes.',
                   ['a.extra-action', '.extra-section-card']),
            _passo('Continue os rascunhos', 'Abra a aba "Rascunhos" para continuar registros ainda não enviados.',
                   '.extra-tab-card[href*="aba=rascunhos"]'),
            _passo('Acompanhe o resultado', 'Na aba "Justificativas", consulte os registros enviados e o status da análise.',
                   '.extra-tab-card[href*="aba=justificativas"]'),
        ],
    },
    'extra_curricular:supervisao_estagio': {
        'titulo': 'Supervisão de Estágio',
        'resumo': 'Cadastro das atividades de coordenação, supervisão e orientação de estágio da unidade.',
        'funcionalidades': [
            'Registrar o docente responsável e a quantidade de supervisionados.',
            'Usar o semestre letivo preenchido automaticamente.',
            'Editar ou encerrar atividades já registradas.',
        ],
        'passos': [
            _passo('Navegue pelo módulo', 'As abas mantêm pendências, justificativas e supervisão dentro do mesmo módulo.', '.extra-tabs'),
            _passo('Registre uma atividade', 'Clique em "Registrar estágio / supervisão" para abrir o formulário.',
                   '#modalNovoEstagio .estagio-modal-panel', abrir='button[onclick="abrirModal(\'modalNovoEstagio\')"]', fechar='#modalNovoEstagio'),
            _passo('Confira o semestre', 'O semestre letivo é definido automaticamente conforme a data atual.',
                   ['#modalNovoEstagio input[name="semestre"]', '#modalNovoEstagio .estagio-modal-body'],
                   abrir='button[onclick="abrirModal(\'modalNovoEstagio\')"]', fechar='#modalNovoEstagio'),
            _passo('Gerencie os registros', 'Use "Editar" para atualizar a atividade ou "Encerrar" quando ela deixar de vigorar.',
                   ['button[onclick^="abrirModal(\'modalEditarEstagio"]', '#estagio-section-title'],
                   requisito='As ações aparecem depois que uma atividade é cadastrada.'),
        ],
    },
    'courses:matrix_list': {
        'titulo': 'Matrizes Curriculares',
        'resumo': 'Consulta das matrizes curriculares relacionadas aos cursos da unidade.',
        'funcionalidades': [
            'Pesquisar matrizes e filtrar por curso, situação e turno.',
            'Consultar componentes, carga horária total e vigência.',
            'Abrir a matriz e editar rascunhos quando disponíveis.',
        ],
        'passos': [
            _passo('Abra os filtros', 'Expanda "Filtros e pesquisa" para localizar uma matriz por curso, situação ou turno.',
                   ['#matrix-secondary-filters', '#matrix-filter-form'], abrir='#matrix-secondary-filters:not([open]) > summary',
                   fechar='clicar:#matrix-secondary-filters[open] > summary'),
            _passo('Consulte a lista', 'A tabela mostra curso, turno, código, quantidade de componentes, carga total e status.', 'table'),
            _passo('Abra a matriz', 'Clique no curso, turno ou código para consultar os componentes curriculares.',
                   ['table td[onclick]', 'table'], requisito='Aparece quando há matrizes cadastradas para a unidade.'),
            _passo('Edite um rascunho', 'Quando houver uma matriz em rascunho, use "Editar Rascunho" para continuar o preenchimento.',
                   ['a[href$="/edit/"]', 'table'], requisito='A ação aparece somente nas matrizes em rascunho.'),
        ],
    },
}


def resolver_alvo(seletor):
    """Converte "rota:<nome>" no seletor do link correspondente; outros valores passam direto."""
    if not seletor.startswith('rota:'):
        return seletor
    from django.urls import NoReverseMatch, reverse

    try:
        return 'a[href^="%s"]' % reverse(seletor[len('rota:'):])
    except NoReverseMatch:
        return ''


def passos_resolvidos(conteudo):
    """Passos com os alvos "rota:" já convertidos em seletores (usado pelo context processor)."""
    resolvidos = []
    for passo in conteudo['passos']:
        alvo = [s for s in (resolver_alvo(item) for item in passo['alvo']) if s]
        resolvidos.append({**passo, 'alvo': alvo})
    return resolvidos
