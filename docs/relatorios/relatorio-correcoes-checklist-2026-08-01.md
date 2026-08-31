# Relatório — Fechamento das pendências do checklist de correções

**Data:** 2026-08-01
**Base:** `74dd64f` (branch `fix/corr-pendentes-checklist`)
**Escopo:** todos os itens `🔴 Pendente` de `docs/checklist_correcao.md` — **10 itens** ·
mais **3 itens novos** (CORR-020/021/022) abertos a partir das pendências desta leva
**Resultado:** 13/13 corrigidos · suíte **174/174 verde** · `manage.py check` sem problemas

---

## 1. Sumário

| Ordem | Item | Prioridade | Branch | Commit |
|:--:|------|:---:|------|--------|
| 1 | CORR-015 — filtro "Sem registro" não retorna nada | 🅐 | `fix/CORR-015-filtro-sem-registro` | `f935bbb` |
| 2 | CORR-006 — cobertura de testes dos pareceres DESUP | 🅑 | `test/CORR-006-cobertura-pareceres-desup` | `dd69371` |
| 3 | CORR-007 — bloquear campos do componente na matriz | 🅑 | `fix/CORR-007-campos-componente-bloqueados` | `5f713c7` |
| 4 | CORR-014 — pop-up "Janela fechada" duplicado | 🅑 | `fix/CORR-014-aviso-janela-duplicado` | `f05fa6b` |
| 5 | CORR-017 — menu de usuário: e-mail + página de Perfil | 🅑 | `feat/CORR-017-pagina-perfil` | `09543b8` |
| 6 | CORR-018 — troca de senha sem digitar e-mail | 🅑 | `fix/CORR-018-troca-senha-sem-email` | `b02514c` |
| 7 | CORR-019 — superuser cai no dashboard DESUP | 🅑 | `fix/CORR-019-superuser-admin` | `f640989` |
| 8 | CORR-009 — coluna "Código da Disciplina" estreita | 🅒 | `fix/CORR-009-coluna-codigo-estreita` | `18f25a9` |
| 9 | CORR-010 — ícones do menu lateral não centralizados | 🅒 | `fix/CORR-010-icones-sidebar-centralizados` | `bd27359` |
| 10 | CORR-016 — título "HARPIA" na tela de Alocação | 🅒 | `fix/CORR-016-titulo-alocacao` | `aefe87b` |

**CORR-013** (turnos por curso) **não** entrou: está marcado como `📄 Planejado` no checklist, com a
instrução explícita de **não implementar solto** (plano em `docs/planejamento/plano-turnos-por-curso.md`).

## 2. Como fazer rollback

As branches são **encadeadas**, uma por correção, na ordem da tabela acima — cada uma tem
**exatamente um commit**. Isso dá três opções:

- **Descartar da correção N em diante:** `git reset --hard <branch da correção N-1>`.
- **Reverter uma correção isolada:** `git revert <commit>` (cada commit toca só os arquivos do
  seu item — ver seção 5).
- **Levar tudo:** a ponta é `fix/CORR-016-titulo-alocacao`.

> O push é seu. Nenhuma branch foi enviada ao remoto.

---

## 3. O que foi corrigido, item a item

### CORR-015 — filtro "Sem registro" não retorna nada 🅐

**Sintoma:** filtrar por "Sem registro" na tela de Alocações Extracurriculares não listava nenhum
professor, mesmo com todos nesse estado.

**Causa-raiz:** três camadas com vocabulários diferentes para o mesmo estado —
`<option value="Sem registro">` no template, comparação com `'sem_registro'` na view, e
`data-status` com rótulos capitalizados nas linhas.

**Correção:** os tokens passaram a ter **uma única fonte da verdade**, em
`apps/extra_curricular/services.py` (`status_token()` / `justificativa_token()`), anexada a cada
linha por `get_pendencias_data`. View, `<option value>` e `data-*` consomem o mesmo token.
O `?status=` também é normalizado com `.replace(" ", "_")`, mantendo URLs antigas válidas.

**Bug adicional encontrado:** o filtro **Justificativa → "Sem registro"** tinha o mesmo defeito, por
outro caminho — `data-justificativa` vinha **vazio** nas linhas sem item (`justificativa_tipo` é `""`)
e nunca casava com `value="Sem registro"`. Corrigido junto.

