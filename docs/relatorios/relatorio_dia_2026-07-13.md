# Relatório do dia — 2026-07-13

Sistema: **AllocGest-DESUP / HARPIA** (alocação de professores FAETEC/FAETERJ)
Branch: `fix/responsivity`

> **Observação sobre commits:** conforme combinado, **nenhum commit foi feito por mim** — todos
> os commits são feitos por você. Ao final há a lista de arquivos alterados ainda não commitados.

---

## 1. Extracurricular — funcionalidade "Reabrir" (lado Coord. DESUP)

Correção da reabertura de uma pendência já **Finalizada (Aprovada)** para revisão.

- **Removido o "motivo"** exibido abaixo do status *Finalizado* na tabela principal
  (`pendencia_list.html`). A informação continua visível no **detalhe** da pendência.
- **Pop-up de confirmação centralizado (~1s):** mensagens de **sucesso/info** viraram um *toast*
  centralizado na tela que some sozinho em ~1s; mensagens de **erro/aviso** continuam como banner
  fixo no topo. Vale para **toda mensagem de sucesso** do sistema (global) — `base.html`.
- **CH justificada deixa de contar ao reabrir:** ao reabrir, qualquer CH previamente aprovada
  **para de contar** até ser aprovada de novo. A coluna "CH Justificada" da listagem passou a
  respeitar o *status* da pendência (só conta quando `APROVADO`) — `services.py`.
- **Robustez:** a reabertura foi envolvida em `transaction.atomic()` — reverte os pareceres dos 3
  grupos (TCC / Extensão / Redução de CH) para *Pendente* e re-sincroniza o status de forma
  consistente, preservando as horas aprovadas como ponto de partida (`views.py`).
- **Testes:** 3 testes de regressão adicionados; suíte do `extra_curricular` verde.

## 2. Extracurricular — verificação do "Finalizar"

Confirmado que ao **Finalizar** o estado é persistido corretamente (via
`sincronizar_status_pendencia`) e que tanto a **tabela de extracurriculares** quanto a **própria
página de detalhe** releem o novo estado. Status vira `APROVADO` somente quando **todos** os
itens estão aprovados.

## 3. Banco — matrizes e componentes curriculares

Reset completo das matrizes e re-carga dos componentes (matrizes serão recriadas do zero pela
Coord. DESUP).

- **Wipe no Supabase** das matrizes + componentes (`TRUNCATE ... RESTART IDENTITY CASCADE`).
- **Script de seed atualizado** com o novo arquivo `Componentes_Curriculares_TEC_LIC.csv`
  (**507 componentes** — 312 TEC + 195 LIC), validado (0 códigos duplicados).
- **SQL de INSERT idempotente** gerado para rodar no SQL Editor do Supabase.
- **Créditos = CH total / 20** gravados no banco (SQL de `UPDATE` + regra também no comando de
  sync, tanto na criação quanto na atualização).
- **Postgres local totalmente re-sincronizado** para espelhar o Supabase (matrizes zeradas, 507
  componentes, todos com créditos = CH/20).
- **SQL para apagar somente as matrizes** (preservando os componentes) — usado após você criar
  matrizes de teste no Supabase.

## 4. Banco — limpeza das justificativas extracurriculares de teste

- **SQL** `scripts/sql/wipe_justificativas_extra_supabase.sql` para o Supabase: limpa as 4 tabelas
  (`pendenciaextra` + TCC + extensão + redução) com `TRUNCATE ... RESTART IDENTITY CASCADE`, com
  `SELECT` de conferência e bloco opcional (comentado) p/ limpar notificações relacionadas.
- **Local aplicado:** 20 → **0** pendências (nada mais referencia essas tabelas; professores e
  demais dados intactos).

## 5. Janela de Entrega — formato de data (dd/mm/aaaa)

Os campos de início/fim mostravam `mm/dd/aa`.

- **Causa raiz identificada:** os forms usados pelas telas de criar/editar janela estão em
  `apps/core/views.py` (`JanelaEntregaCreateForm` / `JanelaEntregaUpdateForm`) — **não** no
  `apps/core/forms.py` (esse `JanelaEntregaForm` é código morto). Além disso, o
  `<input type="date">` nativo escolhe o formato de exibição pela **língua do navegador** (o seu
  está em inglês → mostrava `mm/dd`), não pela do Windows.
