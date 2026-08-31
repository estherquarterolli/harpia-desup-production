# Tarefas para o Agente Coder — Correções de Alocações Extracurriculares e Senha

> **Para:** Agente Coder (Gemini, Claude ou Codex — ver `docs/ia/coder.md`).
> **De:** Arquiteto/QA (Claude Opus — ver `docs/ia/claude-opus.md`).
> **Regras obrigatórias:** `docs/ia/agentes_strict_rules.md` e as regras de negócio do projeto.
>
> **⚠️ ESCOPO FECHADO.** Implemente **somente** o que está descrito abaixo. Nenhuma
> alteração pode fugir deste escopo. Se encontrar algo fora do escopo que pareça
> precisar de mudança, **apenas sinalize** — não altere.
>
> **Correção de rota deste documento (v2):** a Tarefa 1 foi **corrigida**. O “Status
> Autorizado/Indeferido” **não** é na tela de Alocação Curricular nem no model
> `AlocacaoCurricular` (como constava na v1). Ele é na tela de **Alocações
> Extracurriculares** e nos models de `extra_curricular`. Veja a Tarefa 1 abaixo.

---

## 🔢 ORDEM DE EXECUÇÃO (definida pelo cliente)

1. **ENTREGA 1 (fazer PRIMEIRO) — “Decisão da DESUP”: Tarefas 1.2 + 1.3 JUNTAS** (a 1.1 é só
   conferência). Ou seja, num **único entregável**:
   - **relocação** (1.2): botão “Finalizar” sai da lista e vai para o **detalhe**; a coluna
     “Status” da lista vira **somente leitura** e perde a caixa de horas;
   - **estado INDEFERIDO** (1.3): o seletor `parecer_desup` de **cada item** no detalhe ganha
     **“Indeferido”**; o “Finalizar” **consolida** (Aprovado **ou** Indeferido); badge vermelho.
2. **ENTREGA 2 (prioridade a definir pelo cliente)** — Tarefa 2 (Segurança/Senha — 2.1, 2.2, 2.3).

> Comece pela **Entrega 1 (1.2 + 1.3 juntas)**. Só avance para a Tarefa 2 quando o cliente
> indicar a prioridade.

---

## 0. Guardrails (leia antes de codar)

- **Segurança server-side sempre.** Toda autorização, filtro por unidade
  (`UnitBoundManager`/queryset) e trava de janela deve estar no backend, nunca só no
  HTMX/Alpine/CSS. Requisição inválida → `403` ou falha de validação controlada.
- **Não** altere dados de origem RH; ajustes ficam na camada DESUP.
- **Não** mude a stack, nem introduza SPA/React/Vue.
- **Não** reescreva o cálculo de CH que já existe em
  `apps/extra_curricular/services.py::get_pendencias_data` (`meta_horas`, `ch_alocada`,
  `ch_pendente`, `ch_faltante`) nem as properties de `Professor`. Você só vai **ler**
  esses valores. A mudança real é no **fluxo de status/parecer**.
- **Não** mexa na validação de SEI, nas janelas semestrais, nem no cálculo das horas de
  TCC/Extensão/Redução. Só toque no que as Tarefas 1.2/1.3 descrevem (fluxo e estado de
  decisão da DESUP).
- **Não** reescreva o **parecer por item** já existente no detalhe (`ParecerTCCForm`/
  `ParecerExtensaoForm`/`ParecerReducaoForm` + `_BaseParecerView`); ele será **reutilizado**.
- Regra de negócio vence UX. Tetos: **20h em sala** (`ContractType.max_class_hours`),
  **40h global** (`max_total_hours`).

**Decisões / alvo confirmados pelo cliente (não reabrir):**
1. A tela alvo da Tarefa 1 é **Alocações Extracurriculares** (`/extracurriculares/pendencias/`
   → `apps/extra_curricular/views.py::PendenciaListView` →
   `templates/extra_curricular/pendencia_list.html`; e o detalhe
   `templates/extra_curricular/pendencia_detail.html`).
2. O **Status “Indeferido/Autorizado”** reutiliza os models de **`extra_curricular`**
   (`PendenciaExtra.status` + `ParecerChoices` dos itens), **adicionando o estado
   “Indeferido”**, que hoje não existe. **Não** usar `AlocacaoCurricular`.

---

## 1. Corrigir “Alocações Extracurriculares” (tela `/extracurriculares/pendencias/`)

### Contexto do estado atual (confirmado no código — leia antes de codar)
- A tabela `templates/extra_curricular/pendencia_list.html` **já exibe** por docente as
  colunas: Docente, Processo SEI, Justificativa, **Meta CH**, **CH Alocada**,
  **CH Pendente**, **CH Justificada**, **Não alocado** e **Status**.