**Decisão registrada:** a camada client-side (JS) segue sendo a fonte da verdade dos 3 filtros
instantâneos. O select **não** ganhou `name`/`hx-*` de propósito: a barra de filtros fica dentro do
bloco que só renderiza quando há resultados, então um round-trip ao servidor faria a própria barra
sumir da tela quando o filtro zerasse a lista — o usuário ficaria sem como desfazer o filtro.
O filtro server-side continua existindo para deep-link `?status=`, agora com o mesmo vocabulário.

**Testes:** `FiltroStatusPendenciaTests` (9).

### CORR-006 — cobertura de testes dos pareceres DESUP 🅑

**Problema:** o fluxo de parecer não tinha cobertura suficiente — o HTTP 500 do CORR-004 chegou ao
cliente sem ser barrado por teste.

**Correção:** nova classe `ParecerDesupCoberturaTests` (13 testes), cobrindo o mínimo pedido no
checklist:

- matriz **3 tipos × 3 pareceres**, com e sem os campos "aprovados" preenchidos (18 combinações);
- sequências do mesmo professor e consolidação por `sincronizar_status_pendencia`
  (qualquer indeferido ⇒ `INDEFERIDO`; todos aprovados ⇒ `APROVADO`; item pendente mantém `ENVIADO`;
  a ordem de avaliação não altera o resultado);
- estouro de `limite_horas_extra_efetivo` ⇒ mensagem de erro e **parecer não gravado**, sem 500,
  inclusive somando os demais itens já aprovados do professor;
- consistência de tipo de `ch_aprovada` (regressão do CORR-004);
- permissão: unidade recebe **403**, anônimo vai ao login, item de outra pendência dá **404**.

Nenhuma mudança de comportamento — commit só de testes.

### CORR-007 — só Disciplina e Período editáveis no componente 🅑

`carga_horaria` (CH Total) e `creditos` viraram `disabled=True`, juntando-se a `codigo` e
`carga_horaria_semanal`. `disabled` bloqueia na UI **e** faz o Django ignorar o valor do POST.

`MatrixComponentForm.clean` passou a derivar tudo no servidor: CH Total mantém o valor já gravado
(edição) e cai para `carga_horaria_padrao` na criação; `creditos = ch // 20`;
`carga_horaria_semanal = round(ch / 20, 2)` — mesma regra de `CurricularComponentForm.clean()` e de
`MatrixComponent.save()`.

Também corrigido um defeito de exibição no JS do formulário, que escrevia o valor de **créditos**
dentro do campo "CH Sem." (só coincidia quando a CH era múltipla de 20).

**Efeito colateral aceito:** ao duplicar/copiar matriz, a CH do componente passa a ser a da
disciplina — é exatamente a regra pedida ("os demais campos derivam da disciplina").

**Testes:** `MatrixComponentCamposBloqueadosTests` (7), incluindo POST adulterado
(`carga_horaria=999`, `creditos=99`) sendo ignorado e edição preservando CH legada.

### CORR-014 — pop-up "Janela de entrega fechada" duplicado 🅑

Removidos os blocos inline `{% if window_fechada %}` de `alloc_curricular.html` e
`pendencia_list.html`. Fica só o banner do `base.html`, que é o único com o botão
**"Solicitar abertura"**.

**Verificação de que ninguém fica sem aviso:** `janela_fechada` (context processor) e
`window_fechada` (`build_window_lock_context`) são verdadeiros para **exatamente o mesmo público** —
`COORDENADOR_UNIDADE`; DESUP e superuser fazem bypass da janela (`user_can_bypass_window`).

Os avisos análogos em `pendencia_form.html`, `pendencia_detail.html` e `pendencia_lote.html` **não**
foram tocados, conforme a nota do checklist.

**Testes:** `AvisoJanelaFechadaUnicoTests` (3).

### CORR-017 — menu de usuário: e-mail + página de Perfil 🅑

