# Relatório de modificações

## 16/10/2026 — Criação dos prompts de evolução do Harpia DESUP

### `prompts_alteracoes_harpia.md`
- Tipo: criado.
- Alteração: criação de um conjunto de quatorze prompts para auditoria, implementação e validação das melhorias descritas no plano de evolução do Harpia DESUP.
- Motivo: dividir o trabalho em etapas verificáveis e incorporar, em todas elas, requisitos de responsividade, segurança, norma-padrão da língua portuguesa, acessibilidade, testes e rastreabilidade.
- Escopo: documentação de trabalho; nenhum comportamento da aplicação foi alterado.

### `relatoriodemodificações.md`
- Tipo: criado.
- Alteração: criação do histórico de modificações, com data e blocos separados por arquivo.
- Motivo: atender ao requisito de registrar continuamente os arquivos criados, alterados ou removidos.

### Verificações
- Leitura do PDF `HARPIA DESUP .pdf`: concluída; as três prioridades e seus requisitos foram contemplados nos prompts.
- Inspeção da arquitetura do repositório: concluída; os prompts foram associados aos aplicativos e estruturas Django existentes.
- Verificação de alterações funcionais: não aplicável; nesta etapa foram criados somente arquivos Markdown de planejamento e rastreabilidade.

## 16/10/2026 — Versão do plano separada por responsabilidade

### `output/pdf/plano_evolucao_harpia_desup_responsabilidades.pdf`
- Tipo: criado.
- Alteração: criação de uma versão reorganizada do plano de evolução, mantendo a ordem das prioridades e separando, em cada item, as modificações e responsabilidades da DESUP e da unidade.
- Motivo: tornar explícito quem configura, supervisiona, solicita, executa e acompanha cada alteração prevista no sistema.
- Escopo: documento de planejamento com oito páginas, princípios gerais, três prioridades, pontos de atenção e síntese final.

### `relatoriodemodificações.md`
- Tipo: alterado.
- Alteração: inclusão do registro da criação e da verificação do novo PDF.
- Motivo: manter o histórico dos arquivos produzidos em blocos separados.

### Verificações
- Estrutura do PDF: oito páginas A4, sem criptografia e sem JavaScript incorporado.
- Revisão visual: todas as páginas foram renderizadas e inspecionadas; não foram encontrados cortes, sobreposições, caracteres ausentes ou problemas de legibilidade na versão final.
- Conteúdo: as prioridades 1, 2 e 3 permanecem na ordem original, com responsabilidades específicas para DESUP e unidade.
- Revisão textual: concluída conforme a norma-padrão do português brasileiro.

## 16/10/2026 — Distribuição das tarefas entre Esther e Jefferson

### `distribuicao_tarefas_harpia_esther_jefferson.txt`
- Tipo: criado.
- Alteração: criação de um documento em texto simples que atribui a Esther todas as atividades da DESUP e a Jefferson todas as atividades das unidades, preservando a ordem das prioridades do plano de evolução.
- Motivo: disponibilizar um material direto e pronto para encaminhamento aos responsáveis pela implementação.
- Escopo: responsabilidades individuais, pontos de integração, ordem de execução e critérios de conclusão.

### `relatoriodemodificações.md`
- Tipo: alterado.
- Alteração: inclusão do registro da criação do documento de distribuição de tarefas.
- Motivo: manter o histórico dos arquivos produzidos em blocos separados.

### Verificações
- Estrutura: as prioridades 1, 2 e 3 foram mantidas na ordem original.
- Responsáveis: todas as atividades da DESUP foram atribuídas a Esther e todas as atividades das unidades foram atribuídas a Jefferson.
- Revisão textual: concluída conforme a norma-padrão do português brasileiro.

## 16/10/2026 — Implementação da Prioridade 1 sob responsabilidade de Esther (DESUP)

### `project_root/apps/core/models.py`
- Tipo: alterado.
- Alteração: inclusão dos modelos de tipos de cargo, ocupações da equipe diretiva, solicitações de professor externo, limites de carga por unidade, exceções de carga e readaptações, com vigência, histórico, validações e restrições de integridade.
- Segurança: vínculos incompatíveis, períodos inválidos, sobreposições e relações entre unidades são validados no servidor; as exclusões usam proteção referencial.

### `project_root/apps/core/forms.py`
- Tipo: alterado.
- Alteração: criação dos formulários administrativos da Prioridade 1 e dos formulários de decisão de solicitações e exceções.
- Segurança: o ajuste de ocupação expõe à DESUP somente redução e observações; o motivo é obrigatório em recusas.

### `project_root/apps/core/services.py`
- Tipo: alterado.
- Alteração: criação dos serviços transacionais de aprovação e recusa, efetivação de vínculo externo, envio de notificação e e-mail e registro de auditoria.
- Segurança: decisões usam bloqueio transacional, só aceitam estados previstos e são restritas à DESUP ou ao grupo institucional correspondente.

### `project_root/apps/core/priority1.py`
- Tipo: criado.
- Alteração: implementação da consulta consolidada dos indicadores da Prioridade 1, com filtros institucionais e prevenção de dupla contagem por vínculo múltiplo ou componente compartilhado.
- Escopo: calcula carências, cargas, saldos, excessos, funções diretivas em sala, readaptações, origem no Ensino Médio, solicitações, exceções e limites das unidades.

### `project_root/apps/core/views.py`
- Tipo: alterado.
- Alteração: integração do resumo ao dashboard e criação das telas exclusivas da DESUP para equipe diretiva, solicitações externas, limites, readaptações e exceções.
- Segurança: todas as novas rotas exigem autenticação e perfil DESUP no servidor; operações mutáveis aceitam somente POST.

### `project_root/apps/core/urls.py`
- Tipo: alterado.
- Alteração: inclusão das rotas nomeadas dos módulos da Prioridade 1 da DESUP.
- Segurança: as URLs apontam para views com autorização explícita e não expõem operações mutáveis por GET.

### `project_root/apps/core/admin.py`
- Tipo: alterado.
- Alteração: registro dos novos modelos para suporte técnico e inspeção administrativa, com filtros, pesquisas e campos históricos somente para leitura.

### `project_root/apps/core/atalhos.py`
- Tipo: alterado.
- Alteração: inclusão dos atalhos de equipe diretiva, solicitações externas e alertas de carga na lista permitida exclusivamente à DESUP.

### `project_root/apps/core/migrations/0005_tipocargodiretivo_excecaocargaunidade_and_more.py`
- Tipo: criado.
- Alteração: criação das tabelas, índices, chaves estrangeiras e restrições da Prioridade 1.
- Banco de dados: esta migração deve ser aplicada no PostgreSQL do Supabase antes da disponibilização das novas telas.