- Esses números vêm de `apps/extra_curricular/services.py::get_pendencias_data`:
  `meta_horas = tipo_contrato.max_class_hours` (padrão 20),
  `ch_pendente = max(meta − ch_alocada, 0)`, `ch_faltante = max(ch_pendente − ch_justificada, 0)`.
- **Onde a decisão da DESUP mora HOJE (o que está errado):** a coluna **“Status” da lista**
  contém um `<form>` interativo (linhas ~274–312 de `pendencia_list.html`) que faz `POST`
  para `extra_curricular:atualizar_status`, com `<input type="hidden" name="status"
  value="APROVADO">` **fixo**, um `textarea` `motivo_status_desup`, uma **caixa de horas
  `item_horas_aprovadas`** e o botão **“Finalizar”**. Ou seja: a **ação de decisão** e um
  **input de horas** estão embutidos numa coluna que deveria ser só informativa.
- **A tela de DETALHE** (`pendencia_detail.html` + `partials/_accordion_{tcc,extensao,reducao}.html`)
  **já tem** o **parecer por item** da DESUP (“Salvar Parecer” → `parecer_tcc/extensao/reducao`),
  que salva cada item e **deriva** o status via
  `apps/extra_curricular/services.py::sincronizar_status_pendencia`. Mas **não existe** ali um
  botão explícito de **“Finalizar”/consolidar**. As horas aprovadas já são definidas no
  detalhe (redução: campo `horas_aprovadas`; TCC/extensão: contagens `num_*_aprovados`).
- **Endpoint atual** `PendenciaStatusUpdateView` (`views.py` ~746–814, DESUP-only): grava
  `status`/`motivo_status_desup`, opcionalmente `item_horas_aprovadas` de um item, e
  **sobrescreve o `parecer_desup` de TODOS os itens** (bulk) — comportamento que a Tarefa 1.2
  vai substituir por **consolidação**.
- **Estado de rejeição ainda não existe:** `ParecerChoices` = `PENDENTE`/`APROVADO`;
  `PendenciaExtra.StatusChoices` = `RASCUNHO`/`ENVIADO`/`APROVADO`. Adicionar **INDEFERIDO**
  é a **Tarefa 1.3** (prioridade a definir).

---

### 1.1 — Meta CH e Não Alocado: **já existem** (apenas CONFERIR, não reimplementar)

**Objetivo:** garantir que os números continuem corretos após as mudanças das Tarefas 1.2/1.3.
`Meta CH = max_class_hours` (ex.: 20h) e `CH Pendente = Meta CH − CH alocada` já estão
implementados e corretos em `get_pendencias_data`. **Não reescreva.**

**Ponto a confirmar com o cliente (só sinalizar, não alterar sem OK):** hoje a coluna
rotulada **“Não alocado”** mostra `ch_faltante` (= `CH Pendente − CH Justificada`),
enquanto a fórmula que o cliente citou (“meta − CH alocada”) corresponde à coluna
**“CH Pendente”**. As duas informações já aparecem lado a lado. Se o cliente quiser
renomear/rearranjar rótulos, é ajuste de template — **aguarde confirmação**.

**Critério de aceite (1.1):** após as Tarefas 1.2/1.3, os valores de Meta CH / CH Pendente /
CH Justificada / Não alocado permanecem idênticos aos de antes (nenhuma regressão de cálculo).

---

### 1.2 — Reposicionar a decisão da DESUP (parte da ENTREGA 1 — junto com a 1.3)

**Objetivo:** tirar a **ação de decisão** (e o input de horas) da coluna “Status” da **lista**
e levá-la para a **tela de detalhe**. A coluna “Status” da lista passa a ser **somente
leitura**. Esta subseção é a parte de **UI/fluxo** da Entrega 1; entregue **junto** com a 1.3
(estado INDEFERIDO), formando o fluxo completo de decisão da DESUP.

#### a) Lista (`templates/extra_curricular/pendencia_list.html`) — coluna Status SOMENTE leitura
- **Remover** da coluna Status todo o `<form>` de `atualizar_status` (bloco ~274–312):
  o botão **“Finalizar”**, o `<input type="hidden" name="status" value="APROVADO">`, os
  hidden `item_tipo`/`item_pk`, o `textarea` `motivo_status_desup` **e a caixa
  `item_horas_aprovadas`** (o input de horas acoplado à coluna).