- Nova `ProfileView` (somente leitura) e rota `accounts/perfil/` (name **`profile`**).
- Novo template `accounts/profile.html`: e-mail, tipo de perfil e unidade (a unidade só aparece
  para perfis de unidade), com atalho para "Alterar senha".
- `base.html`: o componente de usuário mostra o **e-mail** (antes
  `get_full_name|default:email|upper`, que rendia "ADMIN Alberto"), e **"Meu Perfil"**,
  **"Alterar senha"** e **"Sair"** viraram itens separados — antes o link de senha se disfarçava de
  "Meu Perfil" para quem não era superuser.

**Testes:** `PerfilPageTests` (5).

### CORR-018 — troca de senha sem digitar o e-mail 🅑

`CustomPasswordChangeView` não lê mais `request.POST["email"]`; usa `request.user.email` direto.
O template do prompt foi reescrito sem campo de e-mail e sem o SweetAlert: mostra o e-mail da conta
e um botão de envio. O link com token de 1 hora foi mantido (a confirmação por e-mail continua).

`PasswordChangeConfirmView._render_invalid` passa `somente_erro=True` — link expirado/já usado mostra
só a mensagem, sem botão de ação (nesse caminho o usuário pode nem estar autenticado).

O ramo `PASSWORD_CHANGE_EMAIL_MISMATCH` deixou de existir. Não havia vazamento real (a view já
comparava com o e-mail do usuário logado); o problema era de UX, como o próprio checklist observava.

**Correção de bônus:** `test_password_change_link_sent` **já estava falhando antes desta sessão**
(`AssertionError: 0 != 1`). Causa: o envio roda em `transaction.on_commit` e o `TestCase` reverte a
transação, então o callback nunca disparava. Resolvido com `captureOnCommitCallbacks(execute=True)`.

### CORR-019 — superuser cai no dashboard DESUP 🅑

**Causa-raiz:** `get_dashboard_url_for_user` roteava `is_superuser` para `/dashboard/desup/`. Como a
raiz `/` e `LOGIN_REDIRECT_URL='dashboard'` passam por essa função, qualquer redirect a `/`/`dashboard`
levava o admin ao dashboard da DESUP — inclusive quando o `/admin/` exigia re-login sem `next`
válido, o que explica o caráter **intermitente** do relato.

A função agora devolve `/admin/` para superuser, alinhando-se a `get_redirect_url_for_user`, que já
devolvia. **Dois testes existentes codificavam o bug** e foram reescritos.

### CORR-009 — coluna "Código da Disciplina" estreita 🅒

Código: `col-span-1` → `col-span-2`, no cabeçalho e na linha. Coluna doadora: **CH Total**
(`col-span-2` → `col-span-1`), que com a CORR-007 virou read-only e exibe só um número. Os spans
continuam somando **12**; o empilhamento mobile não mudou.

### CORR-010 — ícones do menu lateral não centralizados 🅒

Os 8 `.sidebar-link` ganharam `justify-center group-hover:justify-start`, e o botão **"Sair"** — que
não tinha a classe — virou `.sidebar-link` também. Em `dashboard.css`, dentro do
`@media (max-width: 1023px)` já existente, o alinhamento volta a `flex-start`: na gaveta mobile não
há hover, então sem essa regra o rótulo ficaria centralizado. O `text-2xl` dos ícones não mudou.

### CORR-016 — título "HARPIA" na tela de Alocação 🅒

`alloc_curricular.html` ganhou `{% block title %}` e `{% block header_title %}`. A auditoria de
**todas** as telas que estendem `base.html` encontrou outras **4** com o mesmo sintoma —
`core/janela_form.html`, `core/janela_list.html`, `core/unidade_form.html`, `core/unidade_list.html` —
todas corrigidas (as de formulário com título condicional a `form.instance.pk`).

---

## 4. Verificação

**Suíte completa:** `python manage.py test apps` → **157 testes, OK** (baseline: 114 testes com
**1 falha** — `test_password_change_link_sent`, corrigida na CORR-018).
`manage.py check` sem problemas em `development` e `production`.

**Testes acrescentados:** 43.

| App | Antes | Depois |
|-----|:--:|:--:|
| `apps.extra_curricular` | 19 | 41 |
| `apps.courses` | 18 | 25 |
| `apps.core` | 50 | 56 |
| `apps.accounts` | 27 | 29 |