### `project_root/apps/core/migrations/0006_cargos_diretivos_iniciais.py`
- Tipo: criado.
- Alteração: carga inicial segura dos cargos Diretor(a), Vice-Diretor(a), Secretário(a), Coordenação de Curso, Coordenação de Pesquisa e Extensão e Coordenação de Estágio.
- Integridade: a reversão preserva registros administrativos para evitar exclusão destrutiva de cargos já referenciados.

### `project_root/apps/core/tests_prioridade1_desup.py`
- Tipo: criado.
- Alteração: inclusão de testes de autorização, sobreposição de vigências, limite por unidade, decisão única, auditoria, notificação, vínculo externo, motivo de recusa e saldo sem alocação.

### `project_root/apps/professors/models.py`
- Tipo: alterado.
- Alteração: inclusão do nível de ensino de origem do professor, necessário para o alerta institucional de atuação do Ensino Médio no Ensino Superior.

### `project_root/apps/professors/forms.py`
- Tipo: alterado.
- Alteração: inclusão do nível de ensino de origem no cadastro institucional, com edição bloqueada para coordenadores de unidade e compatibilidade com formulários antigos que omitam o campo.

### `project_root/apps/professors/migrations/0011_professor_nivel_ensino_origem.py`
- Tipo: criado.
- Alteração: adição do campo indexado `nivel_ensino_origem`, com valor inicial seguro “Não informado”.
- Banco de dados: esta migração também deve ser aplicada no PostgreSQL do Supabase.

### `project_root/templates/base.html`
- Tipo: alterado.
- Alteração: inclusão, no menu da DESUP, dos acessos à equipe diretiva, às solicitações externas e aos alertas de carga.

### `project_root/templates/dashboard/desup.html`
- Tipo: alterado.
- Alteração: criação dos filtros institucionais por unidade, semestre, curso, turno e situação, além de cartões de alertas e links para os módulos da Prioridade 1.
- Responsividade e acessibilidade: os controles se reorganizam por largura, mantêm área mínima para toque e possuem rótulos associados.

### `project_root/templates/professors/professor_form.html`
- Tipo: alterado.
- Alteração: inclusão do campo e da explicação do nível de ensino de origem na área institucional do cadastro.

### `project_root/templates/core/prioridade1/form.html`
- Tipo: criado.
- Alteração: formulário responsivo compartilhado pelas configurações da Prioridade 1, com erros por campo, proteção CSRF, foco visível e ações adequadas para toque.

### `project_root/templates/core/prioridade1/equipe_diretiva.html`
- Tipo: criado.
- Alteração: painel global de cargos e ocupações diretivas, com filtros, histórico e ajuste da carga de redução. O cadastro de ocupantes e o encerramento permanecem reservados à futura etapa de Jefferson.
- Responsividade: cartões se reorganizam por largura e a tabela utiliza rolagem horizontal controlada e rótulos de célula.

### `project_root/templates/core/prioridade1/solicitacoes_professor.html`
- Tipo: criado.
- Alteração: fila paginada de solicitações externas com filtros e decisão fundamentada da DESUP.
- Responsividade e acessibilidade: cada solicitação é apresentada como cartão adaptável, com rótulos associados aos campos de decisão.

### `project_root/templates/core/prioridade1/alertas_carga.html`
- Tipo: criado.
- Alteração: painel de indicadores, limites por unidade, readaptações, exceções pendentes e alertas administrativos.
- Responsividade: indicadores, formulários e listas utilizam grades progressivas para celular, tablet e computador.

### `project_root/static/css/tailwind.min.css`
- Tipo: alterado.
- Alteração: recompilação do Tailwind CSS para incorporar as classes utilizadas nas novas interfaces responsivas.

### `relatoriodemodificações.md`
- Tipo: alterado.
- Alteração: inclusão deste registro detalhado, mantendo um bloco separado para cada arquivo criado ou modificado.

### Pendência administrativa documentada
- As regras legais definitivas de readaptação e de atuação de profissionais oriundos do Ensino Médio no Ensino Superior ainda dependem de validação da área competente. Esta etapa da DESUP registra e sinaliza esses casos sem inventar critérios legais adicionais; o bloqueio operacional na alocação pertence às tarefas de Jefferson.
- A DESUP ainda deve formalizar quais perfis da unidade poderão nomear, substituir e encerrar ocupações. Por isso, esta etapa não abriu essas operações às unidades nem atribuiu permissões por suposição.

### Implantação no Supabase
- Há alteração obrigatória de banco de dados.
- Aplicar, na ordem, as migrações `professors.0011`, `core.0005` e `core.0006` por meio do processo de implantação do Django (`python manage.py migrate`).
- Não executar manualmente o SQL de referência presente no arquivo de prompts; a fonte correta das alterações são as migrações versionadas.

### Verificações executadas
- `python manage.py check --settings=config.settings._tmp_test`: aprovado, sem problemas.
- `python manage.py makemigrations --check --dry-run --settings=config.settings.development`: aprovado, sem alterações pendentes.
- `python manage.py test apps.core.tests_prioridade1_desup --settings=config.settings._tmp_test`: aprovado; sete testes específicos da Prioridade 1.
- Testes de compatibilidade do cadastro de professores: aprovados; 22 testes.
- `python manage.py test --settings=config.settings._tmp_test`: executados 631 testes; 7 falhas, 3 erros e 16 ignorados. As ocorrências remanescentes pertencem a expectativas legadas já divergentes do código atual, incluindo o campo removido `limite_horas_extra`, o escopo histórico do gerenciador de professores e textos antigos de confirmação de senha. Nenhum teste foi removido ou enfraquecido.
- `npm run build:css`: aprovado.
- `npm audit --omit=dev`: nenhuma vulnerabilidade de dependência de produção encontrada. O instalador informou avisos apenas na cadeia de ferramentas de desenvolvimento; uma nova consulta completa foi impedida temporariamente por indisponibilidade de rede do registro npm.
- `git diff --check`: aprovado, sem erros de espaços em branco.

## 16/10/2026 — Script SQL da Prioridade 1 para o Supabase