- Renderizar, **para todos os perfis** (coordenador e DESUP), **apenas o badge de status
  somente-leitura** — reaproveite o markup do branch read-only que já existe (~313–335).
  Rótulos: `RASCUNHO`→“Rascunho”, `ENVIADO`→“Pendente”, `APROVADO`→“Finalizado”,
  `INDEFERIDO`→“Indeferido”, sem pendência→“Sem registro”.
  > O badge de `INDEFERIDO` (vermelho) faz parte **desta mesma entrega** (implementado na 1.3).
  > Já inclua o mapeamento visual aqui.
- Pode manter o **eco somente-leitura** de `motivo_status_desup` (~332–334) abaixo do badge.
- **Não** remova as colunas de horas do relatório (CH Justificada / Não alocado continuam
  vindo de `get_pendencias_data`). Some **apenas** a caixa de input `item_horas_aprovadas`.

#### b) Detalhe (`templates/extra_curricular/pendencia_detail.html`) — botão “Finalizar” (consolidar)
- Adicionar, na área de ações do cabeçalho (perto do botão “Avisar Unidade”, ~196–203), um
  botão **“Finalizar”** visível **só para `is_desup`** (DESUP-only).
- **Comportamento = CONSOLIDAR (decisão confirmada pelo cliente):** o botão **não sobrescreve**
  pareceres. Ele apenas **fecha a pendência com base nos pareceres já salvos por item** (via
  `sincronizar_status_pendencia`). Opcional: um `textarea` `motivo_status_desup` ao lado do
  botão para registrar o motivo geral.
- POST volta para o **detalhe** (`extra_curricular:pendencia_detail pk=object.pk`).

#### c) Backend — `PendenciaStatusUpdateView` (`atualizar_status`) passa a CONSOLIDAR
- **Remover** o bulk-overwrite de `parecer_desup` de todos os itens e o tratamento de
  `item_horas_aprovadas` (agora superados pelo parecer por item no detalhe).
- Passar a: (a) gravar `motivo_status_desup` se enviado; (b) chamar
  **`sincronizar_status_pendencia(pendencia)`** (reutilizar `services.py`) para **derivar** o
  status a partir dos itens; (c) **redirecionar ao detalhe** (`pendencia_detail`).
- Manter **`allowed_profiles = ["DESUP"]`** e o isolamento por unidade.
- Hoje `sincronizar_status_pendencia`: todos os itens `APROVADO` (≥1) → `APROVADO` (Finalizado);
  senão, se não é rascunho → `ENVIADO` (Pendente). Logo, se houver item sem parecer, o
  “Finalizar” mantém “Pendente” — **aceitável**. Opcional: `messages.warning` (“há itens sem
  parecer”).
> Como o “Salvar Parecer” por item **já** chama `sincronizar_status_pendencia`, o botão
> “Finalizar” é a ação **explícita** de fechamento + registro de motivo. **Não** apaga
> pareceres nem recalcula horas.

**Critérios de aceite (1.2):**
- Na **lista**, a coluna “Status” mostra **apenas o badge** (sem `<form>`, sem botão
  “Finalizar”, sem `textarea`, **sem a caixa de horas**), para DESUP e coordenador.
- No **detalhe**, existe o botão **“Finalizar”** (DESUP-only). Clicar **consolida** o status a
  partir dos pareceres por item, **sem apagar** os pareceres e **sem** recalcular horas.
- Autorizar todos os itens pelo detalhe + “Finalizar” → pendência `APROVADO`/“Finalizado”;
  redireciona de volta ao detalhe.
- `COORDENADOR_UNIDADE` **não** finaliza: `POST` direto em `atualizar_status` → `403`.
- Nenhuma regressão nos números de CH da lista (Tarefa 1.1).

---

### 1.3 — Estado INDEFERIDO + Autorizar/Indeferir por item (parte da ENTREGA 1 — junto com a 1.2)

> **Entregar JUNTO com a 1.2** (mesma Entrega 1 “Decisão da DESUP”). Aqui a decisão
> Autorizar/Indeferir acontece **por item, no detalhe** (não com botões na lista). Resultado
> combinado: o seletor `parecer_desup` de cada item passa a ter **Pendente/Aprovado/Indeferido**
> e o botão “Finalizar” (1.2) consolida a pendência como Aprovado **ou** Indeferido.

**Objetivo:** a DESUP deve poder **autorizar** ou **indeferir** cada justificativa; o backend
reflete a decisão (novo estado **Indeferido**) e a parte visual acompanha (badge próprio).
Autorizar = `APROVADO` (já existe); Indeferir = `INDEFERIDO` (novo).

