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
