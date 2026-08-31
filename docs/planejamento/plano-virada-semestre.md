# Plano de implementação — Virada de semestre (arquivamento + backup/PDF + reset de alocação)

> **Documento de handoff.** Este plano foi levantado e validado com o gestor DESUP, mas **ainda
> não foi implementado**. Outro agente pode executá-lo a partir daqui. Data do levantamento:
> 2026-07-14. Projeto: **HARPIA-DESUP / AllocGest-DESUP** (Django 6, `config.settings.development`,
> `.venv` na raiz do repo). **Commits são feitos somente pelo usuário** — não commitar.

---

## 1. Contexto e objetivo

Quando o semestre letivo vira, a DESUP abre uma nova **Janela de Entrega** para o próximo
semestre. Hoje isso não tem efeito nenhum no sistema. Precisamos do ciclo de virada:

1. **Atualizar o "semestre atual"** a partir do semestre da janela nova (hoje não há valor
   persistido — é derivado do relógio).
2. **Backup automático** (matrizes + professores + alocação + justificativas) → histórico
   read-only no banco + registro em auditoria **e** um **.pdf** consolidado.
3. **Matrizes anteriores viram histórico read-only**, preservadas e separadas por semestre.
4. **"Zerar" a alocação**: no novo semestre todos os professores começam sem alocação para serem
   realocados nas matrizes novas (professores de disciplinas mudam a cada semestre).

## 2. Decisões validadas com o usuário (não reabrir sem perguntar)

| Tema | Decisão |
|------|---------|
| **Gatilho** | Ação **explícita** da DESUP — botão **"Virar semestre"** com tela de confirmação. Nada automático. |
| **Zerar** | **Arquivar todas as matrizes vigentes → histórico**, carimbadas com o semestre que fecha. Professores zeram via `is_vigente`. A unidade cria/duplica matrizes novas depois. |
| **Backup no banco** | **Preservar como histórico read-only + registro em `AuditoriaGlobal`**. O **PDF é a cópia portável**. **Sem tabelas de snapshot novas.** |
| **PDF** | **Um consolidado global** por semestre (todas as unidades), salvo no bucket Supabase. |
| **Ponto de partida (semestre inicial)** | Go-live = **2026.2**. Semear `ConfiguracaoSistema.semestre_vigente = "2026.2"` via **data migration** (determinístico, entra no banco no deploy, sem passo manual). *(Decisão 2026-07-15.)* |
| **Edição do "semestre atual"** | **Read-only** em todo o sistema; avança **somente** pelo botão "Virar semestre" (DESUP). Correção pontual via **Django admin** (superuser) — sem campo editável livre em tela comum, pois o valor controla todo o escopo por semestre. *(Decisão 2026-07-15.)* |
| **Auto-arquivamento na publicação** | **REMOVIDO** (ver `docs/checklist_correcao.md` CORR-011). Matrizes do mesmo curso/unidade em **turnos diferentes coexistem como vigentes**. O arquivamento em massa passa a ser **exclusivo desta virada de semestre**; arquivar/reativar pontual é o CORR-012. *(Decisão 2026-07-15.)* |

O usuário também pediu que o **Histórico** fique de fácil acesso, **separado das matrizes vigentes**
e **navegável por semestre**, sem poluir o trabalho atual.

## 3. Achados da exploração (mapa do código — file:line)

**Semestre atual / fonte de verdade**
- `apps/extra_curricular/utils.py:5` — `semestre_atual()` é **derivado do relógio** (mês ≤6 → `.1`,
  senão `.2`). **Não há valor persistido** em lugar nenhum (não existe `SiteConfig`/singleton).
- Consumidores: `apps/professors/models.py:177-183` (`ch_justificada`, já filtra por semestre);
  `apps/extra_curricular/views.py:49-53` (`_semestre_atual()` delega para o util) e usos em
  `:73,172,219,251,602,661`.
- **Duplicata inline** da regra de semestre em `apps/allocations/views.py:182-185` (precisa passar
  a usar `semestre_atual()`).