#### a) Models — `apps/extra_curricular/models.py`
1. Em **`ParecerChoices`**, adicionar o estado de rejeição:
   ```python
   class ParecerChoices(models.TextChoices):
       PENDENTE   = "PENDENTE",   "Pendente"
       APROVADO   = "APROVADO",   "Aprovado"
       INDEFERIDO = "INDEFERIDO", "Indeferido"   # NOVO
   ```
2. Em **`PendenciaExtra.StatusChoices`**, adicionar o status agregado de indeferimento:
   ```python
   class StatusChoices(models.TextChoices):
       RASCUNHO   = "RASCUNHO",   "Rascunho"
       ENVIADO    = "ENVIADO",    "Enviado para DESUP"
       APROVADO   = "APROVADO",   "Finalizado"
       INDEFERIDO = "INDEFERIDO", "Indeferido"    # NOVO
   ```
3. `makemigrations extra_curricular` (mudança de `choices` não altera schema, mas
   mantenha a migração versionada).

> Os selects de parecer nos formulários (`ParecerTCCForm`, `ParecerExtensaoForm`,
> `ParecerReducaoForm` em `forms.py`) usam `parecer_desup` como `Select` — eles passam a
> exibir **“Indeferido”** automaticamente ao adicionar o choice. Não precisa mexer nos forms.

#### b) Service — `apps/extra_curricular/services.py::sincronizar_status_pendencia`
Implementar o ramo de rejeição (a docstring já menciona “rejeitado => REJEITADO”, mas o
código **não** trata isso hoje). Regra:
- Se **qualquer** item tiver `parecer_desup == ParecerChoices.INDEFERIDO` → status da
  pendência = `INDEFERIDO`.
- Senão, manter a lógica atual (todos `APROVADO` e ≥1 item → `APROVADO`; senão, se já
  enviado → `ENVIADO`; rascunho continua `RASCUNHO`).

Isso garante que, no fluxo por item (tela de detalhe / `_BaseParecerView`), indeferir um
item reflita no status agregado. O botão **“Finalizar”** (Tarefa 1.2) consolida a pendência
como `INDEFERIDO` quando houver item indeferido.

> A view `PendenciaStatusUpdateView` **não** recebe `INDEFERIDO` por parâmetro — na Tarefa 1.2
> ela passou a **consolidar** (derivar o status via `sincronizar_status_pendencia`). A decisão
> Autorizar/Indeferir é **por item**, no detalhe, e permanece **DESUP-only**.

#### c) Detalhe (partials) — a decisão por item ganha “Indeferido”
- O `select` `parecer_desup` de cada item (`ParecerTCCForm`/`ParecerExtensaoForm`/
  `ParecerReducaoForm`, já renderizados em `partials/_accordion_*`) passa a exibir
  **“Indeferido”** automaticamente ao adicionar o choice — **não precisa mexer nos forms**.
- Ao salvar um item como Indeferido (fluxo `_BaseParecerView`, já existente), o status
  agregado reflete (via **b**). Ao indeferir, **não** consolidar horas: `ch_total_justificada`
  já só soma quando `APROVADO`.

#### d) Badge INDEFERIDO — lista e detalhe
- CSS (bloco `extra_head` de cada template):
  `.badge-indeferido { background:#fee2e2; color:#991b1b; }`.
- Renderizar o badge vermelho quando o status/parecer for `INDEFERIDO`: **no badge
  read-only da lista** (o da Tarefa 1.2.a) e **no detalhe** (badge da pendência e do item).
- **Filtro “Filtrar por Status”** (client-side): acrescentar a opção `Indeferido` e mapear
  `data-status = 'Indeferido'` quando `status_item == 'INDEFERIDO'`. Se acrescentar o filtro
  server-side em `PendenciaListView` (`status_filtro`), inclua o caso:
  ```python
  elif status_filtro == 'indeferido' and pendencia and status_item == 'INDEFERIDO':
      filtered_data.append(item)
  ```

**Critérios de aceite (1.3):**
- No detalhe, a DESUP consegue **Indeferir** um item; `parecer_desup = INDEFERIDO` persiste.
- `sincronizar_status_pendencia` retorna `INDEFERIDO` quando ≥1 item está indeferido; o
  “Finalizar” (Tarefa 1.2) consolida a pendência como `INDEFERIDO`.
- Ao **Autorizar** todos os itens + “Finalizar”: pendência `APROVADO`/“Finalizado”, badge verde.
- A CH justificada consolidada **não** soma itens indeferidos.
- Badge vermelho “Indeferido” aparece na **lista** (read-only) e no **detalhe**.
- `COORDENADOR_UNIDADE` **não** altera parecer/status (`DESUP`-only; `POST` direto → `403`);
  coordenador não altera pendência de outra unidade.
- O motivo (`motivo_status_desup` / `motivo_parecer`) continua sendo gravado e exibido.