### `project_root/sql/supabase_prioridade1_desup.sql`
- Tipo: criado.
- Alteração: criação do script transacional PostgreSQL equivalente às migrations `professors.0011`, `core.0005` e `core.0006`, destinado à execução pelo SQL Editor do Supabase quando o processo normal `python manage.py migrate` não estiver disponível.
- Banco de dados: adiciona o nível de ensino de origem ao professor, cria as seis tabelas administrativas da Prioridade 1, seus índices, restrições e chaves estrangeiras, cadastra os seis cargos iniciais e registra as migrations na tabela `django_migrations`.
- Segurança: valida os pré-requisitos e interrompe uma implantação parcial; aplica limite de tempo, executa tudo em uma transação, habilita RLS nas novas tabelas e revoga o acesso direto dos papéis `anon` e `authenticated`.
- Observação: o script é uma alternativa às migrations do Django. Não deve ser executado se essas migrations já tiverem sido aplicadas.

### `relatoriodemodificações.md`
- Tipo: alterado.
- Alteração: inclusão do registro do script SQL fornecido para a implantação da Prioridade 1 no Supabase.
- Motivo: manter a rastreabilidade por arquivo e registrar explicitamente as alterações previstas no banco de dados.

## 16/10/2026 — Equipe diretiva por unidade e reorganização da supervisão de carga (Esther, DESUP)

### `project_root/templates/core/prioridade1/equipe_diretiva.html`
- Tipo: alterado.
- Alteração: tela reorganizada em torno da unidade selecionada. Mostra a composição da equipe diretiva (um cartão por cargo, com ocupantes vigentes ou "Vago"), a redução de carga por ocupante e a redução total da unidade. Preenchimento de cargo, ajuste de redução e gestão dos tipos de cargo (novo/editar, com ícones) passam a ocorrer em modais; o histórico de ocupações fica recolhido.
- Motivo: permitir que a DESUP preencha os cargos de cada unidade e registre a redução de carga sem sair da tela.

### `project_root/templates/core/prioridade1/alertas_carga.html`
- Tipo: alterado.
- Alteração: tela dividida em abas (Visão geral, Teto por unidade, Readaptações, Exceções), com textos explicativos, barra de uso do teto por unidade, filtros com envio automático e todos os formulários (teto, readaptação, encerramento e decisão de exceção) em modais.
- Motivo: a tela anterior apresentava todos os blocos ao mesmo tempo e não explicava o significado de limite e readaptação.

### `project_root/templates/core/prioridade1/_modal_form.html` e `_campos_form.html`
- Tipo: criados.
- Alteração: modal genérico com formulário e renderização padronizada de campos, reutilizados pelas telas acima.

### `project_root/templates/core/prioridade1/form.html`, `solicitacoes_professor.html`
- Tipo: alterados.
- Alteração: remoção do rótulo "Prioridade 1" das telas; o formulário de página inteira preserva o parâmetro `next` quando há erro de validação.

### `project_root/apps/core/views.py`
- Tipo: alterado.
- Alteração: nova `OcupacaoEquipeDiretivaCreateView` (preencher cargo de uma unidade), mixin `RetornoOrigemMixin` (redireciona para a origem validada após salvar em modal), composição por cargo e redução total no contexto da equipe diretiva, carga atual × teto por unidade e formulários dos modais no contexto de alertas.

### `project_root/apps/core/forms.py`
- Tipo: alterado.
- Alteração: `OcupacaoEquipeDiretivaForm` (servidores e cursos restritos à unidade), `ReadaptacaoProfessorEdicaoForm` (edição sem troca de professor), rótulos e textos de ajuda de teto e readaptação.

### `project_root/apps/core/priority1.py`
- Tipo: alterado.
- Alteração: o resumo passa a retornar a carga alocada e as horas adicionais aprovadas por unidade.

### `project_root/apps/core/urls.py`
- Tipo: alterado.
- Alteração: rota `ocupacao_diretiva_create`.

### `project_root/apps/core/tests_prioridade1_desup.py`
- Tipo: alterado.
- Alteração: testes de preenchimento de cargo, bloqueio de servidor de outra unidade, renderização dos modais de alertas e edição de readaptação com retorno à origem.
- Verificação: `python manage.py test apps.core.tests_prioridade1_desup --settings=config.settings._tmp_test` (com `DATABASE_URL` SQLite): aprovado, 11 testes.

### `project_root/static/css/tailwind.min.css`
- Tipo: alterado.
- Alteração: recompilado com `npm run build:css` para incluir as classes novas.

### `project_root/apps/core/management/commands/seed_dados_teste.py`
- Tipo: criado.
- Alteração: comando `python manage.py seed_dados_teste`, idempotente e restrito a `DEBUG=True`, que cria 5 unidades, 7 cursos vinculados às unidades, 36 professores distribuídos entre as unidades e os tipos de contrato, equipe diretiva parcial em duas unidades, tetos de carga, uma readaptação e uma exceção pendente. Todos os registros usam o prefixo/sufixo "TESTE".
- Motivo: permitir testar localmente as telas de equipe diretiva, alertas de carga e consulta de professores.
- Verificação: executado duas vezes no `local.sqlite3` sem gerar duplicidades; telas renderizadas com os dados.

## 16/10/2026 — Ajustes de layout: equipe diretiva, alertas, dashboard e selects

### `project_root/templates/core/prioridade1/equipe_diretiva.html` e `apps/core/views.py`
- Alteração: layout em lista ("Cargos da equipe") com avatar, situação e seta; barra com unidade e redução total; detalhe do cargo, preenchimento, redução, edição de cargo e histórico em modais; botão "Adicionar cargo". Filtros de cargo/situação removidos da view.

### `project_root/templates/core/prioridade1/alertas_carga.html` e `apps/core/views.py`
- Alteração: removida a aba "Teto por unidade" e o ponto de atenção correspondente; "Pontos de atenção" passa a ficar recolhido, exibindo em negrito a quantidade de pontos com ocorrências.

### `project_root/templates/dashboard/desup.html`
- Alteração: removido o cartão "Unidades no limite"; a lista de unidades com pendências passa a abrir para baixo do cartão.

### `project_root/static/css/tailwind-input.css` e `tailwind.min.css`
- Alteração: seta padronizada dos selects, afastada da borda direita.

### Banco de dados
- Nenhuma alteração de estrutura (`makemigrations --check`: "No changes detected"). Nenhum SQL novo para o Supabase.

## 16/10/2026 — Área de atuação do professor

### `project_root/apps/professors/models.py` e `migrations/0012_professor_area_atuacao.py`
- Tipo: alterado / criado.
- Alteração: novo campo `area_atuacao` (texto livre, até 150 caracteres, opcional, padrão vazio).
- Banco de dados: `ALTER TABLE harpiadb_professores_professor ADD COLUMN area_atuacao varchar(150) NOT NULL` (registros existentes ficam vazios).

### `project_root/sql/supabase_professor_area_atuacao.sql`
- Tipo: criado.
- Alteração: script idempotente equivalente à migration 0012 para o SQL Editor do Supabase.

