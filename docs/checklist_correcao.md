# Checklist de correções — HARPIA-DESUP

Registro central de correções/ajustes a fazer no sistema. Cada item tem um ID estável
(`CORR-NNN`), status e prioridade, para acompanhamento e distribuição entre agentes/sessões.

> **Commits são feitos somente pelo usuário.** Ao corrigir um item, atualize o **Status** aqui e
> aponte os arquivos tocados.

## Convenções

**Status:** 🔴 Pendente · 🟡 Em andamento · 🟢 Corrigido · ⚪ Descartado · 📄 Planejado (feature grande, documento separado em `docs/planejamento/`)
**Prioridade:** 🅐 Alta · 🅑 Média · 🅒 Baixa

**Como adicionar um item novo:** copie o template abaixo, use o próximo ID livre, e acrescente uma
linha no Índice.

```md
## CORR-NNN — <título curto>
- **Status:** 🔴 Pendente · **Prioridade:** 🅑 Média · **Área:** <app/tela>
- **Arquivos:** `caminho/arquivo.py:linha`
- **Problema:** <o que está errado e o efeito observável>
- **Correção proposta:** <como corrigir>
- **Notas:** <riscos, dependências, links> (opcional)
```

## Índice

| # | Item | Área | Prioridade | Status |
|------|------|------|:---:|:---:|
| CORR-001 | `ch_justificada` soma horas solicitadas em vez das aprovadas | Professores / Extracurricular | 🅐 | 🟢 |
| CORR-002 | Seleção "Sem professor" não fica visível (idêntica ao estado vazio) | Alocação (front) | 🅑 | 🟢 |
| CORR-003 | Dropdown de docente é cortado/some nas últimas linhas da matriz | Alocação (front) | 🅐 | 🟢 |
| CORR-004 | HTTP 500 ao emitir parecer (misturar aprovado/indeferido do mesmo professor) — `ch_aprovada` retorna `float` e `Decimal` | Extracurricular / Parecer DESUP | 🅐 | 🟢 |
| CORR-005 | Sem observabilidade de erros 500: nenhum email/log ao super admin (500.html mente "equipe notificada") | Infra / Observabilidade | 🅐 | 🟢 |
| CORR-006 | Cobertura de testes dos pareceres DESUP (todas as combinações/sequências) | Testes / Extracurricular | 🅑 | 🟢 |
| CORR-007 | Ao criar matriz, bloquear todos os campos do componente exceto Disciplina e Período | Matrizes / Form | 🅑 | 🟢 |
| CORR-008 | Unidade não pode editar matriz e não deve ver rascunhos (só DESUP) | Matrizes / Permissões | 🅐 | 🟢 |
| CORR-009 | Campo "Código da Disciplina" estreito — não mostra o código inteiro | Matrizes / Form (front) | 🅒 | 🟢 |
| CORR-010 | Ícones do menu lateral não centralizados no rail recolhido | Layout / Navegação (front) | 🅒 | 🟢 |
| CORR-011 | Duplicar matriz arquiva a original — deveriam coexistir como vigentes | Matrizes / Publicação | 🅐 | 🟢 |
| CORR-012 | Falta ação manual de arquivar/reativar matriz | Matrizes / Ações | 🅑 | 🟢 |
| CORR-013 | Turnos por curso: matrizes-irmãs por turno + alocação independente (feature grande, planejada) | Matrizes / Turnos | 🅐 | 📄 |
| CORR-014 | Pop-up "Janela de entrega fechada" duplicado (alocação e extracurricular, perfil unidade) | Janela / Front | 🅑 | 🟢 |
| CORR-015 | Filtro "Sem registro" não retorna nada (value `Sem registro` × token `sem_registro`) | Extracurricular / Filtro | 🅐 | 🟢 |
| CORR-016 | Título da página de Alocação mostra "HARPIA" em vez de "Alocação Curricular" | Alocação / Front | 🅒 | 🟢 |
| CORR-017 | Menu de usuário: mostra "ADMIN Alberto" (não o email) e "Meu Perfil" leva à troca de senha | Conta / Perfil | 🅑 | 🟢 |
| CORR-018 | Troca de senha exige digitar email manualmente (redundante); usar email do usuário logado | Conta / Senha | 🅑 | 🟢 |
| CORR-019 | Admin (superuser) às vezes cai no dashboard DESUP ao entrar no /admin/ — deveria ficar só no admin Django | Conta / Roteamento | 🅑 | 🟢 |
| CORR-020 | Envio do link de troca de senha sem rate-limit | Conta / Senha | 🅑 | 🟢 |
| CORR-021 | Perfil ADMIN (TI DESUP) não era oficial — superuser misturado com a operação da DESUP | Conta / Perfis | 🅐 | 🟢 |
| CORR-022 | Diretório `templates/extracurricular/` órfão (código morto) | Manutenção / Templates | 🅒 | 🟢 |
| CORR-024 | Escopo da janela de entrega não estava explícito (professor fica fora) | Janela / Documentação | 🅑 | 🟢 |
| CORR-023 | Item indeferido zerava toda a CH já aprovada da pendência | Extracurricular / Parecer DESUP | 🅐 | 🟢 |

---

## CORR-001 — `ch_justificada` soma horas solicitadas em vez das aprovadas
- **Status:** 🟢 Corrigido (2026-07-15) · **Prioridade:** 🅐 Alta · **Área:** Professores / Extracurricular
- **Arquivos:** `apps/professors/models.py:168` (`Professor.ch_justificada`);
  referência correta em `apps/extra_curricular/models.py:100` (`PendenciaExtra.ch_total_justificada`).
- **Problema:** `Professor.ch_justificada` agrega os valores **solicitados**
  (`OrientacaoTCC.carga_horaria`, `AtividadeExtensionista.carga_horaria`,
  `ReducaoCargaHoraria.horas_reduzidas`), enquanto o correto é usar os valores **aprovados pela
  DESUP** (`ch_aprovada` de cada item). Isso é **inconsistente** com
  `PendenciaExtra.ch_total_justificada`, que já usa `ch_aprovada`. Efeito: quando a DESUP aprova
  menos horas do que o solicitado, o total do professor no dashboard fica **superestimado**.
- **Correção proposta:** fazer `ch_justificada` somar `ch_aprovada`. Como `ch_aprovada` é
  *property* (não coluna), não dá para usar `Sum` no banco — reaproveitar a lógica já pronta:
  ```python
  # já filtrando por status=APROVADO + semestre atual (ver escopo por semestre):
  return sum(
      p.ch_total_justificada
      for p in self.pendencias_extra.filter(semestre=semestre_atual())
  )
  ```
  (`ch_total_justificada` já retorna 0 quando a pendência não está `APROVADO` e já soma
  `ch_aprovada` de TCC + extensão + redução — elimina a duplicação de lógica.)
- **Notas:** manter o escopo por semestre já implementado (ver
  `memory/justificativa-extra-escopo-semestre.md`). Atualizar/estender os testes de
  `apps/extra_curricular/tests.py` que hoje asseguram `ch_justificada` (verificar se algum teste
  fixa horas solicitadas ≠ aprovadas). Rodar `apps.professors` + `apps.extra_curricular` + `apps.core`.
- **Resolução (2026-07-15):**
  - `apps/professors/models.py` — `ch_justificada` agora faz
    `sum(float(p.ch_total_justificada) for p in self.pendencias_extra.filter(semestre=semestre_atual()))`,
    passando a somar as horas **aprovadas** (`ch_aprovada`) via `ch_total_justificada` (que já
    ignora pendências não-APROVADAS). Mantido o escopo por semestre e o `try/except` de segurança.
  - `apps/extra_curricular/tests.py` — novo teste
    `test_ch_justificada_usa_horas_aprovadas_nao_solicitadas` (solicita 8 orientandos = 4.0h, aprova
    2 = 1.0h → total do professor = **1.0h**, não 4.0h).
  - Verificação: `apps.extra_curricular` + `apps.professors` **15/15** verdes; `apps.core` +
    `apps.courses` **48/48** verdes; `manage.py check` sem problemas.
  - Observação: `ch_total_justificada` ainda tem a inconsistência de tipo `float`/`Decimal` da
    **CORR-004** (aqui blindada pelo `float(...)` + `try/except`); a normalização de tipo será
    feita na CORR-004.

## CORR-002 — Seleção "Sem professor" não fica visível (idêntica ao estado vazio)
- **Status:** 🟢 Corrigido (2026-07-16) · **Prioridade:** 🅑 Média · **Área:** Alocação — front (autocomplete de docente)
- **Arquivos:** `templates/allocations/alloc_curricular.html:114-115` (input + placeholder),
  `:131-135` (opção fixa `SEM_PROFESSOR`), `:261` (`_bindEvents`, define `label`),
  `:362-396` (`_selectValue`, faz reload).
- **Problema:** ao escolher **"Sem professor"** no seletor, a JS define o rótulo do input como
  string vazia (`opt.dataset.value === 'SEM_PROFESSOR' ? '' : ...`) e recarrega a página. Após o
  reload, o input volta **vazio com o placeholder "Escolha uma opção"** — exatamente igual ao
  estado de um componente que **nunca** foi escolhido. Resultado: a escolha "Sem professor" não
  produz nenhuma mudança visível (parece que o clique não fez nada) e não há como distinguir
  "marquei explicitamente sem professor" de "ainda não mexi".
- **Correção proposta:** dar um estado visual próprio ao `SEM_PROFESSOR` (distinto do vazio/default).
  Ex.: exibir o texto "Sem professor" no input (ou um badge/ícone `ph-user-minus`) e um estilo
  próprio (ex.: `border-slate-300 bg-slate-50` com texto marcado), diferente do placeholder
  "Escolha uma opção". Ajustar o rótulo no clique (linha 261) e o render inicial (linhas 108-118) —
  hoje o template só trata `comp.docente` e `NAO_OFERECIDA`; falta o ramo explícito de
  `SEM_PROFESSOR`. Conferir como o backend distingue "sem professor escolhido" de "nunca alocado"
  (ver `data-current-id` na linha 104 e a view `alocar_docente_componente`).
- **Notas:** puramente front + template; não altera regra de negócio. Validar visualmente nos 3
  estados (com docente / sem professor / não oferecido).