---

## 2. Segurança e Usabilidade — Senha

### 2.1 — “Esqueci a senha” deve enviar um link direto ao próprio usuário

**Objetivo:** ao usar “Esqueci a senha”, o **próprio usuário da unidade** recebe, no seu
e-mail, um **link para trocar a senha atual** (autoatendimento), em vez de depender de
aprovação manual da DESUP.

**Estado atual (confirme):** `apps/accounts/views.py::ForgotPasswordView.post` hoje cria
um `PasswordResetRequest` e **notifica DESUP/coordenadores para aprovar** (a senha só é
resetada para o padrão após aprovação em `ApprovePasswordResetView`). O usuário **não**
recebe link nenhum.

**Reutilize a infraestrutura que já existe** (não crie model novo):
- Model `apps/accounts/models.py::SelfPasswordChangeRequest` (token UUID, expira em 1h,
  uso único).
- View `apps/accounts/views.py::PasswordChangeConfirmView` + rota
  `password_change_confirm` (`config/urls.py`) — já permite que um usuário **não
  autenticado** com token válido defina nova senha.
- Task de e-mail `apps/core/tasks.py::send_email_task`.

**O que fazer em `ForgotPasswordView.post`:**
1. Buscar o usuário pelo e-mail informado.
2. Se existir: criar um `SelfPasswordChangeRequest` para ele e montar o link absoluto
   (`request.build_absolute_uri(reverse('password_change_confirm', kwargs={'token': ...}))`).
3. Enviar o e-mail **para o próprio usuário** (`user.email`) com o link, via
   `send_email_task.delay(...)` dentro de `transaction.on_commit(...)` (mesmo padrão já
   usado em `CustomPasswordChangeView._request_email_confirmation`).
4. Registrar auditoria (`PASSWORD_RESET_LINK_SENT`, por exemplo).
5. **Anti-enumeração de usuários:** responda **sempre** com a **mesma mensagem genérica**
   de sucesso (“Se o e-mail existir, enviaremos um link de troca de senha”), exista o
   usuário ou não. Não revele que o e-mail não foi encontrado.

**Template — `templates/registration/forgot_password.html`:**
- Ajustar o texto de ajuda (hoje diz que a solicitação vai “aos administradores do DESUP”)
  para: “Enviaremos um link de redefinição para o seu e-mail cadastrado.”
- Manter o botão/fluxo; só muda a cópia e a mensagem de retorno.

**Decisão a sinalizar (não implementar sem OK):** o fluxo antigo de aprovação pela DESUP
(`ApprovePasswordResetView`, `PasswordResetRequest`, notificações) pode ser **mantido em
paralelo** (trilha/monitoramento) ou **removido**. Para esta tarefa, **mantenha-o intacto**
e apenas **adicione** o envio do link direto ao usuário. Se o cliente quiser remover o
fluxo antigo, é outra tarefa.

**Critérios de aceite (2.1):**
- Usuário existente informa o e-mail → recebe e-mail com link
  `.../accounts/password_change/confirm/<token>/`.
- O link abre a tela de definição de nova senha **sem exigir login**; ao salvar, a senha
  muda e o token vira usado/expirado (uso único).
- E-mail inexistente → **mesma** mensagem de sucesso genérica (sem enumeração).
- Em dev sem Redis, o Celery roda **eager** (`CELERY_TASK_ALWAYS_EAGER`) e o e-mail é
  processado; valide com o backend de e-mail configurado (ex.: console/SMTP de teste).

---

### 2.2 — Verificar se “Forçar troca de senha” (admin do super admin) funciona

**Objetivo:** confirmar que marcar **“Forçar troca de senha”** no admin realmente obriga
o usuário a trocar a senha no próximo acesso — e corrigir se houver falha.

**Estado atual (confirmado pelo arquiteto — apenas verifique/valide):**
- Campo `forcar_troca_senha` exposto e editável no admin
  (`apps/accounts/admin.py`: `list_display`, `list_filter`, `fieldsets`; e em
  `apps/accounts/forms.py::CustomUserChangeForm.fields`). ✔
- Middleware `apps/accounts/middleware.py::PasswordChangeForceMiddleware` **está
  registrado** em `config/settings/base.py` (linha ~49), após o `AuthenticationMiddleware`. ✔
- Ao trocar a senha com sucesso, `CustomPasswordChangeView.form_valid` zera a flag. ✔
- **Superusuários são isentos por design** (o middleware faz `return` cedo para
  `is_superuser`). Isso **não é bug** — mas se o cliente esperava forçar troca também para
  super admins, sinalize (é uma decisão, não implemente sem OK).