### `project_root/apps/professors/forms.py`, `views.py`
- Alteração: campo no formulário de professor; área incluída na busca da listagem.

### `project_root/templates/professors/professor_form.html`
- Alteração: nova aba "Área", após "Contrato".

### `project_root/templates/professors/professor_list.html`, `dashboard/partials/_professor_table.html`, `professors/partials/_professor_detail.html`
- Alteração: coluna "Área" nas listagens de professores e no detalhe do professor.
- Verificação: `manage.py test apps.professors apps.core` — 214 de 217 aprovados; as 3 falhas (`test_unidade_coord_can_only_see_their_unit`, `test_limite_manual_da_desup_prevalece_sobre_o_calculo`, `test_listagem_mostra_colunas_por_matriz_e_soma_de_horas`) não envolvem a área e já existiam no código commitado.


## 19/10/2026 — Prioridade 2, Fase 1: alocação de docente por turma, carência e RAT

Resumo: o docente deixou de ser um campo de `MatrixComponent` e passou a ser registrado em `AlocacaoTurmaDocente` (uma ou mais linhas por componente, cada uma com docente ou carência). Foram criados os modelos `Carencia` e `SolicitacaoRAT`, a quantidade de turmas por componente e, na tela de Alocação Curricular, o botão "+" (outro docente ou carência) e a coluna "Turmas" (somente números, com número por extenso e confirmação). Os dados existentes foram preservados por migração de dados reversível.

### `project_root/apps/allocations/models.py`
- Tipo: alterado.
- Alteração: novos modelos `AlocacaoTurmaDocente` (restrições `harpia_alocturmadocente_unica` e `harpia_alocturmadocente_unica_sem_turma`), `Carencia` (OneToOne com a alocação; status DECLARADA, EM_ANALISE, HOMOLOGADA, RESOLVIDA) e `SolicitacaoRAT` (status RASCUNHO, AGUARDANDO_DESUP, APROVADO, REJEITADO).
- Motivo: requisito da Prioridade 2 (múltiplas turmas, carências e RAT).

### `project_root/apps/allocations/migrations/0004_alocacao_turma_docente_carencia_rat.py`
- Tipo: criado.
- Alteração: cria os três modelos e as restrições.
- Motivo: passo 2.1 (somente schema).

### `project_root/apps/allocations/migrations/0005_migrar_docente_componente_para_alocacao_turma.py`
- Tipo: criado.
- Alteração: `RunPython` que copia cada `MatrixComponent.docente` para `AlocacaoTurmaDocente` (sem turma). Unidade: a principal do docente, se pertencer à matriz; senão, a de menor id. Consolidado: semestre corrente, turno da matriz (padrão M). É idempotente, reversível e aborta com erro, sem perder dados, quando não há vínculo em "Cursos na Unidade".
- Motivo: passo 2.2 / Regra 5 (sem perda de histórico).

### `project_root/apps/courses/models.py`
- Tipo: alterado.
- Alteração: removido `MatrixComponent.docente`; adicionado `quantidade_turmas` (padrão 1).
- Motivo: passo 2.3 e coluna "Turmas".

### `project_root/apps/courses/migrations/0010_matrixcomponent_quantidade_turmas.py` e `0011_remove_matrixcomponent_docente.py`
- Tipo: criados.
- Alteração: 0010 adiciona `quantidade_turmas`; 0011 remove `docente`, dependendo de `allocations.0005` (a cópia roda antes). Na reversão o campo volta nulo e é repreenchido pela reversa da 0005.
- Motivo: passo 2.3 com ordem segura.

### `project_root/apps/allocations/services.py`
- Tipo: criado.
- Alteração: regras de negócio (escolha de docente, "Sem professor" com carência, "Não oferecido", linhas adicionais, quantidade de turmas de 1 a 20 só com dígitos, status do componente, `alocacoes_vigentes`, `atribuir_docente` para fixtures). Operações em transação com bloqueio de linha.
- Motivo: centralizar a regra e evitar duplicação entre views.

### `project_root/apps/allocations/views.py` e `project_root/config/urls.py`
- Tipo: alterado.
- Alteração: `AlocarDocenteComponenteView` passa a operar em linhas (`linha_id`, `acao=remover`); nova `QuantidadeTurmasComponenteView` (`quantidade_turmas_componente`, POST); pendências e aprovação calculadas por turma. Perfil, escopo por unidade, janela de entrega e CSRF mantidos no servidor; o `linha_id` precisa pertencer ao componente da URL (evita IDOR); a unidade do pedido do DESUP é validada contra as unidades da matriz.
- Motivo: Prioridade 2 e Regra 2 (segurança).

### `project_root/templates/allocations/alloc_curricular.html` e `templates/allocations/partials/_slot_docente.html`
- Tipo: alterado / criado.
- Alteração: botão "+", linhas adicionais com remoção, coluna "Turmas" com input numérico, número por extenso e confirmação; modelo `<template>` da nova linha; contagem de pendências por componente. Rótulos acessíveis (`aria-label`, `sr-only`), foco por teclado e confirmação com Enter/Esc; tabela já responsiva (`stack-table`).
- Motivo: requisito da diretoria.

### `project_root/static/css/tailwind.min.css`
- Tipo: alterado (gerado por `npm run build:css`).
- Motivo: novas classes Tailwind.

### `project_root/apps/core/priority1.py`, `apps/core/views.py`, `apps/professors/models.py`, `apps/professors/views.py`, `apps/extra_curricular/services.py`, `apps/core/management/commands/sync_unidades_cursos.py`
- Tipo: alterado.
- Alteração: cargas e listagens passam a ler `AlocacaoTurmaDocente` do semestre corrente em matrizes vigentes, mantendo a deduplicação de componentes compartilhados.
- Motivo: o campo `docente` foi removido.

### `project_root/apps/courses/admin.py`, `apps/courses/forms.py`, `templates/courses/matrix/partials/_formset_row.html`, `templates/courses/matrix_form.html`
- Tipo: alterado.
- Alteração: removidas as referências ao campo `docente`; `quantidade_turmas` exibida no admin.
- Motivo: o campo foi removido.

### `project_root/apps/allocations/admin.py`
- Tipo: alterado.
- Alteração: `AlocacaoTurmaDocente`, `Carencia` e `SolicitacaoRAT` registrados no Django Admin.
- Motivo: operação técnica (perfil ADMIN).