**Janela de Entrega**
- `apps/core/models.py:31-69` — `JanelaEntrega` tem `semestre` (texto), `data_inicio/fim`, `status`
  (Aberto/Fechado/Reaberto, default Fechado), `unidade` (null = global). `is_ativa` em `:65`.
- Criar/abrir janela **não tem efeito colateral** hoje (`JanelaEntregaCreateView`/`UpdateView` são
  genéricas — `apps/core/views.py:402-412`). Forms em `apps/core/views.py:249-357` (o
  `apps/core/forms.py` é código morto).
- `apps/core/services.py` — lifecycle da janela (fechar expiradas, enforcement). `urls` em
  `apps/core/urls.py` (janelas em `entregas/...`).

**Alocação e "zerar"**
- Alocação = `MatrixComponent.docente` (`apps/courses/models.py:197-204`, `on_delete=PROTECT`).
  O app `apps/allocations/` **não guarda alocação por professor** — só `AlocacaoCurricular`
  (workflow por curso/semestre/turno, sem FK de professor).
- `Professor.ch_alocada` (`apps/professors/models.py:193`) **só conta `matriz__is_vigente=True`** →
  **arquivar as matrizes já zera todo professor automaticamente**, sem apagar `docente`.
- Fluxos de duplicar/importar matriz **não copiam `docente`** (`apps/courses/views.py:454-463` e
  `:542-549`) → matriz nova nasce com `docente=None`, status `SEM_PROFESSOR`.

**Matrizes / histórico**
- `CurriculumMatrix` (`apps/courses/models.py:80`): `is_vigente`, `is_rascunho`, `periodo_letivo`
  (`:122`, **inerte** — só escrito por seeds, nunca lido em query de app).
- Publicar matriz arquiva as vigentes do mesmo curso hoje (`apps/courses/views.py:198-209`) — **mas
  esse auto-arquivamento será REMOVIDO** (CORR-011): turnos diferentes coexistem como vigentes e o
  arquivamento em massa passa a ser **exclusivo desta virada**. Editar só é permitido em rascunho
  (`:257`). Lista já tem filtro **Vigente/Rascunho/Histórico** (`:85-91`) e selo/cadeado "Bloqueado"
  (`templates/courses/matrix_list.html:119-137`).

**PDF / storage / infra**
- **Nenhuma lib de PDF** instalada (`requirements.txt`). Storage = **Supabase bucket** via
  `STORAGES` (`config/settings/base.py:176-183`, `apps/core/storage.py`); em dev cai em
  `FileSystemStorage` **sem `MEDIA_ROOT`** configurado.
- **Sem tabela de snapshot/versionamento**; "histórico" hoje é só flag `is_vigente=False`. Único
  export existente: `ExportarLogsView` CSV (`apps/core/views.py:514`). Auditoria central:
  `AuditoriaGlobal` (`apps/core/models.py:133`).
- **Celery + Redis disponíveis** (`config/celery.py`, uma task `send_email_task` em
  `apps/core/tasks.py`). Sem beat/cron.

## 4. Arquitetura da mudança

### 4.1. Semestre atual persistido — `ConfiguracaoSistema` (singleton)
- `apps/core/models.py`: novo model `ConfiguracaoSistema` com `semestre_vigente` (CharField,
  blank) + `atualizado_em`. Classmethod `get_solo()` (get_or_create pk=1); `save()` força pk=1 e
  invalida cache (`cache.delete('cfg_semestre_vigente')`). **Migration nova** (`makemigrations core`).
- **Seed do ponto de partida (2026.2):** **data migration** que cria o singleton já com
  `semestre_vigente = "2026.2"` (idempotente: `get_or_create` pk=1, só define o valor se estiver
  vazio — não sobrescreve um valor já avançado pela virada). É como o go-live começa em 2026.2 sem
  passo manual.
