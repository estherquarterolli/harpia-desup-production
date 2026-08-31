# Relatório — CORR-012: ação manual de arquivar/reativar matriz

**Data:** 2026-07-16 · **Commit:** feito pelo usuário (nada commitado).

## 1. O que era
Não existia ação para arquivar/desativar uma matriz manualmente, nem para reativar uma arquivada.
Com o fim do auto-arquivamento (CORR-011), passou a ser necessário um controle manual de
Vigente ↔ Histórico.

## 2. O que mudou

**`apps/courses/views.py`** — DESUP-only, POST:
- Base `_MatrixDesupActionView` (perfil DESUP/superuser → senão redirect + msg).
- `ArquivarMatrizView` (`is_vigente=False`; guarda contra rascunho e contra já-arquivada).
- `ReativarMatrizView` (`is_vigente=True`; **não** toca nas demais do curso — coerente CORR-011).
- Ambas registram em `AuditoriaGlobal` (`MATRIZ_ARQUIVADA` / `MATRIZ_REATIVADA`) via
  `registrar_auditoria` (`apps/accounts/views.py`).

**`apps/courses/urls.py`** — `matrices/<pk>/arquivar/` (`matrix_archive`),
`matrices/<pk>/reativar/` (`matrix_reactivate`).

**Templates** — `templates/courses/matrix_list.html` e `matrix/partials/_table_body.html`:
botões **Arquivar** (vigente) / **Reativar** (histórico) com `confirm()`, só para `is_desup`;
rascunho mantém "Editar Rascunho"; demais perfis veem "Bloqueado".

**`apps/courses/tests.py`** — `MatrixArquivarReativarTests` (5 testes).

## 3. Funcionamento / verificação
- DESUP arquiva vigente → vai para Histórico (read-only, cadeado existente) + auditoria.
- DESUP reativa histórico → volta a Vigente + auditoria, sem arquivar as demais.
- Rascunho não arquiva; unidade/coord recebe redirect (bloqueado).
- **Testes:** `apps.courses` 18/18 verdes; `manage.py check` limpo.

## 4. Rollback
```bash
git checkout -- project_root/apps/courses/views.py project_root/apps/courses/urls.py \
  project_root/apps/courses/tests.py project_root/templates/courses/matrix_list.html \
  project_root/templates/courses/matrix/partials/_table_body.html
```
Sem migration. Nada commitado.