### `project_root/apps/allocations/tests_e2e.py`, `apps/core/tests_e2e.py`, `apps/professors/tests_e2e.py`
- Tipo: alterado.
- Alteração: fixtures adaptadas ao novo modelo; 28 testes novos (linhas, carência, "+", turmas, entradas inválidas, isolamento entre unidades, janela fechada, IDOR, restrições de banco). Nenhum teste foi enfraquecido; duas asserções "não existe nenhum consolidado" passaram a "não existe consolidado aprovado", pois a fixture agora cria o consolidado em rascunho.

### `project_root/sql/supabase_alocacao_turma_docente.sql`
- Tipo: criado.
- Alteração: script idempotente equivalente às migrations 0004, 0010, 0005 e 0011 para o SQL Editor do Supabase (usar este script OU `migrate`). Aborta, sem alterar nada, se algum componente com docente não puder ser mapeado.
- Motivo: Regra 8. **Não foi executado em PostgreSQL neste ambiente** — revisar e testar antes (de preferência com backup).

### Banco de dados (Supabase)
- Novas tabelas `harpiadb_alocacoes_alocacao_turma_docente`, `harpiadb_alocacoes_carencia` e `harpiadb_alocacoes_solicitacao_rat`; nova coluna `harpiadb_cursos_componente_matriz.quantidade_turmas`; remoção de `harpiadb_cursos_componente_matriz.docente_id` após a cópia.

### Verificações
- `python manage.py check`: nenhum problema.
- `python manage.py makemigrations --check --dry-run`: "No changes detected".
- Migração de dados 0005 (ida, repetição, reversão e caso de erro) validada com script sobre o estado histórico dos modelos em SQLite; a cadeia completa de `migrate` não roda em SQLite (migrações antigas usam SQL de PostgreSQL) e não foi testada em PostgreSQL.
- `python manage.py test --settings=config.settings._tmp_test`: 667 testes executados; 12 falhas (9 falhas e 3 erros), todas já existentes: as mesmas 12 falham no commit original (HEAD), verificado em worktree limpo (`test_estouro_de_limite_gera_mensagem_e_nao_500`, `test_soma_de_itens_respeita_o_limite`, `test_formset_da_unidade_barra_limite_manual_de_horas_extras`, `test_reset_exige_tela_e_checkbox_de_confirmacao`, `test_unidade_coord_can_only_see_their_unit`, `test_hr_total_dois_decimais`, `test_opcoes_de_duplicacao_para_a_desup`, `test_lista_desup_sem_form_de_status`, `test_limite_manual_da_desup_prevalece_sobre_o_calculo`, `test_listagem_mostra_colunas_por_matriz_e_soma_de_horas` e os 2 de iconografia). Nenhuma falha nova; os testes de alocação, inclusive os 28 novos, passam.
- `npm run build:css`: executado com sucesso.
- Pendências reais: `turma` fica vazia (não há criação de `ClassGroup` por componente); uma carência declarada continua impedindo a aprovação da alocação (comportamento anterior); fluxo de homologação de carência e de RAT ainda sem telas (Fases seguintes).

### `project_root/templates/core/prioridade1/equipe_diretiva.html`
- Tipo: alterado.
- Alteração: no modal "Redução de carga", barra de 0 a 20 h sincronizada com o campo numérico (máximo 20 h no campo) e botão selecionável "Redução total (20 h)" (marca 20 h; ao desmarcar, volta ao valor anterior). Validação do servidor inalterada (aceita até 168 h).
- Verificação: `manage.py test apps.core.tests_prioridade1_desup` — 18 aprovados; `npm run build:css` executado.

## 19/10/2026 — Remoção de atalho do painel sem erro 404

### `project_root/apps/core/views.py`
- Tipo: alterado.
- Alteração: `AtalhoRemoveView` — o POST remove somente atalhos do próprio usuário e, se o atalho não existe mais ou é de outro usuário, redireciona ao painel com aviso (antes: 404). O GET no endereço de remoção redireciona ao painel (antes: 405).
- Motivo: tela "Página não encontrada" em `/core/atalhos/3/remover/`. Escopo por usuário mantido no servidor, sem revelar a existência do id.

### `project_root/apps/core/tests_e2e.py`
- Tipo: alterado.
- Alteração: 2 testes novos (atalho inexistente/de outro usuário; GET volta ao painel).

### Verificações
- `manage.py test apps.core.tests_e2e.JornadaAtalhosDashboardTests`: 4 aprovados.
- Sem alteração de banco de dados.

## 19/10/2026 — Redesenho da página de Alertas e Limites de Carga e remoção de banner

### `project_root/templates/core/prioridade1/alertas_carga.html`
- Tipo: alterado.
- Alteração: layout conforme o modelo da diretoria — cabeçalho com ícone e descrição; filtros em cartão (Unidade, Curso, Ano, Turno, com ícones); quatro cartões (Disciplinas, Professores, Exatamente no limite, Acima do limite) com cores azul, verde, âmbar e vermelho; faixa "Pontos de atenção" com botão "Ver todos" (expande/oculta a lista, com `aria-expanded`). As abas Readaptações e Exceções, os modais e todos os dados foram mantidos. Cores não são o único indicador (texto e ícones presentes); filtros empilham em telas pequenas.

### `project_root/apps/core/views.py`
- Tipo: alterado.
- Alteração: `AlertasCargaDesupView` passa `cursos` (limitados à unidade, quando filtrada) e `filtro_curso` (somente dígitos); o filtro por curso já era aceito por `obter_resumo_prioridade1`.

### `project_root/templates/core/prioridade1/solicitacoes_professor.html`
- Tipo: alterado.
- Alteração: removido o bloco "Análise institucional de solicitações" (título e texto explicativo).

### `project_root/static/css/tailwind.min.css`
- Tipo: alterado (gerado por `npm run build:css`).

### Verificações
- `manage.py test apps.core.tests_prioridade1_desup`: 18 aprovados. Teste temporário (removido) confirmou render da página com filtros de unidade/curso e valor inválido de curso.
- `apps.core.tests_iconography`: 2 falhas já existentes, causadas por `extra_curricular/pendencia_list.html` (`ph-list-bullets`), sem relação com estas telas.
- Sem alteração de banco de dados.

## 19/10/2026 — Janelas de detalhe nos cartões de Alertas e Limites de Carga

### `project_root/apps/core/priority1.py`
- Tipo: alterado.
- Alteração: `obter_resumo_prioridade1` passa a devolver também `detalhe_disciplinas`, `detalhe_sobra`, `detalhe_limite`, `detalhe_acima` e `limite_detalhe` (cada lista com no máximo 100 itens, ordenados pelos maiores desvios; os totais continuam nos cartões). Chaves existentes inalteradas.
- Motivo: explicar os números com os itens que os compõem.