- **Resolução (2026-07-16):**
  - `templates/allocations/alloc_curricular.html` — o estado **`SEM_PROFESSOR`** passou a ter um
    ramo próprio de renderização, distinto do vazio/placeholder (antes caía no `{% else %}` e
    renderizava input vazio com "Escolha uma opção"). Como o `default` do model é `SEM_PROFESSOR`,
    todo componente sem docente agora exibe visivelmente esse estado:
    - `data-current-nome` (linha ~105): novo ramo `{% elif comp.status == 'SEM_PROFESSOR' %}Sem professor`
      (usado por `_close()` para restaurar o rótulo quando o input é limpo sem seleção).
    - `.ac-input-wrap` (linha ~109): novo ramo de estilo `border-slate-300 bg-slate-50` para
      `SEM_PROFESSOR` (distinto do `border-slate-200 bg-slate-50` do vazio e do `bg-slate-100` de
      `NAO_OFERECIDA`); adicionado ícone `ph-user-minus` (mesmo do dropdown) antes do input.
    - `.ac-input` (linhas ~114-117): novo ramo de cor `text-slate-500 font-semibold` e `value="Sem professor"`
      para `SEM_PROFESSOR`.
  - `templates/allocations/alloc_curricular.html` (JS do controlador):
    - `_bindEvents` (linha ~261): removido o caso especial `opt.dataset.value === 'SEM_PROFESSOR' ? '' : ...`
      — o rótulo agora vem sempre de `opt.textContent.trim()`, ou seja, "Sem professor" (antes ficava vazio).
    - Botão limpar `.ac-clear` (linha ~274): `_selectValue('SEM_PROFESSOR', '')` → `_selectValue('SEM_PROFESSOR', 'Sem professor')`
      (feedback visual imediato coerente até o reload).
  - Verificação: `manage.py check` sem problemas; `apps.allocations` **5/5** verdes (testes de model
    SEI, não afetados pela mudança de front). Backend (`AlocarDocenteComponenteView`) já persistia
    `status=SEM_PROFESSOR` corretamente — nenhuma alteração de regra de negócio.
  - Rollback: reverter as edições em `templates/allocations/alloc_curricular.html`
    (`git checkout -- project_root/templates/allocations/alloc_curricular.html`); é o único arquivo de
    código tocado. Reverter também esta seção do checklist se desejado.

## CORR-003 — Dropdown de docente é cortado/some nas últimas linhas da matriz
- **Status:** 🟢 Corrigido (2026-07-16) · **Prioridade:** 🅐 Alta · **Área:** Alocação — front (autocomplete de docente)
- **Arquivos:** `templates/allocations/alloc_curricular.html:80` (wrapper com overflow),
  `:101` (`.ac-docente relative`), `:128-129` (`.ac-dropdown absolute ... mt-1`),
  `:296-308` (`_open`/`_close`, sem lógica de flip).
- **Problema:** o container da tabela usa `overflow-hidden overflow-x-auto` (linha 80). Como um
  dos eixos vira contexto de scroll/clip, o `overflow-y` não permanece `visible` (o CSS o computa
  para `auto`), então o dropdown posicionado em `absolute` (que **sempre** abre para baixo, com
  `mt-1`) é **cortado** nas linhas de baixo da matriz. Nas últimas linhas o seletor não aparece;
  em algumas linhas próximas do fim aparece parcialmente e sem barra de rolagem. Falta lógica de
  **flip**: detectar que não há espaço abaixo e abrir o dropdown **para cima**.
- **Correção proposta:** em `_open()` (linha 296), medir o espaço disponível abaixo do
  `.ac-input-wrap` (`getBoundingClientRect()` vs. altura da viewport / do container) e, quando não
  couber, abrir o dropdown para cima (ex.: alternar entre `top-full mt-1` e `bottom-full mb-1`, ou
  ajustar `style.top/bottom`). Alternativa mais robusta: renderizar o dropdown em posição `fixed`
  ancorada ao input (fora do container com overflow) para não sofrer clipping. Rever o
  `overflow-hidden` da linha 80 (trocar por algo que não corte o eixo Y, ou mover o dropdown para
  fora do container).
- **Notas:** puramente front. Testar em matriz longa (rolar até as últimas linhas) e em telas
  baixas; validar que o dropdown continua alinhado ao input e fecha corretamente ao clicar fora.
- **Resolução (2026-07-16):** `templates/allocations/alloc_curricular.html` (bloco `extra_js`):
  `_open()` chama novo `_position()` e registra listeners de `scroll` (captura) + `resize`;
  `_close()` remove-os; `_position()` posiciona o `.ac-dropdown` em `position: fixed` ancorado ao
  input (escapa do container com overflow) com **flip para cima** quando não há espaço abaixo
  (mede `getBoundingClientRect` vs `innerHeight`/`offsetHeight`); `_renderResults()` reancora após
  resultados assíncronos. Linha 80 (overflow) e o scroll horizontal preservados; dropdown segue
  filho de `.ac-docente` (clicar-fora intacto). Verificação: `manage.py check` sem problemas.
  Relatório: `docs/relatorios/CORR-003-dropdown-docente-cortado.md`.

## CORR-004 — HTTP 500 ao emitir parecer misturando aprovado/indeferido do mesmo professor
- **Status:** 🟢 Corrigido (2026-07-16) · **Prioridade:** 🅐 Alta · **Área:** Extracurricular — Parecer DESUP
- **Relato (cliente/DESUP):** na fase de testes, o Coord (DESUP) **aprovou** uma orientação de TCC
  de um professor e, em seguida, tentou **indeferir** esse mesmo professor numa atividade
  extensionista. Resultado: tela branca *"Ocorreu um problema / Não foi possível processar sua
  solicitação"* (HTTP 500). URL:
  `/extracurriculares/pendencias/1/parecer/extensao/1/`.
- **Arquivos:**
  - Raiz (tipos inconsistentes) — `apps/extra_curricular/models.py:192-199`
    (`OrientacaoTCC.ch_aprovada`), `:287-294` (`AtividadeExtensionista.ch_aprovada`),
    `:366-371` (`ReducaoCargaHoraria.ch_aprovada`).
  - Onde estoura de fato — `apps/extra_curricular/forms.py:50-55`
    (`BasePendenciaFormSet.clean`, acumulação de `ch_outros` **sem cast**).
  - Caminho do parecer (view do relato) — `apps/extra_curricular/views.py:705-729`
    (`_BaseParecerView.post`) e `:683-696` (`_ch_aprovada_outros`, este **já** faz cast correto).
- **Problema (causa-raiz):** a *property* `ch_aprovada` **retorna tipos diferentes** conforme o
  caminho: `float` quando a DESUP preenche os "aprovados" (`round(n * 0.5, 1)`) e `Decimal` quando
  cai no fallback `horas_aprovadas`/`carga_horaria` (campos `DecimalField`). Ao **misturar** itens
  de tipos diferentes (um item aprovado com nº aprovado → `float`; outro calculado → `Decimal`), a
  soma `float + Decimal` levanta
  `TypeError: unsupported operand type(s) for +: 'decimal.Decimal' and 'float'` → 500. Isso ocorre
  de forma **garantida** em `BasePendenciaFormSet.clean` (`ch_outros = 0; ch_outros += sum(item.ch_aprovada …)`
  somando os **outros** dois tipos sem converter). O endpoint de parecer em si
  (`_ch_aprovada_outros`) já converte para `float` — por isso o **traço exato** do 500 relatado
  **não pôde ser confirmado estaticamente** (depende do estado/dados e da ausência de log — ver
  **CORR-005**); a inconsistência de tipos é a suspeita nº 1 e precisa ser normalizada de qualquer
  forma.
- **Correção proposta:**
  1. **Normalizar `ch_aprovada`** para retornar **sempre `float`** (ou sempre `Decimal`) nas 3
     models — envolver os retornos de `DecimalField` em `float(...)` (ou converter os `round()` em
     `Decimal`). Padronizar também `ch_total_justificada` (`models.py:99-107`) e o cast já feito em
     `_ch_aprovada_outros` para o mesmo tipo.
  2. **Blindar `BasePendenciaFormSet.clean`** (`forms.py:50-55`) fazendo `float(item.ch_aprovada)`
     na soma (mesmo padrão de `_ch_aprovada_outros`).
  3. Confirmar com o traceback real (após **CORR-005**) que não há outro ponto de mistura
     `Decimal/float` no fluxo de parecer/detalhe.
- **Notas:** regra de negócio **não muda** (só o tipo numérico). Cobrir com testes — ver **CORR-006**.
  Dado que o cliente ficou bloqueado, priorizar junto de CORR-005 (para capturar o traceback exato).
- **Resolução (2026-07-16):** `ch_aprovada` **normalizada para sempre `float`** (menor ripple; os
  consumidores do parecer já casteavam).
  - `apps/extra_curricular/models.py` — as 3 properties `ch_aprovada` (TCC ~192, Extensão ~289,
    Redução ~369) envolvem retornos de `DecimalField` em `float(... or 0)`; `ch_total_justificada`
    (~99) soma com `float(...)` por item.
  - `apps/extra_curricular/forms.py` — `BasePendenciaFormSet.clean` (~49-55): `ch_outros = 0.0` e
    `sum(float(item.ch_aprovada) ...)` no ponto exato do crash.
  - `apps/extra_curricular/views.py` — sem mudança (já convertia).
  - `apps/extra_curricular/tests.py` — `ChAprovadaTipoConsistenteTests` (4): tipo float nos 3
    modelos; soma mista sem `TypeError`; `formset.clean` com tipos mistos; e2e aprovar TCC →
    indeferir Extensão do mesmo professor retorna **302** (não 500) e consolida `INDEFERIDO`.
  - Verificação: `apps.extra_curricular` **19/19** verdes; `manage.py check` limpo.
    Relatório: `docs/relatorios/CORR-004-ch-aprovada-tipo-float-decimal.md`.

## CORR-005 — Sem observabilidade de erros 500 (notificar/logar para o super admin/DEV)
- **Status:** 🟢 Corrigido (2026-07-16) · **Prioridade:** 🅐 Alta · **Área:** Infra / Observabilidade
- **Arquivos:** `config/settings/base.py:120-131` (bloco de e-mail; **não** há `LOGGING`, `ADMINS`
  nem `SERVER_EMAIL` em nenhum settings); `config/settings/development.py`;
  `templates/500.html` (mensagem "Nossa equipe já foi notificada"); `config/urls.py` (handler500).