**Revisão adversarial:** cada lote passou por um revisor independente instruído a **quebrar** a
correção (consumidores esquecidos, especificidade de CSS, sintaxe de template, casos-limite,
testes vazios). Dois apontamentos reais vieram de lá e foram corrigidos antes do commit:

1. `MatrixComponentForm.clean` podia deixar `carga_horaria = None` chegar ao `save()` e estourar
   `IntegrityError` sem explicar a causa → virou `ValidationError` com mensagem clara (CORR-007).
2. `test_apenas_desup_emite_parecer` aceitava `302 ou 403` — um refactor que removesse a trava de
   perfil ainda passaria. Apertado para `403` (CORR-006).

**Defeito próprio encontrado e corrigido durante o trabalho:** comentários `{# ... #}` do Django
**não podem ter mais de uma linha** (`tag_re` não usa `re.DOTALL`); os multi-linha que eu havia
escrito virariam texto literal na página — um deles no meio dos atributos de um `<tr>`. Todos foram
convertidos para `{% comment %}`. Uma varredura no repositório mostrou 3 casos **pré-existentes** do
mesmo erro em `templates/extracurricular/form.html` — template **órfão** (nenhuma view o referencia),
deixado fora do escopo.

---

## 5. Arquivos tocados

| Arquivo | Correções |
|---------|-----------|
| `apps/extra_curricular/services.py` | 015 |
| `apps/extra_curricular/views.py` | 015 |
| `apps/extra_curricular/tests.py` | 015, 006 |
| `templates/extra_curricular/pendencia_list.html` | 015, 014 |
| `apps/courses/forms.py` | 007 |
| `apps/courses/tests.py` | 007 |
| `templates/courses/matrix_form.html` | 007, 009 |
| `templates/allocations/alloc_curricular.html` | 014, 016 |
| `apps/core/tests.py` | 014, 016, 010, 019 |
| `apps/accounts/views.py` | 017, 018, 019 |
| `apps/accounts/tests.py` | 017, 018, 019 |
| `config/urls.py` | 017 |
| `templates/accounts/profile.html` *(novo)* | 017 |
| `templates/base.html` | 017, 010 |
| `templates/registration/password_change_email_prompt.html` | 018 |
| `templates/core/{janela,unidade}_{form,list}.html` | 016 |
| `static/css/dashboard.css` | 010 |
| `docs/checklist_correcao.md` | todas |

Nenhuma migração de banco foi necessária — nenhum model mudou.

---

## 6. Pendências e decisões — todas fechadas em seguida

Os 4 itens que ficaram em aberto ao fim da primeira leva foram resolvidos logo depois, a pedido do
usuário, e viraram **CORR-020, CORR-021 e CORR-022** (ver seção 8). O que sobra:

- **CORR-013** segue como `📄 Planejado`, conforme instrução do próprio checklist.

## 7. Ambiente

Não havia virtualenv no repositório; foi criado `.venv/` (já coberto pelo `.gitignore`) com
`project_root/requirements.txt` para rodar a suíte. Os testes rodaram em **SQLite**
(`DB_ENGINE=django.db.backends.sqlite3`), já que o `development.py` aponta para PostgreSQL local.

---

## 8. Adendo — fechamento dos itens em aberto (mesma data)

| Ordem | Item | Prioridade | Branch | Commit |
|:--:|------|:---:|------|--------|
| 11 | CORR-020 — rate-limit da troca de senha (1×/dia) | 🅑 | `fix/CORR-020-rate-limit-troca-senha` | `48e546b` |
| 12 | CORR-021 — perfil ADMIN (TI DESUP) oficial | 🅐 | `feat/CORR-021-perfil-admin-oficial` | `136249b` |
| 13 | CORR-022 — remover `templates/extracurricular/` órfão | 🅒 | `chore/CORR-022-remove-templates-orfaos` | `6232a2c` |

Continuam encadeadas a partir de `055c955` (o commit do relatório), com a mesma regra de rollback.
**Suíte: 174/174 verde.**

### CORR-020 — rate-limit de 1 pedido por dia