**O que fazer (verificação + teste, corrigir só se quebrado):**
1. Verificação manual: no admin, marcar `forcar_troca_senha = True` para um usuário
   `COORDENADOR_UNIDADE`; efetuar login com ele; confirmar redirecionamento forçado para
   `password_change` em qualquer rota protegida (inclusive resposta `HX-Redirect` para
   requisições HTMX); após trocar, confirmar que a flag zera e a navegação libera.
2. Verificar que a flag realmente **persiste** ao salvar no admin (o campo está no form).
3. **Adicionar teste** em `apps/accounts/tests.py` cobrindo:
   - usuário não-super com `forcar_troca_senha=True` é redirecionado para `password_change`;
   - após trocar a senha, `forcar_troca_senha` fica `False` e o acesso é liberado;
   - superusuário **não** é bloqueado (comportamento esperado atual).
4. Se algum passo falhar, corrigir **apenas** o ponto que estiver quebrado (sem refatorar
   o fluxo inteiro) e documentar a causa no PR.

**Critérios de aceite (2.2):**
- Teste automatizado novo passando.
- Evidência (print/descrição) de que o fluxo manual funciona para `COORDENADOR_UNIDADE`.
- Comportamento de superusuário documentado (isento) — flag para o cliente decidir.

---

### 2.3 — BUG: “This field is required” ao trocar a senha (relatado pelo Super Admin) — **investigar e corrigir**

**Sintoma relatado pelo cliente:** ao tentar trocar a própria senha **como Super Admin**,
o sistema abre um **pop-up de erro** com a mensagem **“This field is required”**, mesmo
tendo digitado uma senha **válida** — o checklist de requisitos ficou **todo verde**.

**Causa provável (mapeada pelo arquiteto na leitura do código — confirmar em runtime):**
1. O menu **“Alterar senha”** (`templates/base.html`, `{% url 'password_change' %}`) leva a
   `apps/accounts/views.py::CustomPasswordChangeView`. Quando `request.user.forcar_troca_senha`
   é **True** (situação típica ao testar o próprio “forçar troca”), a view renderiza
   `templates/registration/password_change_form.html` com o **`SetPasswordForm`**
   (dois campos: **Nova Senha** = `new_password1` e **Confirmar Senha** = `new_password2`).
2. O **checklist “verdinho” valida APENAS o primeiro campo** (`new_password1`) — ver o JS
   em `password_change_form.html` (a função `updateChecklist` só escuta `passwordInput`,
   que é `id_new_password1`). **O campo `new_password2` (Confirmar Senha) NÃO tem validação
   client-side alguma.**
3. Quando um dos dois campos chega **vazio** ao backend, o `SetPasswordForm` do Django
   levanta o erro padrão **“This field is required”** naquele campo. O template **agrega
   TODOS os erros de campo num único pop-up SweetAlert genérico** (bloco `Swal.fire` das
   linhas ~68–90), **sem indicar QUAL campo falhou**. Por isso o usuário enxerga “senha
   válida/verde” e mesmo assim recebe “This field is required” sem contexto.

> Observação importante de diagnóstico: “This field is required” é **especificamente** o
> erro de **campo obrigatório vazio** — **não** é divergência de senhas (essa seria
> “The two password fields didn’t match”) nem regra de força de senha. Ou seja: **algum
> dos dois campos está indo vazio** no POST.

**Passo 0 — reproduzir e confirmar a causa antes de corrigir (obrigatório):**
- No handler do POST (ou via `form.errors` no `form_invalid`), **logar qual chave** de
  `form.errors` disparou (`new_password1` vs `new_password2`) e por qual **rota** o usuário
  chegou: `CustomPasswordChangeView` (com `forcar_troca_senha=True`) **ou**
  `PasswordChangeConfirmView` (link por token). Isso confirma a hipótese acima.
- Se, mesmo com **os dois campos preenchidos**, um deles chegar vazio no POST, então há um
  bug de submissão/markup (ex.: campo fora do `<form>`, `name` divergente, `disabled`) —
  investigar o HTML renderizado do `SetPasswordForm`. (A leitura estática **não** indicou
  isso — os dois inputs estão dentro do `<form id="password-form">` com `name` corretos —
  mas confirme em runtime.)

**✅ DECISÃO CONFIRMADA PELO CLIENTE (padrão correto):** a troca de senha por
**autoatendimento** deve, **para TODOS os usuários — inclusive o Super Admin** —, seguir o
**fluxo de link por e-mail** (o mesmo já usado em `CustomPasswordChangeView` quando
`forcar_troca_senha=False`: confirma o e-mail → recebe link → define nova senha). O
formulário inline de dois campos (`SetPasswordForm` em `password_change_form.html`) **não**
deve ser o caminho do autoatendimento. Isso se conecta à **2.1** (esqueci a senha manda
link) e à **2.2** (isenção do super admin).