- **Problema:** não existe **nenhuma** captura/notificação de erros. Sem `ADMINS` + `LOGGING`, o
  e-mail padrão de 500 do Django **nunca** dispara; logo a promessa do `500.html`
  (*"Nossa equipe já foi notificada"*) é **falsa** — o super admin (DEV) não fica sabendo dos erros
  (foi o que aconteceu no CORR-004: o 500 ocorreu e ninguém foi avisado, sem stack trace acessível).
- **Correção proposta:**
  1. Definir **`ADMINS`** (e-mail do DEV) e **`SERVER_EMAIL`**/`DEFAULT_FROM_EMAIL` nos settings.
  2. Adicionar dict **`LOGGING`** com `django.request` → `AdminEmailHandler` (e-mail no 500) +
     handler de arquivo/console (traceback local). `include_html=True` no e-mail para stack completo.
  3. Garantir que o **SMTP de produção** (Render) esteja de fato configurado por env
     (`EMAIL_HOST/PORT/USER/PASSWORD/TLS`) — hoje o default é `localhost:25`, que no Render não
     envia; validar o envio real.
  4. (Opcional, "log de fácil acesso" pedido) persistir os erros num registro consultável pelo
     super admin — reaproveitar `AuditoriaGlobal` (`apps/core/models.py`) ou um model `ErrorLog`
     dedicado, com uma tela/lista só-DEV; assim o acesso não depende só do e-mail.
  5. Ajustar o texto do `500.html` para condizer com o que realmente acontece.
- **Notas:** é o item que **destrava o diagnóstico** de CORR-004 e de erros futuros — priorizar.
  Cuidado para o `AdminEmailHandler` não vazar dados sensíveis por e-mail (avaliar `include_html`
  e filtros); considerar rate-limit/agrupamento se o volume crescer. Testar com um erro proposital
  em staging.
- **Resolução (2026-07-16):**
  - `config/settings/base.py` — bloco "Observabilidade de erros 500": helper `_parse_admins()` +
    `ADMINS` (de env `ADMINS_EMAILS`, aceita `"Nome <email>,email2"`; vazio por padrão, **sem email
    hardcoded**), `MANAGERS`, `SERVER_EMAIL`, `ADMIN_EMAIL_INCLUDE_HTML` (default False),
    `DJANGO_LOG_LEVEL`, `LOG_DIR` (try/except OSError). `LOGGING` dictConfig: handlers `console`,
    `file` (RotatingFileHandler ERROR), `mail_admins` (`AdminEmailHandler` ERROR + `require_debug_false`);
    `django.request` → console+file+**mail_admins**.
  - `templates/500.html` — removida a frase falsa "Nossa equipe já foi notificada"; mensagem neutra.
  - **Env vars novas:** `ADMINS_EMAILS` (obrigatória em prod p/ email), `SERVER_EMAIL` (opcional),
    `ADMIN_EMAIL_INCLUDE_HTML` (opcional), `DJANGO_LOG_LEVEL` (opcional). Em prod o SMTP
    (`EMAIL_HOST/PORT/USER/PASSWORD/TLS`) precisa estar setado (default `localhost:25` não envia no Render).
  - Notificação: prod (`DEBUG=False`) 500 → email com traceback aos ADMINS + log; dev email inerte
    (`require_debug_false`), só console+arquivo (não exige SMTP).
  - Verificação: `manage.py check` **0 issues** em development e production; smoke test de logging OK.
    Relatório: `docs/relatorios/CORR-005-observabilidade-500.md`.

## CORR-006 — Cobertura de testes dos pareceres DESUP (todas as combinações/sequências)
- **Status:** 🟢 Corrigido (2026-08-01) · **Prioridade:** 🅑 Média · **Área:** Testes / Extracurricular
- **Arquivos:** `apps/extra_curricular/tests.py` (estender); alvo do fluxo:
  `apps/extra_curricular/views.py:699-747` (parecer views) e `forms.py:33-98`
  (`BasePendenciaFormSet.clean`).
- **Problema:** o fluxo de parecer (Aprovar/Indeferir por item, com/sem "aprovados" preenchidos)
  não tem cobertura suficiente — o 500 do CORR-004 passou para o cliente. Faltam casos que
  exercitem a **mistura de tipos** e as **sequências** entre itens do mesmo professor.
- **Casos a cobrir (mínimo):**
  - Aprovar TCC (com `num_orientandos_aprovados`) e **depois** indeferir Extensão do mesmo
    professor — **regressão direta do CORR-004** (não pode dar 500).
  - Cada tipo (TCC / Extensão / Redução) × cada parecer (Aprovado / Indeferido / Pendente),
    com e sem os campos "aprovados"/"horas_aprovadas" preenchidos.
  - Combinações de 2–3 itens do mesmo professor com pareceres divergentes → validar
    `sincronizar_status_pendencia` (qualquer indeferido ⇒ INDEFERIDO; todos aprovados ⇒ APROVADO).
  - Estouro de limite de horas extra (`limite_horas_extra_efetivo`) → mensagem de erro, sem 500.
  - Consistência de tipo de `ch_aprovada`/`ch_total_justificada` (assert que a soma nunca levanta
    `TypeError` e que o total bate com o esperado).
  - Permissão: só **DESUP** emite parecer (perfis Coord/Unidade recebem 403/redirect).
- **Notas:** rodar `apps.extra_curricular` + `apps.professors` + `apps.core`. Estes testes
  validam a correção do CORR-004 e evitam regressão futura.
- **Resolução (2026-08-01):**
  - `apps/extra_curricular/tests.py` — nova classe `ParecerDesupCoberturaTests` (13 testes),
    com helper `_post_parecer(tipo, item, parecer, aprovados=...)` que monta o payload com o
    prefixo real de cada form (`ptcc-<pk>`, `pext-<pk>`, `pred-<pk>`):
    - matriz **3 tipos × 3 pareceres**, com e sem os campos "aprovados" preenchidos
      (2 testes com `subTest`, 18 combinações);
    - sequências do mesmo professor: aprovar TCC → indeferir Redução; 3 itens todos aprovados
      ⇒ `APROVADO`; 1 indeferido entre 3 ⇒ `INDEFERIDO`; ordem inversa dá o mesmo resultado;
      item `PENDENTE` mantém a pendência em `ENVIADO`;
    - estouro de `limite_horas_extra_efetivo`: mensagem de erro, **302 e parecer não gravado**
      (não 500), inclusive somando os demais itens já aprovados;
    - consistência de tipo de `ch_aprovada` (regressão do CORR-004): `float` em todos os
      caminhos e `ch_total_justificada` sem `TypeError`;
    - permissão: coordenador de unidade recebe **403**, anônimo é redirecionado ao login e
      item de outra pendência dá **404**.
  - Verificação: `apps.extra_curricular` verde.

## CORR-007 — Ao criar matriz, bloquear todos os campos do componente exceto Disciplina e Período
- **Status:** 🟢 Corrigido (2026-08-01) · **Prioridade:** 🅑 Média · **Área:** Matrizes / Formulário de componentes
- **Arquivos:** `apps/courses/forms.py:47-120` (`MatrixComponentForm`);
  `templates/courses/matrix_form.html:79-146` (render das colunas do componente).
- **Problema:** na criação/edição de matriz, o usuário só deve **digitar/selecionar a Disciplina**
  (autocomplete → `componente_curricular`) e escolher o **Período**; os demais campos derivam da
  disciplina e **não podem ser alterados**. Hoje `codigo` e `carga_horaria_semanal` já vêm
  `disabled=True` (`forms.py:104-105`), mas **`carga_horaria` (CH Total) e `creditos` continuam
  editáveis** (`matrix_form.html:133` e `:139`) — permitindo alteração indevida.
- **Correção proposta:** no `MatrixComponentForm.__init__`, marcar também
  `self.fields['carga_horaria'].disabled = True` e `self.fields['creditos'].disabled = True`
  (mesmo padrão já usado para `codigo`/`carga_horaria_semanal` — `disabled` bloqueia na UI **e**
  ignora o valor do POST, à prova de adulteração). Garantir que os valores sejam **derivados no
  servidor**: `carga_horaria`/`creditos` a partir da disciplina — `MatrixComponentForm.clean`
  (`forms.py:107-120`) já deriva `codigo` e `carga_horaria_semanal`; estender para `carga_horaria`
  (usar `cc.carga_horaria_padrao` quando vazio) e `creditos` (regra `ch // 20`, ver
  `CurricularComponentForm.clean` em `forms.py:203-208` e `MatrixComponent.save()`), para que
  campos `disabled` (não enviados no POST) não fiquem nulos.
- **Notas:** a Disciplina é um input de busca (hidden `componente_curricular`) e o Período é um
  `Select` — **ambos permanecem editáveis**. Validar visualmente e testar o `save` (os campos
  bloqueados devem ser preenchidos corretamente pela derivação, sem erro de formset).
- **Resolução (2026-08-01):**
  - `apps/courses/forms.py` — `MatrixComponentForm.__init__` marca também
    `carga_horaria` e `creditos` como `disabled=True` (juntando-se a `codigo` e
    `carga_horaria_semanal`). `disabled` bloqueia na UI **e** faz o Django ignorar o valor do
    POST, à prova de adulteração.
  - `MatrixComponentForm.clean` — deriva no servidor: `carga_horaria` mantém o valor já
    gravado (edição) e cai para `cc.carga_horaria_padrao` quando vazio (criação);
    `creditos = ch // 20` e `carga_horaria_semanal = round(ch / 20, 2)`, mesma regra de
    `CurricularComponentForm.clean()` e de `MatrixComponent.save()`.
  - Guard novo: se a disciplina estiver sem CH padrão, o form levanta `ValidationError` com
    mensagem clara em vez de deixar o `save()` estourar `IntegrityError`
    (`MatrixComponent.carga_horaria` é `NOT NULL` sem default).
  - `templates/courses/matrix_form.html` — os 3 pontos de JS que preenchiam a linha passaram a
    espelhar as regras do servidor (antes escreviam **créditos** dentro do campo "CH Sem.").
  - **Efeito colateral aceito:** ao duplicar/copiar matriz, a CH do componente passa a ser a
    da disciplina (é a regra pedida: os campos derivam da disciplina).
  - `apps/courses/tests.py` — `MatrixComponentCamposBloqueadosTests` (7 testes), incluindo
    POST adulterado (`carga_horaria=999`, `creditos=99`) sendo ignorado e edição preservando
    a CH legada.
  - Verificação: `apps.courses` verde.

