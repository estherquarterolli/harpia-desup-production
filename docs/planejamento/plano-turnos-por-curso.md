# Plano — Turnos por Curso (matrizes-irmãs por turno + alocação independente)

> **Status:** planejado, **NÃO implementado**. Feature grande, companheira do
> [plano de virada de semestre](./plano-virada-semestre.md). Rastreada em
> `docs/checklist_correcao.md` como **CORR-013**. Execução posterior.
> Decisões travadas com o usuário em **2026-07-16**.

## Contexto

Hoje o sistema não distingue turnos de forma efetiva. O campo `turno` existe **apenas** em
`CurriculumMatrix` (`M/T/N`, nullable) e está **inerte**: não está no formulário de matriz, o
filtro "Turno" da lista existe no template mas **não é lido no servidor**
(`CurriculumMatrixListView._apply_filters`), e a duplicação não carrega turno. Na prática só dá
para diferenciar duas matrizes do mesmo curso pelo **nome/código** — não pelo turno.

O que a DESUP precisa: um curso pode ser ofertado em **mais de um turno** (ex.: manhã e noite) numa
unidade. Ao **criar a matriz** deve-se **selecionar os turnos** em que ela é ofertada; selecionar
dois turnos gera **duas matrizes irmãs** (componentes duplicados), uma por turno. Assim, o mesmo
professor pode ser **alocado nas disciplinas dos dois turnos**, e a carga horária de quem leciona
nos dois **soma** (carga real dobrada).

**Decisões travadas com o usuário (2026-07-16):**
1. **Onde os turnos ofertados moram:** no **`CourseUnit`** (curso na unidade) — cada unidade define
   quais turnos oferta para aquele curso. (Não em `Course` global; não na matriz.)
2. **Fluxo de alocação entre irmãs:** **independente** — cada turno é alocado manualmente; as
   matrizes-irmãs apenas aparecem **agrupadas** lado a lado na tela. Sem espelhamento automático.
3. **Contagem de CH (mesmo prof, mesma disciplina, 2 turnos):** **em dobro (2×)** — soma a CH das
   duas matrizes (é aula real nos dois turnos).

## Achados da exploração que moldam o desenho

- `turno` só existe em `CurriculumMatrix` (`apps/courses/models.py:129-135`, choices `M/T/N`,
  nullable). `Course` (`:5-26`) e `CourseUnit` (`:28-51`) **não** têm turno.
- **Alocação = FK `docente` em `MatrixComponent`** (`apps/courses/models.py:197-204`), por
  componente, escopada a uma matriz. Não há tabela de alocação separada.
- **`Professor.ch_alocada`** (`apps/professors/models.py:192-210`) soma `ha_semanal` de
  `componentes_matriz.filter(matriz__is_vigente=True)`, deduplicando por `componente_curricular_id`
  **apenas quando `comp.compartilhado`**; caso contrário a chave é `comp.pk`.
  → **Consequência-chave:** matrizes-irmãs por turno **não** são `compartilhado` (esse flag é
  cross-*curso*, `:205-213`, e a validação proíbe mesmo curso, `:258-261`). Logo cada irmã tem
  `MatrixComponent` com pk distinto e o `ch_alocada` **já soma 2×** naturalmente. **O "2×" sai de
  graça — nenhuma mudança em `ch_alocada`.**
- **A tela de alocação já lista um bloco por (curso, turno)** e ordena por `turno`
  (`apps/allocations/views.py:41-49`), exibindo `get_turno_display` quando há turno
  (`templates/allocations/alloc_curricular.html:74-75`). Os selects de professor filtram por
  `unidade_principal_id` (`:68-75`) → o mesmo professor aparece nas duas irmãs (mesma unidade) e
  pode ser alocado em ambas. **A alocação independente entre irmãs já funciona assim que as duas
  matrizes existem.**
- **`AlocacaoCurricular`** (consolidação p/ SEI) já é chaveada por
  `unique_together = ('curso', 'semestre', 'turno')` (`apps/allocations/models.py:19-21,45`) →
  cada irmã (turno próprio) mapeia para sua própria consolidação. **Alinhado.**