### `project_root/templates/core/prioridade1/alertas_carga.html`
- Tipo: alterado.
- Alteração: cada cartão ganhou seta (botão acessível) que abre uma janela com "O que significa", "Como é calculado" e a lista detalhada (tabelas com rolagem horizontal em telas pequenas; aviso quando a lista é truncada).

### `project_root/apps/core/tests_alertas_detalhes.py`
- Tipo: criado.
- Alteração: 2 testes (conteúdo dos detalhes e acesso restrito à DESUP).

### Verificações
- `manage.py test apps.core.tests_alertas_detalhes apps.core.tests_prioridade1_desup`: aprovados (2 + 18). `npm run build:css`: executado. Sem alteração de banco de dados.

## 19/10/2026 — Ajuda ("?") com tutorial nas abas da DESUP e ajustes em Alertas e Limites de Carga

### `project_root/apps/core/ajuda.py`
- Tipo: criado.
- Alteração: conteúdo do tutorial (resumo, "O que você pode fazer aqui" e "Passo a passo") das 12 abas do menu da DESUP: Dashboard, Unidades, Usuários, Equipe diretiva, Solicitações externas, Alertas, Professores, Alocação, Extracurriculares, Matrizes, Componentes e Entrega.

### `project_root/apps/core/context_processors.py` e `project_root/config/settings/base.py`
- Tipo: alterado.
- Alteração: novo context processor `ajuda_pagina`, ativo somente para o perfil DESUP e para as rotas cadastradas.

### `project_root/templates/base.html`, `templates/partials/_ajuda_botao.html`, `templates/partials/_ajuda_modal.html`
- Tipo: alterado / criados.
- Alteração: botão "?" ao lado do título da página e modal de tutorial (foco no botão de fechar, Esc e clique fora fecham; foco retorna ao botão; passos numerados com texto para leitor de tela). Novos blocos `header_titulo` e `header_ajuda` permitem a uma página assumir o próprio título.

### `project_root/templates/core/prioridade1/alertas_carga.html`
- Tipo: alterado.
- Alteração: título exibido uma única vez (o do topo foi removido nesta página) com o "?" ao lado; removido o texto "Acompanhe a supervisão…"; removidas as seções "O que significa" e "Como é calculado" das janelas dos cartões; os números de "Pontos de atenção" viraram botões que abrem a lista de professores de cada ponto.

### `project_root/apps/core/priority1.py`
- Tipo: alterado.
- Alteração: `obter_resumo_prioridade1` devolve também `detalhe_diretivos`, `detalhe_readaptados` e `detalhe_medio` (professor, unidade, situação; até 100 itens). Contagens inalteradas.

### `project_root/apps/core/tests_ajuda.py`, `apps/core/tests_alertas_detalhes.py`, `apps/core/tests.py`
- Tipo: criado / alterado.
- Alteração: testes da ajuda (12 rotas válidas e com conteúdo, botão e modal em cada página para DESUP, ausência para coordenador, título único em Alertas) e dos pontos de atenção. Em `tests.py`, `test_remove_apenas_do_proprio_usuario` passou a esperar redirecionamento (e não 404) ao tentar remover atalho alheio, consequência da alteração de `AtalhoRemoveView` registrada acima; o atalho continua sem ser apagado.

### Verificações
- `manage.py test apps.core apps.allocations`: 249 executados; 3 falhas já existentes (`test_unidade_coord_can_only_see_their_unit` e as 2 de iconografia, de `extra_curricular/pendencia_list.html`) e 1 ajustada (descrita acima). `npm run build:css` executado. Sem alteração de banco.
- Pendência real: os textos dos tutoriais foram escritos a partir do código das telas e devem ser revisados por quem conhece o fluxo real da DESUP.

## 19/10/2026 — Tutorial guiado, cabeçalho fixo e padrão "resumo + filtro + dados" (Unidades, Solicitações, Professores, Matrizes)

### `project_root/templates/partials/_ajuda_modal.html`, `_ajuda_botao.html`, `apps/core/ajuda.py`, `apps/core/context_processors.py`
- Tipo: alterado.
- Alteração: o "?" agora inicia um tutorial guiado — popups em sequência (boas-vindas, passos com "Anterior/Próximo/Concluir", indicador de progresso, "Pular tutorial", setas do teclado e Esc). Cada passo destaca o elemento da ação e o popup aparece ao lado dele (direita, depois esquerda; se não couber, embaixo ou em cima; no celular, como folha na base). Os alvos usam seletores ou "rota:<nome>", resolvidos para o link correspondente; passo sem alvo aparece centralizado.
- Motivo: pedido de tutorial sequencial e junto dos botões (ex.: "Novo Professor").

### `project_root/templates/base.html`, `static/css/dashboard.css`
- Tipo: alterado.
- Alteração: cabeçalho fixo e colado no topo (o `<main>` não tem mais padding superior; o aviso de modo de visualização ganhou margem própria). Título, "?", notificações e conta no mesmo cabeçalho.

### `project_root/templates/partials/_kpi_cards.html`
- Tipo: criado.
- Alteração: cartões de resumo reutilizáveis (ícone, número e rótulo; sem texto extra).

### `project_root/apps/core/views.py`, `templates/core/unidade_list.html`
- Tipo: alterado.
- Alteração: Unidades — resumo (unidades, ativas, inativas, cursos ativos), busca por nome/sigla, filtro de situação e tabela com cursos ativos, status e ações, com paginação preservando os filtros. Os rótulos "Ativo/Inativo" foram mantidos.

### `project_root/templates/core/prioridade1/solicitacoes_professor.html`, `apps/core/views.py`
- Tipo: alterado.
- Alteração: Solicitações externas — resumo (pendentes, aprovadas, recusadas), filtros e tabela enxuta; a justificativa e o formulário de decisão (aprovar/recusar com motivo) passaram para uma janela aberta por "Decidir"/"Ver". Regras e endpoint de decisão inalterados.

### `project_root/apps/professors/views.py`, `templates/professors/professor_list.html`
- Tipo: alterado.
- Alteração: Professores — resumo (no sistema, ativos, afastados e, com filtro, encontrados) no lugar das etiquetas de contagem; botões de ação alinhados à direita; filtros e tabela mantidos.

### `project_root/apps/courses/views.py`, `templates/courses/matrix_list.html`
- Tipo: alterado.
- Alteração: Matrizes — resumo (total, vigentes, rascunhos só para a DESUP, histórico) no escopo do perfil; filtros e tabela mantidos.