## CORR-008 — Unidade não pode editar matriz e não deve ver rascunhos (só DESUP)
- **Status:** 🟢 Corrigido (2026-07-15) · **Prioridade:** 🅐 Alta · **Área:** Matrizes / Permissões e visibilidade
- **Arquivos:** `apps/courses/views.py:43-44` (`MatrixBaseView.allowed_profiles`),
  `:63-93` (`CurriculumMatrixListView._apply_filters`), `:247-261`
  (`CurriculumMatrixUpdateView.dispatch`), `:266-284` (`CurriculumMatrixDetailView.get_queryset`).
- **Problema:** dois furos de permissão/visibilidade:
  1. **Edição:** `CurriculumMatrixUpdateView.dispatch` só bloqueia matrizes **não-rascunho**, mas
     **não filtra por perfil**. Como `MatrixBaseView.allowed_profiles` inclui
     `COORDENADOR_UNIDADE`, uma unidade poderia **editar** uma matriz em rascunho da sua unidade.
     A criação já é DESUP-only (`CreateView.dispatch`, `:225-229`); a edição precisa da mesma trava.
  2. **Visibilidade:** `_apply_filters` (lista) e `DetailView.get_queryset` escopam por
     `unidades=user.unidade`, mas **nunca excluem `is_rascunho=True`** quando não há filtro de
     status. Ou seja, a unidade **enxerga rascunhos** (que deveriam ser só da DESUP até publicar).
- **Correção proposta:**
  1. Em `CurriculumMatrixUpdateView.dispatch`, adicionar trava de perfil (padrão do CreateView):
     se não for `is_superuser`/`DESUP` → `messages.error` + `redirect('courses:matrix_list')`
     (*"Somente a DESUP pode editar matrizes."*).
  2. No **queryset** (fonte à prova de template) — em `_apply_filters` e `DetailView.get_queryset`,
     para perfis não-DESUP acrescentar `.exclude(is_rascunho=True)` (ou `.filter(is_rascunho=False)`).
     Assim rascunhos ficam invisíveis para a unidade tanto na lista quanto no detalhe/URL direta.
- **Notas:** manter a regra já existente de que só rascunho é editável
  (`:257`) e o auto-arquivamento na publicação (`:198-209`). Cobrir com testes: (a) unidade recebe
  redirect ao tentar `matrix_update`; (b) rascunho não aparece na lista da unidade nem no detalhe
  (404/none); (c) DESUP continua vendo e editando. Rodar `apps.courses`.
- **Resolução (2026-07-15):**
  - `apps/courses/views.py` — `CurriculumMatrixUpdateView.dispatch` agora exige DESUP/superuser
    (redirect + *"Somente a DESUP pode editar matrizes."*) **antes** da checagem de rascunho;
    `CurriculumMatrixListView._apply_filters` e `CurriculumMatrixDetailView.get_queryset` passaram a
    `.exclude(is_rascunho=True)` para perfis não-DESUP (à prova de `?status=rascunho` e de acesso
    direto por URL → 404 no detalhe).
  - `apps/courses/tests.py` — nova classe `MatrixPermissaoUnidadeTests` (5 testes): unidade não
    edita (redirect), DESUP edita rascunho (200), rascunho invisível na lista da unidade (inclusive
    forçando o filtro), 404 no detalhe do rascunho para a unidade, e DESUP vê rascunho em ambos.
  - Verificação: `apps.courses` **11/11** verdes; `manage.py check` sem problemas.
  - Observação: a criação já era DESUP-only (`CreateView.dispatch`, `:225-229`); o auto-arquivamento
    na publicação (`:205-209`) será **removido** na CORR-011 (decisão já fechada).

## CORR-009 — Campo "Código da Disciplina" estreito (não mostra o código inteiro)
- **Status:** 🟢 Corrigido (2026-08-01) · **Prioridade:** 🅒 Baixa · **Área:** Matrizes / Formulário (front)
- **Arquivos:** `templates/courses/matrix_form.html:80-88` (cabeçalho do grid) e `:96-146`
  (linha do componente); coluna Código = `col-span-1` (`:82` e `:119`).
- **Problema:** a coluna **Código** ocupa apenas `col-span-1` de um grid de 12 colunas — estreita
  demais para exibir o código completo da disciplina (o texto fica cortado no input).
- **Correção proposta:** alargar a coluna Código (ex.: `col-span-1` → `col-span-2`) tanto no
  cabeçalho (`:82`) quanto na linha (`:119`), **rebalanceando** os outros `col-span` para somar 12
  (p.ex. reduzir Disciplina de `col-span-4`→`col-span-3` ou CH Total de `col-span-2`→`col-span-1`).
  Alternativa: manter o span e garantir que o input não trunque (largura mínima/`title` com o valor).
  Como o campo é read-only (ver CORR-007), pode-se exibir como texto que quebra/expande.
- **Notas:** puramente layout; validar em desktop e no modo empilhado (mobile, `md:hidden` labels).
- **Resolução (2026-08-01):**
  - `templates/courses/matrix_form.html` — coluna **Código** passou de `col-span-1` para
    `col-span-2`, no cabeçalho (`:82`) e na linha do componente (`:119`). A coluna doadora foi
    **CH Total** (`col-span-2` → `col-span-1`), que com a CORR-007 virou read-only e exibe só
    um número. Os spans continuam somando **12** nas duas linhas (`md`); o empilhamento mobile
    não mudou.
  - Verificação: `apps.courses` verde; conferência dos spans na revisão adversarial.

## CORR-010 — Ícones do menu lateral não centralizados no rail recolhido
- **Status:** 🟢 Corrigido (2026-08-01) · **Prioridade:** 🅒 Baixa · **Área:** Layout / Navegação (front)
- **Arquivos:** `templates/base.html:23-33` (sidebar `w-20 hover:w-64`) e `:36-91`
  (`.sidebar-link`, classe `flex items-center gap-4 p-3`); possível CSS de apoio em
  `static/css/dashboard.css` (classe `.sidebar-desktop`/`.sidebar-link`).
- **Problema:** o menu lateral (onde ficam os botões de navegação do sistema) recolhe para `w-20`;
  os links usam `flex items-center gap-4 p-3`, que alinha o conteúdo **à esquerda**. Com o rótulo
  oculto (`hidden group-hover:block`), o ícone fica **deslocado para a esquerda** em vez de
  centralizado no espaço do rail recolhido.
- **Correção proposta:** centralizar o ícone quando recolhido **sem alterar o tamanho** (`text-2xl`
  permanece): adicionar `justify-center` no `.sidebar-link` no estado recolhido e voltar para
  `group-hover:justify-start` quando expandido (com o rótulo). Ex.: classe
  `justify-center group-hover:justify-start`; ajustar o `gap-4` para não empurrar o ícone quando o
  rótulo está oculto. Fazer o mesmo no link "Sair" (`:100-103`).
- **Notas:** puramente CSS/classes; não mexer no `text-2xl` dos ícones. Validar recolhido x
  expandido (hover) e no menu mobile (`toggleMobileSidebar`).
- **Resolução (2026-08-01):**
  - `templates/base.html` — os 8 `.sidebar-link` ganharam
    `justify-center group-hover:justify-start`; o botão **"Sair"** (que não tinha a classe)
    virou `.sidebar-link` também. O `text-2xl` dos ícones não foi alterado.
  - `static/css/dashboard.css` — dentro do `@media (max-width: 1023px)` já existente, novo
    `.sidebar-desktop .sidebar-link { justify-content: flex-start !important; }`: na gaveta
    mobile não há hover, então sem essa regra o rótulo ficaria centralizado. Mesmo padrão já
    usado para forçar `.sidebar-label` visível.
  - `apps/core/tests.py` — `SidebarIconesCentralizadosTests` (1 teste) garante que todo
    `.sidebar-link` renderizado tem o par de classes, inclusive o "Sair".
  - Verificação: `apps.core` verde.

## CORR-011 — Duplicar matriz arquiva a original (deveriam coexistir como vigentes)
- **Status:** 🟢 Corrigido (2026-07-16) · **Prioridade:** 🅐 Alta · **Área:** Matrizes / Publicação
- **Arquivos:** `apps/courses/views.py:205-209` (auto-arquivamento em
  `CurriculumMatrixFormsetMixin.form_valid`).
- **Problema:** ao **publicar** uma matriz, o sistema arquiva **todas** as outras matrizes vigentes
  do **mesmo curso**:
  ```python
  CurriculumMatrix.objects.filter(curso=self.object.curso, is_vigente=True)
      .exclude(pk=self.object.pk).update(is_vigente=False)
  ```
  Assim, ao **duplicar/triplicar** uma matriz numa mesma unidade, a matriz de origem (mesmo curso)
  vai para **Histórico/arquivada** automaticamente. O comportamento desejado é que **ambas
  permaneçam vigentes** (ex.: turnos diferentes, ou versões que devem coexistir na mesma unidade).
- **Correção proposta (decisão FECHADA):** **remover por completo** o bloco de auto-arquivamento
  por `curso` no `form_valid` (`views.py:205-209`). Ao publicar/duplicar, a matriz nova nasce
  `is_vigente=True` e **não** arquiva mais nenhuma outra. Matrizes do **mesmo curso/unidade em
  turnos diferentes** passam a **coexistir como vigentes**. O arquivamento deixa de ser automático
  e passa a acontecer só por: (a) **ação manual** de arquivar (ver **CORR-012**); e (b) **virada de
  semestre** em massa (botão na janela de entrega — feature ainda **não implementada**, planejada em
  `docs/planejamento/plano-virada-semestre.md` / memória [[virada-semestre-plano]]).
- **Guard recomendado (opcional, confirmar):** como a coexistência é **por turno**, avaliar uma
  validação que impeça **duas vigentes do mesmo `curso` + mesmo `turno` + mesma unidade** (evita
  duplicata idêntica acidental). `CurriculumMatrix` já tem o campo `turno`. Não bloquear turnos
  diferentes.
