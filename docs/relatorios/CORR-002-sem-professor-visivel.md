# Relatório — CORR-002: "Sem professor" visível na alocação curricular

**Data:** 2026-07-16 · **Commit:** feito pelo usuário (nada commitado).

## 1. O bug
Na tela de alocação (`templates/allocations/alloc_curricular.html`), o widget de seleção de docente
só tinha 3 ramos de render: com docente (verde), `NAO_OFERECIDA` ("Não oferecido") e um `else` que
caía tanto no estado vazio quanto em `SEM_PROFESSOR` — input vazio com placeholder "Escolha uma
opção". No JS, ao clicar "Sem professor", o rótulo era forçado a string vazia
(`opt.dataset.value === 'SEM_PROFESSOR' ? '' : ...`) + reload → voltava ao mesmo estado vazio.
Resultado: escolher "Sem professor" parecia não fazer nada, indistinguível do estado inicial.
(Como `MatrixComponent.status` já tem default `SEM_PROFESSOR`, o "estado vazio" nem existe no banco.)

## 2. O que mudou
Arquivo único: `templates/allocations/alloc_curricular.html`.
- `data-current-nome` (~:105): novo ramo `{% elif comp.status == 'SEM_PROFESSOR' %}Sem professor`.
- Wrapper (~:109): estilo próprio `border-slate-300 bg-slate-50` para `SEM_PROFESSOR` + ícone
  `ph-user-minus`, distinto do vazio e do `bg-slate-100` de "Não oferecido".
- Input (~:113-115): ramo `text-slate-500 font-semibold` com `value="Sem professor"`.
- JS `_bindEvents` (~:261): removido o caso que zerava o rótulo → `label = opt.textContent.trim()`.
- JS `.ac-clear` (~:274): `_selectValue('SEM_PROFESSOR', 'Sem professor')`.
- Sem mudança de regra de negócio (`AlocarDocenteComponenteView` já persistia `SEM_PROFESSOR`).

## 3. Verificação
- `manage.py check` — sem problemas.
- `manage.py test apps.allocations` — 5/5 OK (testes de model/SEI; não exercitam o front, mas passam).

## 4. Rollback
```bash
git checkout -- project_root/templates/allocations/alloc_curricular.html
```
(único arquivo de código tocado). Opcional: reverter a seção CORR-002 no `docs/checklist_correcao.md`.

## 5. Checklist
CORR-002 marcado 🟢 Corrigido (índice + seção + Resolução) em `docs/checklist_correcao.md`.