`SelfPasswordChangeRequest` ganhou `COOLDOWN = timedelta(days=1)`, o classmethod
`pedido_recente(user)` e a property `liberado_em`. `_request_email_confirmation` checa o cooldown
**antes** de criar o token; ao bloquear, registra a auditoria `PASSWORD_CHANGE_RATE_LIMITED` e
mostra a data/hora de liberação. O limite é ignorado quando `settings.DEBUG`.

A checagem e a criação do token ficam na **mesma transação**, com a linha do usuário travada por
`select_for_update()`. Sem o lock, um **duplo clique** no botão dispara dois POSTs que passariam
os dois pela checagem e gerariam dois links — apontado na revisão adversarial e corrigido antes do
commit. Em SQLite o lock é inócuo; em PostgreSQL (produção) ele serializa.

Dois pontos verificados de propósito: `config/settings/production.py` fixa `DEBUG = False` **no
código** (não vem de env), então o bypass não pode ser ligado por engano em produção; e
`USE_TZ = True`, então o `timezone.localtime()` da mensagem opera sobre datetime *aware*.

O limite conta **pedidos**, não trocas concluídas — quem já recebeu o link no dia usa o link (que
vale 1 hora) em vez de pedir outro. O primeiro acesso (`forcar_troca_senha=True`) não passa por
esse fluxo e segue sem limite.

### CORR-021 — perfil ADMIN (TI DESUP) oficial

**Regra de negócio definida pelo usuário:** três perfis oficiais — **ADMIN (TI DESUP)**,
**Coord. DESUP** e **Coord. Unidade**. O ADMIN cuida do desenvolvimento e usa o admin do Django
para testes e alterações; **não** precisa dos dashboards. A operação do dia a dia é dividida
**apenas** entre Coord. DESUP e Coord. Unidade.

- `User.Perfil` ganhou `ADMIN`; os rótulos passaram a distinguir os papéis
  (`DESUP` → "Coordenador DESUP", que antes exibia só "DESUP").
- `User.save()` força `is_staff=True` para ADMIN — sem isso daria para criar um ADMIN sem acesso
  à única tela que ele usa.
- `create_superuser` grava `perfil="ADMIN"` por padrão (antes `DESUP`), ainda aceitando `perfil=`
  explícito para uma conta que também opere.
- Roteamento e `PerfilRequiredMixin` mandam o ADMIN para `/admin/` — o gate fica **antes** do
  bypass de superusuário, porque o ADMIN normalmente também é superusuário. É **redirect**, não
  403: não é falta de permissão, é que a tela certa é outra. HTMX recebe `204` + `HX-Redirect`.

Isso fecha a **trava opcional** que ficara em aberto na CORR-019. A revisão adversarial
confirmou que o redirect não entra em loop (o destino `/admin/` é o admin embutido do
Django, que não passa pelo mixin) — e há teste seguindo a cadeia de redirects até o fim.

**Migração `0003_alter_user_perfil` altera apenas `choices` — sem conversão de dados.** É
deliberado: superusuários existentes seguem com `perfil='DESUP'` e **mantêm** o acesso
operacional, então ninguém é trancado fora no deploy. A conta legada que já estava com `'ADMIN'`
passa a ser válida e a se comportar como TI.

> **Passo manual após o deploy:** promover as contas de TI/DEV para `perfil='ADMIN'` pelo admin do
> Django. Enquanto isso não for feito, elas continuam se comportando como Coord. DESUP.

### CORR-022 — remoção do diretório órfão

`templates/extracurricular/` (**sem** underscore) era código morto — não confundir com
`templates/extra_curricular/` (**com** underscore), que é o de verdade. As únicas referências ao
diretório eram `{% include %}` internos a ele mesmo. Removido por completo. A rota legada
`extracurricular_index` não foi tocada: é um `RedirectView` e não renderiza template.

### Ainda em aberto

- **`ForgotPasswordView`** (fluxo deslogado, com aprovação da DESUP) continua **sem rate-limit**.
  É um fluxo diferente do da CORR-020 e não foi pedido; fica registrado como candidato a item novo.
- Promover as contas de TI para `perfil='ADMIN'` é o passo manual descrito acima.