- **CORR-011 já removeu o auto-arquivamento** na publicação (`apps/courses/views.py:205-210`) →
  matrizes-irmãs por turno **já coexistem** como vigentes. Esta feature é o passo seguinte natural.
- Duplicação hoje é **client-side** (JS) via `DadosMatrizCopiarView` (`views.py:528-558`); copia só
  identidade do componente + cargas (não copia `docente` nem `turno`). O `duplicar_de` do form é
  gatilho de UI, nunca lido no `form_valid`.
- `professors.Availability.turno` e `AlocacaoCurricular.turno` são campos de turno **independentes**
  (disponibilidade do professor / cópia denormalizada) — **não confundir** com o turno da matriz.

## Arquitetura da mudança

### 1. Turnos ofertados no `CourseUnit`
- **`apps/courses/models.py`** — novo model filho **`TurnoOfertado`** (ou child table equivalente):
  `course_unit` FK→`CourseUnit` (related_name=`turnos_ofertados`), `turno` char `M/T/N`,
  `unique_together = ('course_unit', 'turno')`. Mantém o padrão M/T/N já usado e é
  DB-portável/queryável (evita ArrayField Postgres-específico). Migration nova.
  - Alternativa mais enxuta (se preferir menos tabelas): `ArrayField` de choices em `CourseUnit`
    (Postgres/Supabase suporta) — decidir na implementação; **recomendação = child model**.
- **UI de cadastro do CourseUnit** (onde a unidade/DESUP habilita o curso): checkboxes "Turnos
  ofertados" (Manhã/Tarde/Noite). Fonte única da verdade de "quais turnos este curso roda nesta
  unidade".

### 2. `turno` como cidadão de primeira classe na matriz
- **`apps/courses/forms.py`** `CurriculumMatrixForm` (`:26-44`):
  - **Na criação:** adicionar um **multi-select de turnos** (`forms.MultipleChoiceField`,
    checkboxes), **restrito aos turnos ofertados** pelo `CourseUnit` do curso/unidade escolhidos
    (populado via JS ou no `__init__` a partir da seleção). Não é o campo `turno` do model
    diretamente — é o seletor que dispara o fan-out (§3).
  - **Na edição:** cada matriz tem **um** turno fixo (definido na criação); exibir como
    read-only (o turno não muda depois — muda-se criando/arquivando matriz).
- **`apps/courses/models.py`** `CurriculumMatrix`: adicionar **`grupo_turno`** (UUID nullable) para
  **ligar as irmãs criadas juntas** — necessário para operações conjuntas futuras (arquivar o
  grupo, navegar irmãs, virada de semestre). Migration.

### 3. Fan-out na criação: N turnos → N matrizes irmãs
- **`apps/courses/views.py`** `CurriculumMatrixFormsetMixin.form_valid` (`:191-219`):
  - Ler a lista de turnos selecionados. Gerar um `grupo_turno` (UUID) comum.
  - Para **cada turno**: salvar uma cópia da matriz (`nome` sufixado pelo turno, ex.
    `MC-ADS-2026-M` / `-N`, ou mesmo nome + turno distinto), com `turno` setado e `grupo_turno`
    comum, e **clonar os componentes do formset** para cada irmã (mesma lógica de componentes,
    `docente` vazio — alocação é posterior e independente).
  - Um turno selecionado → comportamento atual (uma matriz), agora com `turno` preenchido.
  - Tudo em `transaction.atomic()`.
- Reaproveitar/estender a lógica de cópia de componentes já existente (o clone server-side dos
  `MatrixComponent`), evitando duplicar regra de `save()` (que já deriva `codigo`/CH semanal).

### 4. Filtro de turno na listagem (hoje órfão)
- **`apps/courses/views.py`** `CurriculumMatrixListView._apply_filters` (`:63-96`): passar a ler
  `request.GET.get('turno')` e aplicar `qs.filter(turno=...)`. O `<select name="turno">` já existe
  no template (`templates/courses/matrix/list.html:145-158`) — só falta honrar no servidor.
- Exibir o turno nas linhas/cards da lista (badge "Manhã/Tarde/Noite").