### `project_root/apps/core/tests_resumos_telas.py`, `tests_ajuda.py`, `apps/professors/tests_e2e.py`
- Tipo: criado / alterado.
- Alteração: testes dos resumos, filtros, escopo por perfil, cabeçalho colado e alvos do tutorial. Em `professors/tests_e2e.py`, `test_listagem_mostra_total_de_professores` passou a verificar o cartão "No sistema" (antes procurava o texto "2 no sistema").

### Verificações
- `manage.py test apps.core apps.professors apps.courses`: apenas falhas já existentes (`test_unidade_coord_can_only_see_their_unit`, `test_limite_manual_da_desup_prevalece_sobre_o_calculo`, `test_listagem_mostra_colunas_por_matriz_e_soma_de_horas`, `test_hr_total_dois_decimais`, `test_opcoes_de_duplicacao_para_a_desup` e as 2 de iconografia); os testes novos e os ajustados passam. `npm run build:css` executado. Sem alteração de banco.
- Não validado visualmente em navegador (posição do popup, cabeçalho em telas reais).

## 19/10/2026 — Exclusão de cargo da equipe diretiva mesmo com ocupantes

### `project_root/apps/core/views.py`
- Tipo: alterado.
- Alteração: `TipoCargoDiretivoDeleteView` passa a excluir o cargo mesmo com ocupantes: as ocupações dele (vigentes e históricas) são removidas junto, na mesma transação. A auditoria (`CARGO_DIRETIVO_EXCLUIDO`) registra a quantidade de ocupações removidas e a mensagem ao usuário informa o mesmo. Continuam restritos à DESUP, POST e CSRF. Professores e unidades não são afetados.
- Motivo: pedido da DESUP. Observação: é uma exclusão definitiva do histórico daquele cargo (decisão explícita do solicitante, em exceção à diretriz de evitar exclusões destrutivas).

### `project_root/templates/core/prioridade1/_modal_form.html`
- Tipo: alterado.
- Alteração: a confirmação passou a avisar que ocupantes e histórico do cargo também serão excluídos.

### `project_root/apps/core/tests_prioridade1_desup.py`
- Tipo: alterado.
- Alteração: `test_cargo_com_historico_nao_pode_ser_excluido` foi substituído por `test_cargo_com_ocupantes_pode_ser_excluido_junto_com_as_ocupacoes` (a regra anterior foi alterada a pedido); novo teste garante que ocupações de outros cargos e o cadastro do professor ficam intactos.

### Verificações
- `manage.py test apps.core.tests_prioridade1_desup`: 19 aprovados. Sem alteração de banco (sem migração).

### Correção — botão "Excluir cargo" ausente em cargos preenchidos
- `project_root/templates/core/prioridade1/_modal_form.html`: removido o bloqueio da tela que escondia "Excluir cargo" e exibia "Este cargo tem ocupações no histórico e não pode ser excluído" quando o cargo tinha ocupações (o servidor já permitia a exclusão). Agora o botão aparece sempre, com a confirmação que avisa que ocupantes e histórico também serão excluídos.
- `project_root/apps/core/tests_prioridade1_desup.py`: novo teste `test_modal_de_edicao_oferece_excluir_mesmo_com_ocupantes`. Verificação: `manage.py test apps.core.tests_prioridade1_desup` aprovado.

### Tutorial guiado ligado às funções reais da tela
- `project_root/apps/core/ajuda.py`: cada passo agora tem `alvo` (elementos reais da tela, com alternativas), `abrir` (o que o tutorial clica para abrir o popup, aba ou filtro), `fechar` (o que desfazer ao sair do passo) e `requisito` (aviso quando o elemento ainda não existe, ex.: escolher uma unidade). Passos novos/ajustados para abrir os popups de verdade: Equipe diretiva (cargo, preenchimento, redução, novo cargo/exclusão, histórico), Alertas (lista dos cartões, pontos de atenção, readaptação, exceção), Professores (detalhe e edição), Solicitações (pedido e decisão), Dashboard (atalhos) e Alocação (campo de docente e opções de carência/não oferecido).
- `project_root/templates/partials/_ajuda_modal.html`: o tutorial executa o `abrir`, destaca o elemento real, mostra o aviso de requisito quando necessário e desfaz (fecha popups, volta a aba, recolhe filtros) ao avançar, voltar, pular ou concluir.
- `project_root/apps/core/context_processors.py`, `templates/dashboard/desup.html`, `templates/core/unidade_list.html`: resolução dos alvos por rota e marcadores `data-tour`.
- `project_root/apps/core/tests_ajuda.py`: testes atualizados (todo passo tem alvo; passos de popup têm abrir e fechar).
- Verificação: `manage.py test apps.core.tests_ajuda apps.core.tests_resumos_telas` aprovados; checagem estática dos seletores contra o HTML de cada página (nenhum passo ficou sem alvo). Não validado em navegador: o comportamento de abrir/fechar popups durante o tutorial deve ser conferido na tela.

## 19/10/2026 — Barra de redução no preenchimento do cargo, tutorial sem "dança", alinhamento e responsividade

### `project_root/templates/core/prioridade1/_reducao_controle.html`, `_campos_form.html`, `equipe_diretiva.html`, `apps/core/forms.py`
- Tipo: criado / alterado.
- Alteração: o controle de redução (campo numérico + barra de 0 a 20 h + botão "Redução total") virou um parcial único, usado tanto no modal "Preencher cargo" quanto no "Redução de carga" (script compartilhado, sem duplicação). No preenchimento, professor, curso e redução ocupam a largura toda e as datas ficam lado a lado. O campo numérico dos dois formulários passou a aceitar no máximo 20 (o servidor continua validando só pelo modelo).
- Testes: `test_barra_de_reducao_aparece_ao_preencher_e_ao_ajustar_o_cargo`.

### `project_root/templates/partials/_ajuda_modal.html`, `apps/core/ajuda.py`, `templates/core/prioridade1/equipe_diretiva.html`
- Tipo: alterado.
- Alteração: o tutorial deixa de "pular": o popup fica invisível enquanto o passo é preparado e só aparece depois de abrir o popup da tela, rolar e posicionar (uma conferência final após o layout assentar); reposicionamento por quadro de animação ao rolar/redimensionar; se faltar algo para abrir o popup (ex.: não há cargo vago), o que foi aberto é desfeito e o item mais próximo é destacado com o aviso; o popup procura o lado com espaço livre e, se nenhum couber, encosta na borda com mais espaço em vez de cobrir o elemento. Alternativas de clique (`a || b`) e marcadores `data-tour-vago/ocupado` escolhem o cargo certo para cada passo.