- **Notas:** decisão de negócio **confirmada pelo usuário** (2026-07-15): passa a valer **N vigentes
  por unidade/curso, uma por turno**. Dependências que hoje assumem "1 vigente" e que devem ser
  revisadas: `Professor.ch_alocada` (soma `matriz__is_vigente=True` — com múltiplas vigentes, as
  horas de turnos distintos **somam**; o método já deduplica componentes compartilhados, mas
  confirmar o comportamento desejado quando o mesmo docente aparece em 2 turnos) e listagem/dashboard.
  A virada de semestre continua coerente (arquiva **todas** as vigentes de uma vez). Cobrir com
  teste: duplicar+publicar mantém as duas `is_vigente=True`; publicar não arquiva a de origem.
  Rodar `apps.courses` + `apps.professors`.
- **Resolução (2026-07-16):**
  - `apps/courses/views.py` — `CurriculumMatrixFormsetMixin.form_valid` (ramo de publicação):
    **removido** o bloco de auto-arquivamento por curso
    (`CurriculumMatrix.objects.filter(curso=..., is_vigente=True).exclude(pk=...).update(is_vigente=False)`).
    Publicar/duplicar agora nasce `is_vigente=True` sem arquivar nenhuma outra → matrizes do mesmo
    curso/unidade coexistem como vigentes. Comentário no código apontando CORR-011/CORR-012 e virada.
  - `apps/courses/tests.py` — nova classe `MatrixCoexistenciaVigentesTests` (2 testes): publicar uma
    segunda matriz do mesmo curso **não** arquiva a de origem (`is_vigente` permanece `True`); as
    duas matrizes do curso ficam vigentes simultaneamente (`count() == 2`). POST real no `CreateView`
    com form + formset de componente válido.
  - Verificação: `apps.courses` **13/13** verdes; `apps.professors` sem testes (0), `check` limpo.
  - **Guard opcional NÃO implementado:** impedir "2 vigentes do mesmo curso+turno+unidade" depende de
    `turno` virar campo de verdade (hoje é **inerte** — fora do form, sem query, não setado ao duplicar).
    Fica para quando/se o turno for promovido a campo real. `ch_alocada` (soma `is_vigente=True`)
    passa a poder somar horas de 2 matrizes do mesmo curso — comportamento esperado com a coexistência;
    revisar caso o mesmo docente apareça em 2 turnos (acompanhamento, não bloqueia esta correção).

## CORR-012 — Falta ação manual de arquivar/reativar matriz
- **Status:** 🟢 Corrigido (2026-07-16) · **Prioridade:** 🅑 Média · **Área:** Matrizes / Ações (view + UI)
- **Arquivos:** `apps/courses/urls.py:6-30` (rotas de matriz — hoje **não há** arquivar/reativar
  nem delete de matriz), `apps/courses/views.py` (adicionar views), `apps/courses/models.py`
  (`CurriculumMatrix.is_vigente`/`is_rascunho`), `templates/courses/matrix_list.html` (botões nas
  abas Vigente/Histórico).
- **Problema:** não existe ação para **arquivar/desativar** uma matriz manualmente, nem para
  **reativar** uma já arquivada. Com o fim do auto-arquivamento (CORR-011), passa a ser necessário
  um controle manual para mover matrizes entre Vigente ↔ Histórico.
- **Correção proposta:**
  - **Views (DESUP-only, POST):** `ArquivarMatrizView` (`is_vigente=False, is_rascunho=False`) e
    `ReativarMatrizView` (`is_vigente=True, is_rascunho=False`), seguindo o padrão de permissão do
    `CreateView.dispatch` (`views.py:225-229`) e a trava de perfil da CORR-008.
  - **URLs:** `matrices/<int:pk>/arquivar/` (name `matrix_archive`) e
    `matrices/<int:pk>/reativar/` (name `matrix_reactivate`).
  - **UI:** botão **"Arquivar"** nas matrizes vigentes e **"Reativar"** nas arquivadas
    (`matrix_list.html`), com confirmação. Só DESUP vê/usa.
  - Registrar em `AuditoriaGlobal` (opcional, mas recomendado — histórico de quem arquivou/reativou).
- **Notas:** decidir a interação com CORR-011 (reativar uma matriz **não** deve arquivar as demais
  do curso). Rascunho não entra aqui (segue o fluxo de publicação). Cobrir com testes: arquivar
  tira da aba Vigente e coloca em Histórico (read-only, cadeado já existente); reativar volta para
  Vigente; permissão DESUP-only. Rodar `apps.courses`.
- **Resolução (2026-07-16):**
  - `apps/courses/views.py` — base `_MatrixDesupActionView` (DESUP/superuser-only, redirect+msg) +
    `ArquivarMatrizView` (POST `matrix_archive`: `is_vigente=False`, guarda contra rascunho e contra
    já-arquivada) e `ReativarMatrizView` (POST `matrix_reactivate`: `is_vigente=True`, **não** toca
    nas demais do curso — coerente com CORR-011). Ambas registram em `AuditoriaGlobal`
    (`MATRIZ_ARQUIVADA`/`MATRIZ_REATIVADA`) via `registrar_auditoria` (`apps/accounts/views.py`).
  - `apps/courses/urls.py` — rotas `matrices/<pk>/arquivar/` e `matrices/<pk>/reativar/`.
  - `templates/courses/matrix_list.html` + `matrix/partials/_table_body.html` — botões **Arquivar**
    (vigente) / **Reativar** (histórico) com `confirm()`, só para `is_desup`; rascunho continua com
    "Editar Rascunho"; demais perfis veem "Bloqueado".
  - `apps/courses/tests.py` — `MatrixArquivarReativarTests` (5): DESUP arquiva vigente (+auditoria),
    rascunho não arquiva, unidade não arquiva (redirect), DESUP reativa histórico (+auditoria),
    reativar não arquiva as demais do curso.
  - Verificação: `apps.courses` **18/18** verdes; `check` limpo.

## CORR-013 — Turnos por curso: matrizes-irmãs por turno + alocação independente
- **Status:** 📄 Planejado (feature grande — **NÃO implementar** solto) · **Prioridade:** 🅐 Alta ·
  **Área:** Matrizes / Turnos · Alocação
- **Documento:** plano completo em **`docs/planejamento/plano-turnos-por-curso.md`** (companheiro
  do `plano-virada-semestre.md`). Decisões travadas com o usuário em **2026-07-16**.
- **Arquivos (na implementação futura):** `apps/courses/models.py` (novo `TurnoOfertado` no
  `CourseUnit`; `grupo_turno` na `CurriculumMatrix`), `apps/courses/forms.py` (multi-select de
  turnos restrito ao ofertado), `apps/courses/views.py` (`form_valid` fan-out N turnos → N irmãs;
  `_apply_filters` passa a ler `turno`), `templates/courses/matrix_form.html` + `matrix/list.html`,
  `templates/allocations/alloc_curricular.html` (agrupar por curso/turno), UI de cadastro do
  CourseUnit, testes (`ch_alocada` 2×).
- **Problema:** turno hoje é **inerte** (só na `CurriculumMatrix`, fora do form, filtro órfão no
  servidor). Não dá para ofertar um curso em mais de um turno de forma estruturada.
- **Correção proposta (resumo — ver doc):** turnos ofertados no **CourseUnit**; ao criar matriz,
  **selecionar turnos** → **N matrizes irmãs** (componentes clonados, ligadas por `grupo_turno`);
  alocação **independente** por turno (irmãs só agrupadas na tela); CH conta **2×** para quem
  leciona nos dois turnos (já sai de graça do `ch_alocada` atual, pois irmãs não são
  `compartilhado`). Depende da CORR-011 (coexistência já habilitada) e é coerente com a virada de
  semestre (arquiva todas as vigentes juntas).
- **Notas:** implementação **posterior**; este item é só rastreio do planejamento. Não confundir o
  `turno` da matriz com `AlocacaoCurricular.turno` nem `Availability.turno`.

## CORR-014 — Pop-up "Janela de entrega fechada" duplicado
- **Status:** 🟢 Corrigido (2026-08-01) · **Prioridade:** 🅑 Média · **Área:** Janela de Entrega / Front
- **Arquivos:** aviso **1 (manter)** em `templates/base.html:251-271` (bloco `{% elif janela_fechada %}`,
  com `<form>` para `core:solicitar_chamado_alteracao` + botão **"Solicitar abertura"**); avisos
  **2 (remover)** inline: `templates/allocations/alloc_curricular.html:8-16` e
  `templates/extra_curricular/pendencia_list.html:20-28` (blocos `{% if window_fechada %}`, só texto,
  sem botão).
- **Problema:** para o perfil **UNIDADE** com janela fechada, o aviso "Janela de entrega fechada"
  aparece **duplicado** nas telas de Alocação Curricular e Alocações Extracurriculares. Duas fontes
  independentes disparam juntas: `janela_fechada` (context processor `delivery_window_context`,
  `apps/core/context_processors.py:82`, usado no `base.html`) **e** `window_fechada` (window lock da
  view, usado inline no template da tela).
- **Correção proposta:** **remover os blocos inline** `{% if window_fechada %}` de
  `alloc_curricular.html:8-16` e `pendencia_list.html:20-28`, mantendo **apenas** o de
  `base.html:251-271` (o que tem o botão "Solicitar abertura").
- **Notas:** existem avisos `{% if window_fechada %}` análogos em `pendencia_form.html`,
  `pendencia_detail.html`, `pendencia_lote.html` — **não** mexer nesses (fora do escopo pedido;
  são outras telas). Validar visualmente com usuário de unidade e janela fechada.
- **Resolução (2026-08-01):**
  - `templates/allocations/alloc_curricular.html` e `templates/extra_curricular/pendencia_list.html`
    — removidos os blocos inline `{% if window_fechada %}`. O aviso passa a existir só no
    `base.html` (o que tem o botão **"Solicitar abertura"**).
  - **Confirmação do público:** `janela_fechada` (context processor) e `window_fechada`
    (`build_window_lock_context`) ficam verdadeiros para exatamente o mesmo perfil —
    `COORDENADOR_UNIDADE`; DESUP/superuser fazem bypass (`user_can_bypass_window`). Ou seja,
    remover o inline não deixa ninguém sem aviso.
  - Os avisos análogos em `pendencia_form.html`, `pendencia_detail.html` e `pendencia_lote.html`
    **não** foram tocados (fora do escopo pedido).
  - `apps/core/tests.py` — `AvisoJanelaFechadaUnicoTests` (3 testes): o parágrafo do banner
    aparece **1×** nas duas telas, o `windowClosedNotice` do base é o único, e DESUP não vê
    banner nenhum.
  - Verificação: `apps.core` verde.