- **Solução:** adotado o **flatpickr** (carregado no `base.html` via CDN, no mesmo padrão das
  demais libs), inicializado nos campos `.js-date-ptbr`:
  - exibe **dd/mm/aaaa fixo**, independente do idioma do navegador;
  - envia o valor em **ISO (`Y-m-d`)** num input oculto → o Django parseia sem alterar settings.

## 6. Janela de Entrega — validação das datas

Regras que **não existiam** e foram implementadas (servidor + calendário):

- `data_inicio` **não pode** ser anterior ao dia atual.
- `data_fim` **não pode** ser anterior ao dia atual.
- `data_inicio == data_fim` **é permitido** (abertura/reabertura de 24h).
- `data_fim` não pode ser anterior a `data_inicio` (mantido).
- Na **edição**, a regra "não pode no passado" só se aplica ao campo que você **efetivamente
  alterar** — assim, editar (ex.: status) uma janela já em andamento não trava.
- **Cliente:** o calendário (flatpickr) desabilita dias anteriores a hoje (`minDate: 'today'`).
- **Testes:** 7 testes de regressão (`JanelaEntregaDataValidacaoTests`), todos verdes.

## 6.1. Janela de Entrega — status travado em "Aberto" na criação

Não faz sentido criar uma janela nova já **fechada**.

- No **CreateForm**, o campo `status` mostra **somente "Aberto"** e fica **desabilitado**
  (`disabled`) no formulário.
- **À prova de burla:** por ser campo desabilitado, o Django ignora o valor vindo do POST e usa o
  *initial* (`Aberto`) — mesmo forçando `Fechado` na requisição, a janela é salva como **Aberta**.
- A **edição** de janela continua permitindo trocar o status normalmente (fechar/reabrir); só a
  **criação** foi travada.

## 7. Responsividade total

Aplicada responsividade em **todas as telas** do app: no mobile, as tabelas **empilham em
cards** (classe `.stack-table` + `data-label`), com filtros/cabeçalhos/grids adaptáveis. Corrigido
o *scroll horizontal* global (o `<main>`, sendo flex-child, ganhou `min-width:0`).

## 8. Matriz Curricular — campos "Código" e "CH SEM." bloqueados

Na tela de **nova/editar matriz curricular**, os campos **Código** (da disciplina) e **CH SEM.**
(`carga_horaria_semanal`) são obtidos automaticamente e não devem ser alterados pela DESUP.

- Ambos ficaram **`disabled`** no `MatrixComponentForm` — travados/acinzentados na UI (o JS de
  auto-preenchimento continua exibindo o valor normalmente).
- **À prova de adulteração:** por serem campos desabilitados, o Django ignora qualquer valor vindo
  no POST; um `clean()` **recalcula no servidor** — `codigo` = código da disciplina;
  `carga_horaria_semanal` = CH total / 20 (consistente com `MatrixComponent.save()`). Vale na
  criação e na edição (recalcula ao mudar a CH).
- **Super admin/dev** continua podendo editar via **Django admin** (não usa esse form).
- **Teste:** `test_codigo_e_ch_semanal_ignoram_valor_adulterado_no_post` — POST com `codigo=HACKED`
  e `carga_horaria_semanal=999` resulta em `SI001` e `4` (recalculados). Verde.

## 9. Extracurriculares — coluna "Justificativa" vazia mostrava "None"

Na tabela de extracurriculares, linhas sem justificativa exibiam o literal **"None"** (o *service*
define `justificativa_detalhe = None`).

- `pendencia_list.html`: passou a usar `default_if_none:"Nenhuma"` → quando vazio, mostra
  **"Nenhuma"**; estilo em **cinza claro** quando vazio (azul quando há justificativa).

## 10. Regras de virada de semestre (matriz + justificativas)

Verificação das duas regras de negócio pedidas para quando o semestre vira.

### 10.1. Matriz do semestre anterior bloqueada para a unidade — **já estava implementado**
- A edição de matriz só é permitida para matrizes em **Rascunho**
  (`CurriculumMatrixUpdateView.dispatch` → *"Somente matrizes com status Rascunho podem ser
  editadas."*). Matrizes **Vigente** e **Histórico** ficam **bloqueadas para todos** (inclusive a
  unidade) — o botão vira o cadeado *"Bloqueado"* na listagem.