- **Política de edição:** o valor é **read-only** na UI e só muda pelo `virar_semestre()` (botão
  DESUP). Para correção excepcional, expor `ConfiguracaoSistema` no **Django admin** (superuser).
  **Não** criar campo/form editável livre em tela comum.
- **No admin do model,** exibir `semestre_vigente` + `atualizado_em` (read-only exceto para
  superuser) para dar visibilidade do valor corrente.
- `apps/extra_curricular/utils.py` `semestre_atual()`: passa a ler
  `ConfiguracaoSistema.get_solo().semestre_vigente` via `cache.get_or_set` (é chamada em loop no
  dashboard — não fazer 1 query por professor); **fallback para a regra do relógio** se vazio.
  Manter a assinatura atual.
- `apps/allocations/views.py:182-185`: remover a regra de semestre duplicada → chamar `semestre_atual()`.

### 4.2. Serviço de virada — `apps/core/services_semestre.py` (novo)
`virar_semestre(novo_semestre: str, *, usuario) -> dict`, tudo em `transaction.atomic()`:
1. `semestre_fechando = semestre_atual()`; validar formato `AAAA.S` e que `novo_semestre` é
   diferente/posterior (guard contra duplo clique / semestre igual ou anterior).
2. Gerar o **PDF** do semestre que fecha (§4.3) e salvar no storage → guardar o `path`.
3. Arquivar matrizes vigentes carimbando o semestre:
   ```python
   CurriculumMatrix.objects.filter(is_vigente=True, is_rascunho=False).update(
       is_vigente=False, periodo_letivo=semestre_fechando)
   ```
   (rascunhos têm `is_vigente=False` → naturalmente preservados para o novo semestre.)
4. `cfg.semestre_vigente = novo_semestre; cfg.save()`.
5. `AuditoriaGlobal.objects.create(acao="VIRADA_SEMESTRE", detalhes=...)` com
   `{fechando, novo, qtd_matrizes, pdf_path}` — é o "backup no banco" + ponteiro do PDF.
6. Retornar resumo (contagens + url do PDF) para a view exibir.

### 4.3. PDF — `apps/core/services_pdf.py` (novo)
- **Dependência nova:** `xhtml2pdf` (Python puro, sem libs de sistema — ok no Windows) em
  `project_root/requirements.txt`.
- `gerar_pdf_snapshot_semestre(semestre) -> (bytes, path)`: monta contexto (matrizes do semestre
  agrupadas por unidade/curso com componentes+docentes; professores com
  `ch_alocada`/`ch_justificada`/`ch_total`; justificativas `PendenciaExtra` do semestre) e renderiza
  `templates/core/pdf/snapshot_semestre.html` via `xhtml2pdf.pisa`. Salvar com
  `default_storage.save(f"backups/semestre/{semestre}/snapshot_{semestre}.pdf", ContentFile(pdf))`.
  **Importante:** capturar o snapshot **antes** de arquivar as matrizes (enquanto ainda estão
  vigentes) — ordem no serviço: gerar PDF → depois arquivar.
- `config/settings/base.py`: definir `MEDIA_ROOT`/`MEDIA_URL` para o fallback `FileSystemStorage`
  de dev (hoje ausentes); em prod continua Supabase.

### 4.4. UI — disparo e download (DESUP)
- `apps/core/views.py`: `VirarSemestreView` (DESUP-only, padrão `PerfilRequiredMixin`/`DesupOnlyMixin`):
  **GET** mostra confirmação com o impacto (semestre X→Y, N matrizes a arquivar, aviso do PDF);
  **POST** chama `virar_semestre(...)` e redireciona com toast de sucesso + link do PDF. Reusar o
  padrão de `messages`.
- `apps/core/urls.py`: `path('semestre/virar/', VirarSemestreView.as_view(), name='virar_semestre')`
  + rota de download do último backup (lê o `pdf_path` do último `AuditoriaGlobal`
  `VIRADA_SEMESTRE`).