## CORR-015 — Filtro "Sem registro" não retorna nada (tela de Alocações Extracurriculares)
- **Status:** 🟢 Corrigido (2026-08-01) · **Prioridade:** 🅐 Alta · **Área:** Extracurricular / Filtro
- **Arquivos:** `apps/extra_curricular/views.py:88,106` (filtro server-side de status),
  `templates/extra_curricular/pendencia_list.html:131,138,180,340-373` (select + filtro JS
  client-side), `apps/extra_curricular/services.py:219-234` (estado "sem registro").
- **Problema:** filtrar por **"Sem registro"** não lista **nenhum** professor, mesmo com todos nesse
  estado. **Root cause:** mismatch de valor. O `<option value="Sem registro">` (`:138`) vira
  `"sem registro"` após `.strip().lower()` (view `:88`), mas a view compara com o token
  **`'sem_registro'`** (underscore, `:106`) → `"sem registro" != "sem_registro"` → nada entra em
  `filtered_data`. As outras 4 opções são palavra única e casam. Incoerência extra: o próprio option
  testa `selected` com `status_filtro == 'sem_registro'` (não bate com seu próprio value). "Sem
  registro" é **estado derivado em Python** (professor sem `PendenciaExtra` no semestre,
  `services.py:230`; filtro é `not pendencia` na `views.py:106`) — não é coluna no banco.
- **Correção proposta:** padronizar o value da opção para o token minúsculo esperado pela view
  (`sem_registro`) e **alinhar as duas camadas** de filtro: o `data-status`/JS client-side
  (`pendencia_list.html:180,340-373`) e o comparador server-side (`views.py:106`) devem consumir o
  **mesmo token** para "Sem registro". Conferir também que o filtro chega ao servidor (o `<select
  id="filter-status">` `:131` hoje **não** tem `name`/`hx-*` → só filtra no JS; decidir qual camada
  é a fonte da verdade e alinhar as duas).
- **Notas:** há **duas camadas conflitantes** (server-side em `views.py:98-114` e client-side JS no
  template). Cobrir com teste após corrigir. Verificar as demais opções (Rascunho/Pendente/
  Finalizado/Indeferido) continuam ok.
- **Resolução (2026-08-01):**
  - **Causa-raiz confirmada:** três camadas com vocabulários diferentes para o mesmo estado.
  - `apps/extra_curricular/services.py` — novos `status_token()` / `justificativa_token()` e os
    mapas `_STATUS_TOKENS` / `_JUSTIFICATIVA_TOKENS`; `get_pendencias_data` anexa
    `status_token` e `justificativa_token` a cada linha (**fonte da verdade única**).
  - `apps/extra_curricular/views.py` — `PendenciaListView` agora compara
    `item["status_token"] == status_filtro` (substitui a cadeia de `if/elif`); o `?status=`
    é normalizado com `.strip().lower().replace(" ", "_")`, mantendo URLs antigas válidas.
  - `templates/extra_curricular/pendencia_list.html` — os `<option value>` dos dois selects e
    os `data-status` / `data-justificativa` das linhas passam a usar os mesmos tokens.
  - **Bug adicional encontrado e corrigido:** o filtro **Justificativa → "Sem registro"**
    também nunca retornava nada — `data-justificativa` vinha vazio (`justificativa_tipo` é `""`
    nas linhas sem item) e jamais casava com `value="Sem registro"`.
  - **Decisão:** a camada client-side (JS) segue sendo a fonte da verdade dos 3 filtros
    instantâneos (o select não ganhou `name`, para não sumir da tela quando o filtro zera os
    resultados); o filtro server-side continua disponível para deep-link `?status=`, agora
    com o mesmo vocabulário.
  - `apps/extra_curricular/tests.py` — `FiltroStatusPendenciaTests` (9 testes).
  - Verificação: `apps.extra_curricular` verde; revisão adversarial sem apontamentos.

## CORR-016 — Título "HARPIA" genérico na tela de Alocação Curricular
- **Status:** 🟢 Corrigido (2026-08-01) · **Prioridade:** 🅒 Baixa · **Área:** Alocação / Front
- **Arquivos:** `templates/allocations/alloc_curricular.html` (só define `{% block content %}` `:4` e
  `{% block extra_js %}` `:186` — **sem** `title`/`header_title`); defaults em
  `templates/base.html:6` (`<title>...HARPIA`) e `:114-116` (`header_title` → HARPIA).
- **Problema:** a aba/cabeçalho da tela de Alocação mostra só **"HARPIA"** porque o template **não**
  define `{% block title %}` nem `{% block header_title %}`, caindo nos defaults do `base.html`.
- **Correção proposta:** adicionar no `alloc_curricular.html` (após a linha 2):
  `{% block title %}Alocação Curricular — Harpia-DESUP{% endblock %}` e
  `{% block header_title %}Alocação Curricular{% endblock %}` (padrão de `matrix_list.html:4-5` e
  `pendencia_list.html:4-5`, que já funcionam).
- **Notas:** puramente template. Verificar outras telas sem esses blocos (mesmo sintoma).
- **Resolução (2026-08-01):**
  - `templates/allocations/alloc_curricular.html` — adicionados
    `{% block title %}Alocação Curricular — Harpia-DESUP{% endblock %}` e
    `{% block header_title %}Alocação Curricular{% endblock %}`.
  - **Auditoria completa das telas que estendem `base.html`:** outras **4** também não
    definiam os blocos e caíam em "HARPIA" — `core/janela_form.html`, `core/janela_list.html`,
    `core/unidade_form.html`, `core/unidade_list.html`. Todas corrigidas (as de formulário com
    título condicional a `form.instance.pk`, no padrão de `matrix_form.html`).
  - `apps/core/tests.py` — `TituloDasTelasTests` (2 testes).
  - Verificação: `apps.core` verde.

## CORR-017 — Menu de usuário: exibe "ADMIN Alberto" e "Meu Perfil" leva à troca de senha
- **Status:** 🟢 Corrigido (2026-08-01) · **Prioridade:** 🅑 Média · **Área:** Conta / Perfil (front + view)
- **Arquivos:** `templates/base.html:172-195` (dropdown de usuário: nome `:175`
  `{{ user.get_full_name|default:user.email|upper }}`, perfil `:176` `{{ user.get_perfil_display }}`,
  link "Meu Perfil" `:184` → `{% url 'password_change' %}`); rotas em `config/urls.py:23-29` (não há
  view/URL de "perfil").
- **Problema (2 erros):**
  1. O componente mostra **nome + perfil** ("ADMIN Alberto" — `first_name` "Alberto" + perfil cru
     `ADMIN` de conta legada; `get_perfil_display` devolve o valor bruto quando não está em
     `Perfil.choices`). Deveria mostrar o **email**.
  2. **"Meu Perfil"** aponta para `password_change` — vai direto para a **troca de senha**. Não
     existe página de perfil (só leitura).
- **Correção proposta:**
  - Exibir o **email** do usuário no componente (trocar `get_full_name|default:email` por
    `user.email`), mantendo o perfil/unidade como info secundária.
  - Criar uma **página de Perfil** (só leitura: email, tipo de perfil, e **unidade** para perfis de
    unidade) com view+rota próprias; apontar "Meu Perfil" para ela. No dropdown, manter os itens
    **"Meu Perfil"**, **"Alterar senha"** e **"Sair"** separados (hoje o link de senha se disfarça de
    "Meu Perfil" para não-superuser e "Alterar senha" para superuser — `:181-185`).
- **Notas:** `User` (`apps/accounts/models.py`): `USERNAME_FIELD='email'`, `perfil`
  (DESUP / COORDENADOR_UNIDADE), `unidade` FK. Conta com perfil `ADMIN` no banco é legada/dev —
  confirmar se deve virar um perfil oficial ou ser normalizada. Relaciona-se com **CORR-018**.
- **Resolução (2026-08-01):**
  - `apps/accounts/views.py` — nova `ProfileView` (`LoginRequiredMixin`), somente leitura.
  - `config/urls.py` — rota `accounts/perfil/` (name **`profile`**).
  - `templates/accounts/profile.html` (novo) — e-mail, tipo de perfil e unidade (a unidade só
    aparece para perfis de unidade), com atalho para "Alterar senha".
  - `templates/base.html` — o componente de usuário mostra o **e-mail** (antes
    `get_full_name|default:email|upper`, que rendia "ADMIN Alberto"); o menu passou a ter
    **"Meu Perfil"**, **"Alterar senha"** e **"Sair"** como itens separados — antes o link de
    senha se disfarçava de "Meu Perfil" para quem não era superuser.
  - `apps/accounts/tests.py` — `PerfilPageTests` (5 testes).
  - **Pendência de decisão (não bloqueia):** contas legadas com `perfil='ADMIN'` continuam
    exibindo o valor cru em `get_perfil_display()`; definir se vira perfil oficial ou é
    normalizada no banco (ver **CORR-019**).
  - Verificação: `apps.accounts` verde.

## CORR-018 — Troca de senha exige digitar o email manualmente
- **Status:** 🟢 Corrigido (2026-08-01) · **Prioridade:** 🅑 Média · **Área:** Conta / Senha (view + template)
- **Arquivos:** `apps/accounts/views.py:158-273` (`CustomPasswordChangeView`; gate em `:165-198`;
  `_request_email_confirmation` `:175-249` lê `request.POST.get("email")` e compara com
  `request.user.email`), `templates/registration/password_change_email_prompt.html` (coleta email
  via SweetAlert e grava hidden `:24`).