### `project_root/templates/core/prioridade1/alertas_carga.html`, `templates/base.html`
- Tipo: alterado.
- Alteração: filtros de Alertas ocupam a largura toda, alinhados com as abas e os cartões (4 colunas no desktop/tablet largo, 2 no tablet, 1 no celular); abas com rolagem horizontal sem quebra de texto. No `base.html`, as margens do cabeçalho fixo passaram a acompanhar o padding do `<main>` (quebra em 1024 px), corrigindo estouro lateral de 16 px em tablets (768–1023 px).

### Verificações
- `manage.py test apps.core.tests_ajuda apps.core.tests_resumos_telas apps.core.tests_alertas_detalhes apps.core.tests_prioridade1_desup`: 39 aprovados; `npm run build:css` executado.
- Tentei validar o tutorial no navegador (Chrome), mas o controle remoto não conseguiu anexar à aba ("Cannot attach to this target"); o comportamento visual do tutorial e a responsividade (360/768/1024/1440 px) NÃO foram verificados em tela e precisam de conferência manual.

## 19/10/2026 — Prioridade 1.1: Equipe Diretiva, Coordenações e Estágio/Supervisão (Módulo da Unidade)

### `project_root/apps/core/models.py`, `apps/core/admin.py`, `apps/core/migrations/0009_atividadeestagiosupervisao.py`
- Tipo: alterado / criado.
- Alteração: `UnitBoundQuerySet` e `UnitBoundManager` movidos para o topo de `apps/core/models.py` e associados a `OcupacaoEquipeDiretiva` (`objects = UnitBoundManager()`), garantindo escopo automático por `user.unidade` para `COORDENADOR_UNIDADE`. Criado o modelo `AtividadeEstagioSupervisao` (`harpiadb_nucleo_atividade_estagio_supervisao`) com `UnitBoundManager`, suporte a `COORDENACAO_ESTAGIO`, `SUPERVISAO_ESTAGIO` e `ORIENTACAO_ESTAGIO`, validação de vínculo de servidor e curso com a unidade, formato de semestre (`AAAA.1`/`AAAA.2`), restrições de integridade (`CheckConstraint` de vigência e cargas não negativas) e registro no `HarpiaModelAdmin` (`AtividadeEstagioSupervisaoAdmin`).
- Motivo: atender à Prioridade 1.1 sob a ótica do `COORDENADOR_UNIDADE`, permitindo registrar e acompanhar ocupantes da equipe diretiva, coordenações e atividades de estágio e supervisão da própria unidade com isolamento multi-tenant no servidor.

### `project_root/apps/core/forms.py`
- Tipo: alterado.
- Alteração: criados `OcupacaoEquipeDiretivaUnidadeForm` e `AtividadeEstagioSupervisaoUnidadeForm` para uso exclusivo do `COORDENADOR_UNIDADE`. Ambos restringem `professor` e `curso` (`CourseUnit` ativo) à unidade do usuário autenticado e excluem `carga_reducao_horas`, `unidade`, `cargo` e `criado_por` dos campos editáveis, prevenindo *mass assignment* e mantendo o controle da redução de carga horária exclusivamente com a `DESUP`.

### `project_root/apps/core/views.py`, `apps/core/urls.py`, `apps/core/atalhos.py`
- Tipo: alterado.
- Alteração: implementados `_mapa_alocacoes_sala_por_professor`, `UnidadePrioridade1Mixin` (`allowed_profiles = ['COORDENADOR_UNIDADE']`), `EquipeDiretivaUnidadeView`, `OcupacaoEquipeDiretivaUnidadeCreateView`, `OcupacaoEquipeDiretivaUnidadeUpdateView`, `OcupacaoEquipeDiretivaUnidadeEncerrarView`, `AtividadeEstagioSupervisaoCreateView`, `AtividadeEstagioSupervisaoUpdateView` e `AtividadeEstagioSupervisaoEncerrarView`. As views validam propriedade do objeto com `for_user(request.user)` e `select_for_update()` em transações atômicas, preservam `carga_reducao_horas` definida pela DESUP, registram auditoria (`registrar_evento_prioridade1`), cruzam ocupantes vigentes com `alocacoes_vigentes()` para emitir alertas visuais de docentes alocados em sala de aula e suportam parciais HTMX (`?partial=historico` e `?partial=estagio`). Adicionadas as rotas em `core/urls.py` sob `/core/unidade/equipe-diretiva/` e o atalho `equipe_diretiva_unidade` em `ATALHOS_CATALOGO`.

### `project_root/templates/base.html`, `templates/core/prioridade1/equipe_diretiva_unidade.html`, `form_unidade.html`, `partials/_historico_equipe_unidade.html`, `partials/_estagio_supervisao_list.html`
- Tipo: alterado / criado.
- Alteração: adicionado item de menu "Equipe diretiva" na barra lateral para `COORDENADOR_UNIDADE` (preservando `justify-center group-hover:justify-start`). Criada a interface responsiva da unidade com resumo de redução semanal (somente leitura, definida pela DESUP), banner acessível (`role="alert"`, ícone `ph-warning-circle` e detalhamento de disciplinas/horas) quando integrantes da equipe diretiva ou supervisão de estágio estão alocados em sala de aula, modais de preenchimento/edição/encerramento de ocupações e de atividades de estágio/supervisão, e histórico filtrável via HTMX com cartões em telas pequenas e tabela em telas médias/grandes.

### `project_root/sql/supabase_prioridade1_1_unidade.sql`
- Tipo: criado.
- Alteração: script SQL idempotente para criação da tabela `public.harpiadb_nucleo_atividade_estagio_supervisao`, chaves estrangeiras, restrições `CHECK`, índices e registro em `django_migrations` no Supabase.

### `project_root/apps/core/tests_prioridade1_unidade.py`
- Tipo: criado.
- Alteração: 12 testes cobrindo `UnitBoundManager`, validações de modelo, ausência de `carga_reducao_horas` nos formulários da unidade, controle de acesso por perfil (`COORDENADOR_UNIDADE`, `DESUP`, `ADMIN`, anônimo e coordenador sem unidade), prevenção de vazamento entre unidades e IDOR (404), proteção contra *mass assignment* na redução de carga, detecção e exibição acessível de alerta de docente da equipe diretiva em sala de aula, ciclo completo de atividades de estágio e supervisão e parciais HTMX.

### Verificações
- `python manage.py check`: sem erros (`0 silenced`).
- `python manage.py makemigrations --check --dry-run`: `No changes detected`.
- `python manage.py test apps.core.tests_prioridade1_unidade apps.core.tests_prioridade1_desup apps.core.tests_ajuda --settings=config.settings._tmp_test`: 42 testes executados e aprovados (`OK`).