- Ao **publicar** uma nova matriz do curso, as anteriores viram `is_vigente=False` (Histórico)
  automaticamente — portanto a matriz do semestre anterior deixa de ser editável. **Nenhuma
  mudança necessária.** (Super admin/dev continua via Django admin.)

### 10.2. Justificativas não podem contar em semestre seguinte — **corrigido (era bug)**
A `PendenciaExtra` já é escopada por **professor + semestre** (`unique_together`), mas o cálculo
`Professor.ch_justificada` somava **todas** as justificativas aprovadas, **sem filtrar semestre**.
Efeito: uma justificativa aprovada em 2026.1 continuava contando em 2026.2 e seguintes (inflando
`percentual_alocado` / `ch_nao_alocada` no dashboard e na tela de professores).

- **`apps/extra_curricular/utils.py` (novo):** helper `semestre_atual()` — fonte única de verdade
  do semestre corrente (`AAAA.S`; meses 1–6 → `.1`, 7–12 → `.2`).
- **`apps/professors/models.py`:** `ch_justificada` agora filtra `status='APROVADO'` **e**
  `semestre=semestre_atual()`. Justificativas de semestres anteriores deixam de contar ao virar o
  semestre — elas seguem a matriz/semestre, não ficam acumuladas no professor.
- **`apps/extra_curricular/views.py`:** `_semestre_atual()` passou a delegar para o helper
  (mesma lógica, uma fonte só).
- **Testes:** 2 novos (`test_justificativa_semestre_anterior_nao_conta_no_professor` e a
  contraprova `..._semestre_atual_conta...`); fixtures de `DecisaoDesupTests` passaram a usar
  `semestre_atual()` para não dependerem de data fixa. Suítes `extra_curricular` + `professors`
  verdes (14) e `core` + `courses` verdes (48).

---

## Verificação geral

- `python manage.py check` → **0 problemas**.
- Testes: `apps.core` **42/42** verdes (incl. os 7 novos de validação de data);
  `apps.courses` **6/6** verdes (incl. o novo de bloqueio de Código/CH SEM.);
  `apps.extra_curricular` verde (incl. os de reabrir).
- Cenários de data conferidos manualmente (7/7 conforme esperado).

## Arquivos alterados ainda não commitados

- `apps/core/views.py` — forms da janela: status travado em "Aberto" (criar) + flatpickr
  (dd/mm/aaaa) + validação de datas.
- `apps/core/tests.py` — `JanelaEntregaDataValidacaoTests` (7 testes).
- `templates/base.html` — flatpickr (CDN + init `.js-date-ptbr` com `minDate`).
- `apps/courses/forms.py` — `Código`/`CH SEM.` bloqueados (disabled + recálculo no `clean()`).
- `apps/courses/tests.py` — teste de bloqueio à prova de adulteração.
- `templates/extra_curricular/pendencia_list.html` — "None" → "Nenhuma" na coluna Justificativa.
- `apps/extra_curricular/utils.py` — **novo**: helper `semestre_atual()` (fonte única).
- `apps/professors/models.py` — `ch_justificada` escopada pelo semestre atual (§10.2).
- `apps/extra_curricular/views.py` — `_semestre_atual()` delega para o helper.
- `apps/extra_curricular/tests.py` — 2 testes de escopo por semestre + fixtures sem data fixa.

> Os itens 1–4 e 7 já haviam sido commitados por você em sessões anteriores; os itens **5, 6, 8,
> 9 e 10.2** (janela de entrega, matriz curricular, coluna Justificativa e escopo de justificativa
> por semestre) são as mudanças pendentes acima. O item **10.1 já estava implementado** (nenhum
> arquivo alterado).

## Ações manuais pendentes (suas)

1. Rodar no **SQL Editor do Supabase** (porta 443), se ainda não rodou:
   `scripts/sql/wipe_justificativas_extra_supabase.sql` (limpeza das justificativas de teste).
2. Testar a **Janela de Entrega**: abrir *Nova/Editar* → confirmar campo em **dd/mm/aaaa** (mesmo
   com navegador em inglês) e que o calendário **não deixa** escolher dias passados. *(Ctrl+F5 se
   o server estiver aberto, para recarregar o `base.html`.)*
3. Fazer os **commits** das mudanças pendentes.