- **Problema:** para quem já trocou a senha (`forcar_troca_senha=False`), o fluxo abre um prompt que
  **exige digitar o email** (que precisa ser idêntico ao do usuário logado) e só então envia o link
  de troca. É redundante — o email já está em `request.user.email` — e o usuário percebe como brecha
  ("qualquer email digitável"). *(Obs.: hoje a view valida `email == request.user.email`, então não
  há vazamento real; mas a UX é ruim/confusa.)*
- **Correção proposta:** usar **`request.user.email` diretamente** e **enviar a notificação/link ao
  email do próprio usuário logado**, dispensando o prompt e o campo livre de email. Ponto a alterar:
  o gate `get`/`post` (`views.py:165-198`) e `_request_email_confirmation` (`:175-249`) — remover a
  leitura de `POST["email"]` e o template `password_change_email_prompt.html` (ou reduzi-lo a uma
  confirmação sem campo). Manter o envio de link por email (evita troca sem confirmação).
- **Notas:** não confundir com `ForgotPasswordView` (`views.py:339-403`, fluxo deslogado com
  aprovação DESUP). Quando `forcar_troca_senha=True` (1º acesso) o gate já é ignorado e a troca roda
  sem pedir email (`:251-273`). Relaciona-se com **CORR-017** (mesmo componente/fluxo de conta).
- **Resolução (2026-08-01):**
  - `apps/accounts/views.py` — `CustomPasswordChangeView` não lê mais `request.POST["email"]`.
    O `get()` renderiza uma tela de confirmação **sem campo de e-mail** e o
    `_request_email_confirmation()` usa direto `request.user.email`. O envio do link por
    e-mail (com token de 1 hora) foi mantido.
  - `templates/registration/password_change_email_prompt.html` — reescrito: sem
    `<input name="email">`, sem o prompt SweetAlert; mostra o e-mail da conta e um botão
    "Enviar link de troca de senha".
  - `PasswordChangeConfirmView._render_invalid` passa `somente_erro=True` — link expirado/já
    usado mostra só a mensagem, sem botão de ação (o usuário pode nem estar autenticado).
  - O ramo `PASSWORD_CHANGE_EMAIL_MISMATCH` deixou de existir (não havia vazamento real: a
    view já comparava com o e-mail do usuário logado; o problema era de UX).
  - `apps/accounts/tests.py` — `test_password_change_email_mismatch` (que testava o
    comportamento removido) foi substituído por `test_tela_de_troca_nao_pede_email` e
    `test_email_do_post_e_ignorado`.
  - **Bônus:** `test_password_change_link_sent` estava **falhando desde antes** desta sessão
    (`0 != 1`) porque o envio roda em `transaction.on_commit` e o `TestCase` reverte a
    transação; corrigido com `captureOnCommitCallbacks(execute=True)`.
  - **Observação (pré-existente, não regressão):** não há rate-limit no envio do link.
  - Verificação: `apps.accounts` verde.

## CORR-019 — Admin (superuser) cai no dashboard DESUP ao entrar no /admin/
- **Status:** 🟢 Corrigido (2026-08-01) · **Prioridade:** 🅑 Média · **Área:** Conta / Roteamento (view + settings)
- **Arquivos:** `apps/accounts/views.py:48-58` (`get_dashboard_url_for_user` — **superuser →
  `/dashboard/desup/`**, `:52-53`), `apps/core/views.py:27-36` (`DashboardView.get` roteia via essa
  função), `config/settings/base.py:91` (`LOGIN_REDIRECT_URL = 'dashboard'`),
  `config/urls.py:21,51` (`/admin/` = `admin_site.urls`; raiz `''` → `RedirectView pattern_name='dashboard'`),
  `apps/accounts/admin.py:11-22` (`HarpiaAdminSite`/Unfold — `has_permission` exige `is_staff`).
