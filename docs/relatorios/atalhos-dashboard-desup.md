# Relatório — Atalhos configuráveis no dashboard DESUP

**Data:** 2026-07-16 · **Branch de trabalho:** fix/CORR-008 · **Commit:** feito pelo usuário (nada commitado).

## 1. O que foi feito
Seção de atalhos no dashboard do Coord. DESUP: o usuário monta os próprios atalhos (por usuário),
que persistem. Primeiro acesso mostra só **"Adicionar atalho"**. Todos os atalhos na cor
institucional **azul `#025c9f`**. Adição via **pop-up multi-seleção** (checkboxes); remoção via
**pop-up de confirmação** (sem `alert()`). Feedbacks "Atalho(s) salvo(s)." / "Atalho(s)
removido(s).". Atalhos excedentes quebram para a linha de baixo (`flex-wrap`). Whitelist de
destinos; DESUP-only.

> Histórico: a 1ª versão tinha 2 atalhos fixos amarelos + painel inline. Após teste do usuário,
> ajustado para: sem fixos, tudo azul, pop-ups (add multi + remover), feedbacks pluralizados.

## 2. Arquivos alterados

**Novos:**
- `apps/core/atalhos.py` — catálogo `ATALHOS_CATALOGO` (whitelist, names sem kwargs, inclui
  `adicionar_curso` → `core:unidade_list`) + `resolver_atalho()`.
- `apps/core/migrations/0002_atalhodashboard.py` — cria a tabela.

**Editados:**
- `apps/core/models.py` — model `AtalhoDashboard(user FK, chave, ordem, criado_em)`,
  `unique_together(user, chave)`.
- `apps/core/views.py` — contexto de atalhos em `DashboardDesupView`; `AtalhoAddView`
  (multi: `getlist('chave')`, valida whitelist, bulk `get_or_create`) e `AtalhoRemoveView`
  (`get_object_or_404(pk, user=request.user)` → isolamento por usuário); mensagens de feedback.
- `apps/core/urls.py` — `core:atalho_add`, `core:atalho_remove`.
- `templates/dashboard/desup.html` — seção de atalhos (chips azuis + botão cinza) + 2 modais
  (add multi-checkbox, remover) + JS de abrir/fechar.
- `apps/core/tests.py` — classe `AtalhoDashboardTests` (8 testes).

## 3. Funcionamento
- Dashboard DESUP: chips azuis dos atalhos (com "×") + botão cinza "Adicionar atalho".
- "Adicionar atalho" → modal com checkboxes das páginas ainda não adicionadas → **Salvar** (POST
  múltiplo) → toast "Atalho(s) salvo(s).".
- "×" no chip → modal "Remover atalho" → **Remover** (POST) → toast "Atalho(s) removido(s).".
- Guarda só a **chave** (whitelist); href resolvido por `reverse()` com try/except (pula quebrados).
- Escopo por usuário: um DESUP não vê atalhos de outro.
- **Testes:** `apps.core` 8/8 (classe) e 48/48 (app) verdes; `manage.py check` limpo.

## 4. Rollback
Feature ainda não commitada → voltar ao estado pré-feature:
```bash
git restore project_root/apps/core/models.py project_root/apps/core/views.py \
  project_root/apps/core/urls.py project_root/apps/core/tests.py \
  project_root/templates/dashboard/desup.html
rm project_root/apps/core/atalhos.py project_root/apps/core/migrations/0002_atalhodashboard.py
```
Banco (se aplicou o migrate):
```bash
python manage.py migrate core 0001
```
Ou, com a porta do Postgres bloqueada (Supabase, via SQL Editor):
```sql
DROP TABLE IF EXISTS core_atalhodashboard;
DELETE FROM django_migrations WHERE app='core' AND name='0002_atalhodashboard';
```

## 5. Pendências para o usuário
- **Aplicar a migration `0002`** no banco (não rodado contra o Supabase — porta bloqueada na rede).
- Testar → criar branch → commitar (commits são do usuário).