### 5. Agrupamento visual na tela de alocação
- **`templates/allocations/alloc_curricular.html`** (`:68-`): agrupar os blocos por **curso** com
  **sub-cabeçalhos por turno** (as matrizes já vêm ordenadas por `curso__nome, turno` —
  `allocations/views.py:45`). Deixar visível que são o mesmo curso em turnos diferentes.
  Opcional: no `matrizes_data`, agrupar por `curso` para render aninhado (curso → [turnos]).
- **Nenhuma** mudança na semântica de alocação: cada componente é alocado por si (decisão
  "independente"). O mesmo professor já aparece nos selects das duas irmãs.

### 6. CH 2× — confirmar por teste (sem mudança de código)
- `ch_alocada` **já** soma as duas irmãs (não são `compartilhado`). Adicionar **teste de
  regressão** que trava isso: professor alocado na mesma disciplina em 2 matrizes irmãs (turnos M
  e N, mesmo curso/unidade, ambas vigentes) → `ch_alocada == 2 × ha_semanal`. Guardar contra
  alguém marcar as irmãs como `compartilhado` no futuro (que colapsaria para 1×).

### 7. Pontos a revisitar (dependências)
- **Seeds** (`seeds/*.py`) fixam `turno='N'` — ao tornar turno central, revisar seeds para refletir
  turnos ofertados por CourseUnit. Matrizes antigas sem turno permanecem válidas (`turno` nullable);
  opcional: data migration de backfill (fonte de verdade incerta → deixar nulo e tratar na UI).
- **Duplicação/importação** (`DadosMatrizCopiarView` `:549-557`, `ImportPreviousMatrixView`
  `:461-470`): não carregam turno (ok — turno é escolhido na criação). Sem mudança obrigatória.
- **Virada de semestre** ([plano-virada-semestre.md](./plano-virada-semestre.md)): a virada arquiva
  **todas** as vigentes de uma vez → irmãs por turno arquivam juntas naturalmente. O `grupo_turno`
  (§2) pode ajudar em relatórios/PDF por curso. Manter os dois planos coerentes.

## Arquivos que serão tocados (na implementação futura)
- **Novos:** model `TurnoOfertado` + migration; migration de `grupo_turno`; testes novos.
- **Editados:** `apps/courses/models.py` (grupo_turno, TurnoOfertado), `apps/courses/forms.py`
  (multi-select de turnos + restrição por CourseUnit), `apps/courses/views.py`
  (`form_valid` fan-out; `_apply_filters` turno), `templates/courses/matrix_form.html` +
  `matrix/list.html`, `templates/allocations/alloc_curricular.html` (agrupamento),
  UI de cadastro de CourseUnit (turnos ofertados), `apps/courses/tests.py` +
  `apps/professors`/integração (CH 2×).

## Verificação (na implementação futura)
- `makemigrations` + `migrate` (TurnoOfertado, grupo_turno).
- `manage.py check` limpo.
- Testes: fan-out cria N irmãs com `turno`/`grupo_turno` corretos e componentes clonados;
  `_apply_filters` filtra por turno; **`ch_alocada` 2×** para prof em 2 turnos; restrição de turnos
  ao que o CourseUnit oferta.
- Manual: cadastrar curso na unidade com Manhã+Noite → criar matriz selecionando os 2 turnos →
  conferir 2 matrizes irmãs vigentes (uma por turno, componentes iguais, sem docente) → alocar o
  mesmo professor na mesma disciplina nos 2 turnos → conferir `ch_alocada` somando as duas → filtro
  de turno na lista → agrupamento por curso/turno na tela de alocação.

## Fora de escopo / notas
- **Implementação fica para depois** — este documento é só o planejamento.
- **Commits** — feitos só pelo usuário (constante do projeto).
- Sem espelhamento automático de docente entre irmãs (decisão "independente"). Se no futuro
  quiserem "aplicar aos 2 turnos" num clique, é um follow-up sobre `grupo_turno` + a view de
  alocação — não entra agora.
- Não confundir o `turno` da matriz com `AlocacaoCurricular.turno` (consolidação) nem com
  `Availability.turno` (disponibilidade do professor).