- **Problema:** **de vez em quando**, ao acessar o **/admin/**, o superuser (DEV/ADMIN) é jogado num
  **dashboard equivalente ao do Coord. DESUP** (`/dashboard/desup/`). **Root cause:**
  `get_dashboard_url_for_user` roteia **`is_superuser` → `/dashboard/desup/`** (`:52-53`). Como a raiz
  `/` e `LOGIN_REDIRECT_URL` apontam para `dashboard` → `DashboardView` → essa função, qualquer
  redirect a `/`/`dashboard` (incl. quando o `/admin/` exige (re)login e não há `next` válido, caindo
  no `LOGIN_REDIRECT_URL='dashboard'`) leva o admin ao dashboard DESUP. O caráter intermitente vem do
  timing de sessão/`next` no `/admin/` (às vezes há sessão válida → fica no admin; às vezes re-login →
  cai no dashboard). O admin **só** deveria acessar o admin Django.
- **Correção proposta:**
  - Em `get_dashboard_url_for_user`, tratar **superuser/ADMIN** separadamente → retornar **`/admin/`**
    (ou uma landing de admin), **não** `/dashboard/desup/`. Não misturar "admin/dev" com "operador
    DESUP".
  - Garantir que o pós-login e o `LOGIN_REDIRECT_URL` de superuser resolvam para o **/admin/** (ou que
    o fluxo de login do admin preserve o `next` para dentro do admin).
  - Opcional: `DashboardDesupView` já é `allowed_profiles=['DESUP']` — avaliar se o superuser deve
    mesmo ser aceito lá (hoje `PerfilRequiredMixin` normalmente libera superuser). Se o admin/dev não
    é operador DESUP, bloquear e redirecionar ao admin.
- **Notas:** relaciona-se com **CORR-017** (conta legada `perfil='ADMIN'`) — definir se "ADMIN/dev" é
  um perfil à parte que nunca entra nos dashboards operacionais. Cobrir com teste: superuser acessando
  `/` e `/dashboard/` é levado ao `/admin/`, não ao `/dashboard/desup/`.
- **Resolução (2026-08-01):**
  - `apps/accounts/views.py` — `get_dashboard_url_for_user` passa a devolver **`/admin/`** para
    `is_superuser` (antes `/dashboard/desup/`). Como a raiz `/` e `LOGIN_REDIRECT_URL='dashboard'`
    passam por essa função, era ela que jogava o admin no dashboard da DESUP sempre que havia
    um redirect para `/`/`dashboard` (inclusive no re-login do `/admin/` sem `next` válido) —
    daí o caráter intermitente. `get_redirect_url_for_user` já devolvia `/admin/`: as duas
    funções deixam de divergir.
  - `apps/accounts/tests.py` / `apps/core/tests.py` — dois testes **codificavam o bug**
    (`test_superuser_dashboard_url_points_to_desup_dashboard` e
    `test_dashboard_redirects_superuser_to_desup_dashboard`) e foram reescritos; somados dois
    novos (rota única entre as duas funções; raiz `/` levando ao `/admin/`).
  - **Trava opcional NÃO implementada (decisão do usuário):** bloquear o superuser de acessar
    `/dashboard/desup/` digitando a URL. O sintoma relatado ("cai no dashboard DESUP") está
    resolvido pelo roteamento; bloquear o acesso direto impediria um superuser que também
    opera a DESUP de usar a tela. Se for a regra desejada, basta um guard em
    `DashboardDesupView.dispatch`.
  - Verificação: `apps.accounts` + `apps.core` verdes.

## CORR-020 — Envio do link de troca de senha sem rate-limit
- **Status:** 🟢 Corrigido (2026-08-01) · **Prioridade:** 🅑 Média · **Área:** Conta / Senha
- **Arquivos:** `apps/accounts/models.py` (`SelfPasswordChangeRequest`),
  `apps/accounts/views.py` (`CustomPasswordChangeView._request_email_confirmation`).
- **Problema:** o fluxo de troca de senha (**CORR-018**) enviava um link por e-mail a cada POST,
  sem nenhum limite. Qualquer sessão autenticada — inclusive uma sessão esquecida aberta — podia
  disparar e-mails indefinidamente, com custo de envio e risco de a conta do usuário ser inundada.
  Era uma lacuna **pré-existente**, não introduzida pela CORR-018.
- **Correção proposta:** limitar a **1 pedido por usuário a cada 24 horas**, ignorando o limite
  quando `settings.DEBUG` (para não atrapalhar o desenvolvimento).
- **Resolução (2026-08-01):**
  - `apps/accounts/models.py` — `SelfPasswordChangeRequest` ganhou a constante `COOLDOWN`
    (`timedelta(days=1)`), o classmethod `pedido_recente(user)` (último pedido dentro da janela,
    ou `None`) e a property `liberado_em`.
  - `apps/accounts/views.py` — `_request_email_confirmation` verifica `pedido_recente()` **antes**
    de criar o token; quando bloqueia, registra a auditoria `PASSWORD_CHANGE_RATE_LIMITED` e
    devolve a própria tela com a data/hora em que um novo pedido será liberado. O bloqueio é
    pulado quando `settings.DEBUG` é verdadeiro.
  - A checagem e a criação do token ficam na **mesma transação**, com a linha do usuário travada
    por `select_for_update()`: sem o lock, um **duplo clique** no botão dispara dois POSTs que
    passariam os dois pela checagem e gerariam dois links (apontado na revisão adversarial). Em
    SQLite o lock é inócuo; em PostgreSQL (produção) ele serializa.
  - `config/settings/production.py` fixa `DEBUG = False` **no código** (não vem de env), então o
    bypass de DEBUG não pode ser ligado por engano em produção; e `USE_TZ = True`, então o
    `timezone.localtime()` da mensagem opera sobre datetime *aware*.
  - O limite conta **pedidos**, não trocas concluídas: quem já recebeu o link no dia usa o link
    (que vale 1 hora), em vez de pedir outro.
  - O primeiro acesso (`forcar_troca_senha=True`) **não** passa por esse fluxo e segue sem limite.
  - `apps/accounts/tests.py` — 4 testes: segundo pedido no mesmo dia bloqueado (sem token novo,
    sem e-mail novo, com auditoria); liberação após 24h; `@override_settings(DEBUG=True)` ignora
    o limite; o limite é por usuário.
  - Verificação: `apps.accounts` **33/33** verdes.

## CORR-021 — Perfil ADMIN (TI DESUP) oficial
- **Status:** 🟢 Corrigido (2026-08-01) · **Prioridade:** 🅐 Alta · **Área:** Conta / Perfis de acesso
- **Arquivos:** `apps/accounts/models.py` (`User.Perfil`, `UserManager.create_superuser`,
  `User.save`), `apps/accounts/mixins.py` (`PerfilRequiredMixin`),
  `apps/accounts/views.py` (`get_redirect_url_for_user`, `get_dashboard_url_for_user`,
  `ProfileView`), `apps/accounts/migrations/0003_alter_user_perfil.py`.
- **Problema:** `User.Perfil` tinha só **dois** valores (`DESUP` e `COORDENADOR_UNIDADE`).
  O valor `ADMIN` existia no banco como dado legado, fora de `Perfil.choices` — por isso
  `get_perfil_display()` devolvia o valor cru ("ADMIN"), como apontado na **CORR-017**. Pior:
  `create_superuser` gravava `perfil="DESUP"`, misturando o time de **TI/DEV** com a
  **operação da Coordenação DESUP**, que são funções completamente diferentes.
- **Decisão do usuário (2026-08-01):** são **três perfis oficiais** —
  **ADMIN (TI DESUP)**, **Coord. DESUP** e **Coord. Unidade**. O ADMIN cuida do
  desenvolvimento e usa o **admin do Django** para testes e alterações; **não precisa** dos
  dashboards. A operação do dia a dia é dividida **apenas** entre Coord. DESUP e Coord. Unidade.
- **Resolução (2026-08-01):**
  - `User.Perfil` ganhou `ADMIN = "ADMIN", "Administrador (TI DESUP)"`. Os rótulos dos outros
    dois foram ajustados para distinguir os papéis: `DESUP` → **"Coordenador DESUP"**
    (era só "DESUP") e `COORDENADOR_UNIDADE` → "Coordenador de Unidade".
  - `User.save()` força `is_staff=True` quando o perfil é ADMIN — sem isso seria possível criar
    um ADMIN sem acesso à única tela que ele usa.
  - `UserManager.create_superuser` passou a gravar `perfil="ADMIN"` por padrão (antes `DESUP`).
    Continua aceitando `perfil=` explícito, para o caso de uma conta que também opera a DESUP.
  - **Roteamento:** `get_redirect_url_for_user` e `get_dashboard_url_for_user` devolvem
    `/admin/` para `is_superuser` **ou** `perfil == 'ADMIN'` (o ADMIN pode existir sem ser
    superusuário).
  - **`PerfilRequiredMixin`:** novo gate no topo do `dispatch` — perfil ADMIN em rota
    operacional é **redirecionado** para `/admin/` (HTMX recebe `204` + `HX-Redirect`). Fica
    **antes** do bypass de superusuário, porque o ADMIN normalmente também é superusuário. É
    redirect e não 403 de propósito: não é falta de permissão, é que a tela certa é outra.
    Isso fecha a **trava opcional** que ficara em aberto na CORR-019.
  - `ProfileView` simplificada: o rótulo vem direto de `get_perfil_display()` e a unidade só
    aparece para `COORDENADOR_UNIDADE`.
  - **Migração `0003_alter_user_perfil`: só altera `choices`, sem conversão de dados.**
    Superusuários existentes continuam com `perfil='DESUP'` e **mantêm** o acesso operacional —
    ninguém é trancado fora no deploy. A conta legada que já estava com `'ADMIN'` passa a ser
    válida e a se comportar como TI. Promover as demais contas de TI para ADMIN é uma decisão
    manual (pelo admin do Django).
  - `apps/accounts/tests.py` — `PerfilAdminOficialTests` (13 testes): os 3 perfis e rótulos;
    `is_staff` automático (na criação e ao promover); `create_superuser` nascendo ADMIN e
    aceitando perfil explícito; roteamento e login do ADMIN indo ao `/admin/`; ADMIN
    redirecionado em 3 rotas operacionais e via HTMX, com o destino `/admin/` seguido até o
    fim para provar que não há loop; DESUP e superuser-com-perfil-DESUP
    intactos; rótulo na página de perfil.
  - Verificação: suíte completa **173/173** verde.

## CORR-022 — Diretório `templates/extracurricular/` órfão
- **Status:** 🟢 Corrigido (2026-08-01) · **Prioridade:** 🅒 Baixa · **Área:** Manutenção / Templates
- **Arquivos (removidos):** `templates/extracurricular/form.html`,
  `templates/extracurricular/index.html`,
  `templates/extracurricular/partials/_formset_row.html`,
  `templates/extracurricular/partials/_table_body.html`.
- **Problema:** o diretório `templates/extracurricular/` (**sem** underscore) é código morto —
  não confundir com `templates/extra_curricular/` (**com** underscore), que é o de verdade,
  ligado ao namespace `extra_curricular`. Nenhuma view, script ou outro template apontava para
  ele: as únicas referências eram `{% include %}` **internos ao próprio diretório**.
  Além de morto, tinha 3 comentários `{# ... #}` **multi-linha** — que o Django **não** trata
  como comentário (`tag_re` não usa `re.DOTALL`) e renderizaria como texto literal na tela —,
  e usava a variável `janela_fechada` de um jeito divergente do resto do app.
- **Correção proposta:** remover o diretório.
- **Resolução (2026-08-01):** diretório removido por completo (`git rm -r`). A rota legada
  `extracurricular_index` (`config/urls.py`) **não** foi tocada: ela é um `RedirectView` para
  `extra_curricular:pendencia_list` e não renderiza template nenhum.
  Verificação: `manage.py check` sem problemas; suíte completa **173/173** verde.

## CORR-024 — Escopo da janela de entrega: professor fica de fora (decisão do cliente)
- **Status:** 🟢 Corrigido (2026-08-01) · **Prioridade:** 🅑 Média · **Área:** Janela de Entrega / Documentação
- **Arquivos:** `apps/core/context_processors.py` (comentário de escopo), `docs/ia/claude-opus.md`.
- **Problema:** o repositório se contradizia sobre o alcance da janela. O comentário em
  `context_processors.py` dizia que "nas demais telas (professores, **matrizes**, etc.) a janela
  não se aplica mais"; `docs/ia/claude-opus.md` dizia que a janela controla "prazo de **matriz E**
  justificativas". A auditoria adversarial de 2026-08-01 levantou como possível furo o fato de
  editar/excluir/duplicar professor passar com a janela fechada — sem saber qual das duas fontes
  valia.
- **Decisão do cliente (2026-08-01):** a janela controla **alocação curricular** e
  **justificativas extracurriculares**, e só. **O cadastro de professor passa fora da janela**,
  *"por hora, até o cliente final mudar de ideia"*.
- **Resolução (2026-08-01):** nenhuma mudança de comportamento — as rotas de professor
  **continuam** sem `enforce_window_or_redirect`, de propósito. O que mudou foi tornar isso
  inequívoco:
  - `apps/core/context_processors.py` — comentário reescrito dizendo o escopo exato, que o
    cadastro de professor é exceção deliberada, e pedindo que uma auditoria futura confirme a
    decisão antes de "corrigir".
  - `docs/ia/claude-opus.md` — a linha de regra de negócio passou a descrever o escopo real
    (as duas áreas, o perfil afetado, a exceção do professor e o bypass de DESUP/superusuário).
  - Observação registrada: o CRUD de matriz é DESUP-only e DESUP faz bypass, então a janela
    nunca o alcança na prática; o que a unidade faz sobre a matriz é a **alocação**, essa sim
    coberta pela janela.

## CORR-023 — Aprovação parcial: item indeferido zerava toda a CH aprovada
- **Status:** 🟢 Corrigido (2026-08-01) · **Prioridade:** 🅐 Alta · **Área:** Extracurricular / Parecer DESUP
- **Arquivos:** `apps/extra_curricular/models.py` (`StatusChoices`, `STATUS_FINALIZADOS`,
  `ch_total_justificada`), `apps/extra_curricular/services.py`
  (`sincronizar_status_pendencia`, `_STATUS_TOKENS`, `get_pendencias_data`),
  `apps/extra_curricular/views.py` (`PendenciaReabrirView`),
  `templates/extra_curricular/pendencia_list.html`,
  `apps/extra_curricular/migrations/0004_alter_pendenciaextra_status.py`.
- **Problema:** o status agregado era binário. `sincronizar_status_pendencia` fazia
  `any(INDEFERIDO) ⇒ INDEFERIDO`, e `ch_total_justificada` devolvia `0.0` fora de `APROVADO`.
  Resultado: **um único item indeferido apagava toda a CH que a DESUP já tinha deferido nos
  demais itens** da mesma pendência. Levantado na auditoria adversarial de 2026-08-01.
- **Decisão do cliente (2026-08-01):** *"Um item indeferido não deve zerar tudo, o item que for
  aprovado conta, o que for indeferido deixa quieto."*
- **Resolução (2026-08-01):**
  - Novo status **`PARCIAL`** ("Finalizado parcialmente") e a constante
    `PendenciaExtra.STATUS_FINALIZADOS = (APROVADO, PARCIAL)`.
  - `sincronizar_status_pendencia` passou de 3 para 4 saídas: rascunho nunca é promovido; item
    ainda sem decisão mantém `ENVIADO`; todos aprovados ⇒ `APROVADO`; todos indeferidos ⇒
    `INDEFERIDO`; misto ⇒ `PARCIAL`.
  - `ch_total_justificada` conta em `APROVADO` **ou** `PARCIAL`, somando só os itens com parecer
    `APROVADO` (o filtro por item veio da CORR-027). **O gate pelo status do cabeçalho foi
    mantido de propósito** — é ele que faz a CH parar de contar após uma **reabertura**, quando o
    status volta a `ENVIADO` mas os itens seguem marcados como aprovados.
  - `PendenciaReabrirView` aceita reabrir uma pendência `PARCIAL` (também é análise concluída).
  - UI: badge próprio (`badge-parcial`) e ícone na listagem; token de filtro `parcial` no
    vocabulário da CORR-015 — separado de `finalizado`, senão a DESUP perderia de vista
    justamente as pendências que tiveram item indeferido.
  - **6 testes existentes codificavam a regra antiga** e foram atualizados (dois deles tinham a
    regra no próprio nome: `test_sincronizar_indeferido_tem_prioridade` →
    `test_sincronizar_resultado_misto_vira_parcial`). Mais 7 testes novos em
    `AprovacaoParcialTests`, incluindo o caso do cliente, os dois extremos, item ainda pendente,
    rascunho e reabertura.
  - Verificação: suíte completa **533 testes verdes**.