- `templates/core/janela_list.html`: botão **"Virar semestre"** (só DESUP), exibido quando existe
  janela com `semestre` ≠ `semestre_atual()`; preenche `novo_semestre` a partir dessa janela
  (liga a virada à janela de entrega, como pedido). Novos templates:
  `templates/core/virar_semestre_confirm.html`.

### 4.5. Histórico navegável por semestre
- `apps/courses/views.py` `CurriculumMatrixListView`: sem filtro de status → **default para
  `vigente`+`rascunho`** (trabalho atual limpo); `historico` como visão separada.
- `templates/courses/matrix_list.html`: no modo Histórico, agrupar/rotular por `periodo_letivo`
  (semestre carimbado na virada) — "Matrizes 2026.1" etc. Continua read-only. Sem novas permissões.

### 4.6. Testes
- `apps/core/tests.py`: `ConfiguracaoSistema.get_solo()` singleton; `semestre_atual()` lê o valor
  persistido e cai no relógio quando vazio; `virar_semestre()` arquiva matrizes
  (`is_vigente→False` + `periodo_letivo` carimbado), rola o semestre, cria `AuditoriaGlobal`,
  gera+salva PDF (usar `FileSystemStorage` temp/override no teste); guard rejeita semestre igual/
  anterior; permissão DESUP-only.
- Integração `professors`: após `virar_semestre`, professor cuja única matriz foi arquivada lê
  `ch_alocada == 0`; justificativa de semestre anterior não conta (já coberto — reforçar).
- **PDF smoke test:** `gerar_pdf_snapshot_semestre` retorna bytes não-vazios com header `%PDF`.

## 5. Arquivos tocados

**Novos:** `apps/core/services_semestre.py`, `apps/core/services_pdf.py`,
`templates/core/pdf/snapshot_semestre.html`, `templates/core/virar_semestre_confirm.html`,
migration de `ConfiguracaoSistema`.

**Editados:** `apps/core/models.py`, `apps/core/views.py`, `apps/core/urls.py`,
`apps/extra_curricular/utils.py`, `apps/allocations/views.py`, `apps/courses/views.py`,
`templates/core/janela_list.html`, `templates/courses/matrix_list.html`,
`config/settings/base.py`, `project_root/requirements.txt`, `apps/core/tests.py`.

## 6. Verificação
- `../.venv/Scripts/python.exe -m pip install xhtml2pdf`; `manage.py makemigrations core` + `migrate`.
- `manage.py check` sem problemas.
- `manage.py test apps.core apps.courses apps.professors apps.extra_curricular`.
- **Manual (server dev, `.venv`):** criar janela do próximo semestre → "Virar semestre" →
  confirmar → conferir: (a) toast + link do PDF; (b) PDF com as 4 seções; (c) matrizes do semestre
  anterior em **Histórico** (read-only, rotuladas por semestre) e fora das Vigentes; (d) professor
  antes alocado agora **0% alocado**; (e) dashboard no novo semestre; (f) `AuditoriaGlobal` com
  `VIRADA_SEMESTRE`.

## 7. Fora de escopo / notas
- **Commits** — feitos só pelo usuário.
- **PDF síncrono** na v1 (escala pequena). Se pesar, mover para Celery (`redis`/`celery` já
  disponíveis) é follow-up simples — o serviço já fica pronto para virar `@shared_task`.
- Não altera a semântica de horas de `ch_justificada` (solicitadas vs aprovadas) — inconsistência
  pré-existente, fora deste pedido.
- Reverter/desarquivar uma virada não faz parte deste pedido; o histórico fica preservado e o PDF
  é a cópia portável.

## 8. Pré-requisito já entregue (base desta feature)
A regra "justificativa não conta em semestre seguinte" **já foi implementada** nesta sessão
(`Professor.ch_justificada` filtra `semestre_atual()`; helper `apps/extra_curricular/utils.py`).
A virada de semestre se apoia nisso: ao rolar `semestre_vigente`, as justificativas do semestre
anterior deixam de contar automaticamente. Ver `docs/relatorios/relatorio_dia_2026-07-14.md`.