**Correção esperada — PRINCIPAL (roteamento): garantir o fluxo de link por e-mail p/ todos**
- Em `apps/accounts/views.py::CustomPasswordChangeView`, o autoatendimento (“Alterar senha”)
  deve levar **qualquer** usuário — inclusive `is_superuser` — ao fluxo de **confirmar e-mail
  → enviar link** (`_request_email_confirmation` / `password_change_email_prompt.html`),
  **não** ao `SetPasswordForm` de dois campos.
- **Atenção ao acoplamento com `forcar_troca_senha`:** hoje a decisão “form inline × e-mail”
  é feita por `if not request.user.forcar_troca_senha`. O fluxo **inline de dois campos** só
  faz sentido no **primeiro acesso obrigatório** (usuário caiu no `PasswordChangeForceMiddleware`
  e precisa trocar ali mesmo para destravar). **Não** quebre esse caso. O que muda: o
  **autoatendimento voluntário** (clicar em “Alterar senha” no menu) vai sempre para o e-mail.
  - Se o cliente quiser que **até o primeiro acesso** use link por e-mail, isso é decisão
    adicional — **sinalize**, não implemente sem OK (mudaria o destravar do middleware).
- Como o super admin passa a receber link, valide o envio de e-mail no ambiente (Celery eager
  em dev; backend de e-mail configurado). Registrar auditoria do envio (padrão já existente).

**Correção esperada — SECUNDÁRIA (hardening do form inline que permanece no 1º acesso):**
Mesmo roteando o autoatendimento para o e-mail, o `password_change_form.html` continua sendo
usado no **primeiro acesso obrigatório** — então corrija também o feedback enganoso ali:
- **`templates/registration/password_change_form.html`:**
  1. **Estender o checklist / guard client-side ao segundo campo:** exigir que
     **“Confirmar Senha”** esteja preenchida **e igual** à “Nova Senha” antes de habilitar o
     submit (ou, no mínimo, exibir aviso inline). Hoje o JS ignora `new_password2`.
  2. **Deixar o erro apontar o campo certo:** o template **já renderiza** os erros inline
     por campo (`form.new_password1.errors` e `form.new_password2.errors`, linhas ~103–107 e
     ~151–155), mas o **pop-up SweetAlert genérico** some com essa informação. Ajustar o
     pop-up para **nomear o campo** (ex.: “Confirmar Senha: campo obrigatório”) **ou**
     remover o pop-up agregado e confiar nos erros inline por campo (mais claro). Traduzir a
     mensagem para PT-BR (“Este campo é obrigatório.”) — hoje aparece em inglês.
  3. Garantir que o botão de **mostrar/ocultar senha** (`toggle-password`) não interfira na
     submissão (ele troca `type` para `text`; confirmar que `name`/`value` seguem intactos).
- **Não** enfraquecer nenhum validador de senha do backend; esta parte é **UX/feedback**, não
  regra de segurança.

**Critérios de aceite (2.3):**
- **Roteamento (principal):** clicar em “Alterar senha” (autoatendimento) como
  **Super Admin** — e como qualquer perfil — leva ao fluxo de **confirmar e-mail → link**,
  **não** ao formulário inline de dois campos. O super admin recebe o link no e-mail e
  conclui a troca por ele. O “This field is required” **não** ocorre mais nesse caminho.
- **Primeiro acesso obrigatório preservado:** usuário com `forcar_troca_senha=True` continua
  destravando corretamente (sem regressão do middleware).
- Reprodução documentada: qual campo (`new_password1`/`new_password2`) e qual rota geravam
  o “This field is required”.
- **Hardening do form inline (1º acesso):** com um campo vazio, a UI mostra **claramente qual
  campo** falta (mensagem em PT-BR, associada ao campo), **sem** o pop-up genérico; com ambos
  válidos, a troca conclui.
- Testes em `apps/accounts/tests.py`:
  - autoatendimento como **superusuário** em `password_change` (GET/POST) segue o fluxo de
    **e-mail/link** (não renderiza/valida o `SetPasswordForm` de dois campos);
  - no fluxo inline do 1º acesso (`forcar_troca_senha=True`), POST com `new_password2`
    vazio retorna erro **no campo** `new_password2`; POST com ambos válidos altera a senha;
  - `PasswordChangeConfirmView` (link por token) altera a senha e invalida o token.

---

## 3. Testes obrigatórios (inclua no PR)

