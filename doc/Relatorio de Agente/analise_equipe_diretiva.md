# Equipe Diretiva — correções de 21/10/2026

## Diagnóstico

Foram consultados README.md, relatoriodemodificações.md, modelos, managers,
formulários, views, URLs, templates, administração, auditoria, consumidores de HR
e testes. OcupacaoEquipeDiretiva vincula Unidade, TipoCargoDiretivo, Professor e,
quando exigido, CourseUnit. O período é armazenado em data_inicio/data_fim;
não existe campo de status nem soft delete nesse modelo. AuditoriaGlobal é
independente do histórico funcional.

O encerramento gravava hoje, mas vigente, HR, alertas e conflitos consideravam
o fim inclusivo. Assim, a mesma ocupação continuava ativa nesse dia. O histórico
incluía ativos e classificava futuros como encerrados. A equipe atual era
extraída dos últimos 200/300 registros, podendo omitir ocupantes antigos ativos.

## Regras e arquivos alterados

- apps/core/models.py: período da ocupação passa a ser [início, fim). No dia do
  fim ela está encerrada. Consultas e sobreposições seguem esse critério;
  períodos encerrados no próprio início têm duração zero e não bloqueiam substitutos.
- apps/core/views.py: encerramento imediato e idempotente; cadastro futuro deve
  ser corrigido/excluído, sem inventar período de exercício. Histórico contém
  somente data_fim até hoje; equipe atual é consultada sem limite arbitrário.
  Exclusão mantém transação, isolamento e auditoria, agora com IDs, período e HR.
- apps/core/forms.py: esclarece o significado da data final nos dois formulários.
- apps/professors/models.py: HR usa a propriedade vigente da ocupação, mantendo prefetch.
- apps/core/priority1.py e apps/allocations/views.py: alertas usam o mesmo filtro.
- templates/core/prioridade1/equipe_diretiva_unidade.html: histórico somente de
  encerrados e ação explicitamente identificada como exclusão de cadastro indevido.
- apps/core/tests_prioridade1_unidade.py: regressões de encerramento, substituição
  no mesmo dia, HR, histórico DESUP/unidade, exclusão, repetição, futuros e volume.

Encerrar preserva ocupação e datas. Excluir elimina somente a ocupação indevida,
preserva Professor e registra AuditoriaGlobal na mesma transação. A exclusão
continua exigindo profissional vinculado à unidade, conforme regra existente.

## Validação executada

Com config.settings._tmp_test, SQLite em memória e MD5 somente no processo de
teste para acelerar as senhas: 125 testes de unidade/DESUP, alertas, regras de
alocação, alocações e extracurriculares; 121 passaram, 4 falharam.
As quatro falhas foram reproduzidas numa cópia temporária com os arquivos Python
originais de HEAD: busca de professor de outra unidade (IndexError), dois testes
que salvam o campo inexistente limite_horas_extra e teste de formulário de status
na lista de extracurriculares. Não foram alterados por pertencerem a outros fluxos.

Após o último ajuste de auditoria, todos os 17 testes do módulo da unidade
passaram novamente. Django check sem problemas; makemigrations --check --dry-run
indicou No changes detected; git diff --check passou.

## Impactos e pendências

Não há migration nem atualização em massa. Datas existentes são preservadas.
A interpretação do dia final muda para exclusivo também em períodos já agendados:
a ocupação deixa de reduzir HR no próprio dia final. Readaptações, estágios e
outros períodos mantêm suas regras anteriores.

Ocupações futuras não aparecem como atuais nem como histórico encerrado. Não
foi criada uma nova interface para agendamentos. Não foi feita auditoria dos
dados reais nem correção automática de sobreposições preexistentes. Exclusões
físicas antigas não podem ser reconstruídas no histórico sem fonte adicional.
O fluxo global de exclusão de tipos de cargo pela DESUP possui regra documentada
própria de remoção de vínculos e não foi alterado neste trabalho.