Além dos testes citados por tarefa, cubra os **testes negativos** (exigência de
`agentes_strict_rules.md`):

- **Relocação da decisão (1.2 — Entrega 1):**
  - A **lista** não renderiza mais `<form>` de status na coluna Status (sem botão
    “Finalizar”, sem `textarea`, **sem input `item_horas_aprovadas`**) — só o badge.
  - O **detalhe** tem o botão “Finalizar” (DESUP-only); ao consolidar, `atualizar_status`
    **não** apaga `parecer_desup` dos itens e **não** recalcula horas; o status é derivado
    por `sincronizar_status_pendencia` (todos aprovados → `APROVADO`).
  - `COORDENADOR_UNIDADE` recebe `403` ao tentar `POST` em `atualizar_status`.
- **Estado INDEFERIDO (1.3 — Entrega 1):**
  - DESUP consegue **Indeferir** um item no detalhe: `parecer_desup = INDEFERIDO` persiste.
  - `sincronizar_status_pendencia` retorna `INDEFERIDO` quando ao menos um item está
    indeferido; “Finalizar” consolida a pendência como `INDEFERIDO`.
  - CH justificada consolidada (`ch_total_justificada`) **não** soma quando indeferido.
  - `COORDENADOR_UNIDADE` recebe `403` ao tentar `POST` em parecer; coordenador não altera
    pendência de outra unidade.
- **Regressão de cálculo:** Meta CH / CH Pendente / Não alocado permanecem corretos após
  as mudanças (nada em `get_pendencias_data` foi alterado).
- **Reset de senha:** token de troca é **uso único** e expira (reuso/expirado → inválido);
  e-mail inexistente não vaza enumeração.
- **Forçar troca:** conforme 2.2.
- **Bug “This field is required” (2.3):** POST em `password_change` com `new_password2`
  vazio devolve erro **associado ao campo** `new_password2` (não pop-up genérico); POST com
  ambos os campos válidos conclui a troca.

---

## 4. Fora de escopo (NÃO tocar nesta entrega)

- A tela de **Alocação Curricular** (`/alocacao-curricular/`) e o model `AlocacaoCurricular`
  — **não** são o alvo desta entrega. Não mexer.
- O **cálculo de CH** em `get_pendencias_data` e as properties de `Professor` — apenas ler;
  não reescrever.
- O **parecer por item** já existente no detalhe (`ParecerTCCForm`/`ParecerExtensaoForm`/
  `ParecerReducaoForm` + `_BaseParecerView` + endpoints `parecer_*`) — **reutilizar**, não
  reescrever. A Tarefa 1.2 apenas **reposiciona** a decisão e faz `atualizar_status`
  **consolidar** (em vez de sobrescrever).
- Regex/validação de formato do SEI (divergência conhecida entre `agentes_strict_rules.md`
  e o código; **não** alterar aqui).
- Timeout de sessão por inatividade, MFA, throttle de login por biblioteca (django-axes).
- Regras de cálculo de TCC/Extensão/Redução e janelas semestrais.
- Remoção do fluxo de aprovação de reset pela DESUP (só sinalizar — ver 2.1).

---

## 5. Formato de entrega esperado (padrão `docs/ia/coder.md`)

Para **cada** tarefa entregue:
1. Objetivo da etapa
2. Estratégia técnica
3. Arquivos envolvidos
4. Código completo por arquivo
5. Explicação pedagógica curta
6. Checklist de validação (como testar manualmente)
7. Próximo passo sugerido

**Ordem de execução (relembrando):** **Entrega 1** = Tarefas **1.2 + 1.3 JUNTAS** (“Decisão da
DESUP”: relocação + estado INDEFERIDO), fazer **PRIMEIRO**. Só siga para a **Tarefa 2** (senha)
quando o cliente definir a prioridade.

Ao final, liste explicitamente os **pontos sinalizados** (decisões pendentes do cliente):
rótulo “Não alocado” × “CH Pendente” (1.1), destino do fluxo antigo de reset (2.1) e — só
se aparecer — a dúvida de estender o link por e-mail **também ao primeiro acesso obrigatório**
(2.3). **Já decididos (não reabrir):** (a) o botão “Finalizar” fica no **detalhe** e
**consolida** os pareceres por item; a coluna “Status” da **lista** é **somente leitura**,
sem caixa de horas (1.2); (b) autoatendimento de troca de senha usa **link por e-mail para
todos, inclusive Super Admin** (2.3).

> Depois da implementação, **envie o diff para revisão do Claude Opus** (QA) antes de
> consolidar — foco em segurança, escopo por unidade e não-regressão do cálculo de CH e
> dos estados de justificativa.
