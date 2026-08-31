# Tarefas CODER — Conversão HA→HR (2 casas) e consistência de rótulos na Matriz

> **App alvo:** `courses` (Matriz Curricular) + telas de Alocação.
> **Contrato do agente:** seguir `docs/ia/coder.md` (reproduzir antes de corrigir, testes
> negativos, escopo disciplinado, formato de entrega em 7 partes).
> **Contexto/diagnóstico completo:** `docs/relatorios/relatorio_conversao_ha_hr_matriz.md`.
> **Regra de ouro:** NÃO alterar `ha_semanal`/`hr_semanal` nem qualquer cálculo de carga do
> professor / regras 20h–40h. Sem alteração de schema (nenhuma migração nova esperada).

---

## Contexto verificado (não reinvestigar do zero)

- `MatrixComponent` (`apps/courses/models.py`): `carga_horaria` (PositiveIntegerField, o total
  que a DESUP digita: 80, 48, 40). Properties existentes: `ha_semanal = carga_horaria/20.0`,
  `hr_semanal = ha_semanal × 50/60` — **USADAS** em `allocations/alloc_curricular.html:152-153`,
  `professors/views.py:112` e `professors/models.py:198`. **NÃO MEXER.**
- Topo de `apps/courses/models.py` importa apenas `from django.db import models` — **falta**
  `from decimal import Decimal` (adicionar).
- Detalhe da matriz (`templates/courses/matrix/detail.html:88-100`) converte HR com
  `{% widthratio comp.carga_horaria 6 5 %}` → arredonda para inteiro (66,67 vira 67). Bug.
- `save()` de `MatrixComponent` (linha ~256-267) faz `self.carga_horaria_semanal = self.creditos`
  (divisão inteira), divergindo de `ha_semanal` (divisão real) para não-múltiplos de 20.

---

## Tarefa 1 — HR total com 2 casas decimais, arredondado (PRINCIPAL)

**1a. `apps/courses/models.py`** — adicionar import e uma property em `MatrixComponent`:

```python
from decimal import Decimal   # no topo do arquivo, junto aos imports
```

```python
    @property
    def hr_total(self):
        """Hora-Relógio total do componente: carga horária (hora-aula) × 50/60."""
        return (self.carga_horaria or 0) * Decimal("50") / Decimal("60")
```

Colocar `hr_total` junto das properties `ha_semanal`/`hr_semanal` já existentes (não removê-las).

**1b. `templates/courses/matrix/detail.html:100`** — trocar:

```django
<td class="px-4 py-3">{% widthratio comp.carga_horaria 6 5 %}h</td>
```
por:
```django
<td class="px-4 py-3">{{ comp.hr_total|floatformat:2 }}h</td>
```

`floatformat:2` arredonda half-up (verificado: 80→66,67; 48→40,00; 40→33,33; 50→41,67).

**Aceite 1:** no detalhe da matriz, componentes de 80/48/40h exibem HR = **66,67 / 40,00 /
33,33** (com 2 casas), e não mais 67/40/33.

---

## Tarefa 2 — Consistência de rótulos (HA/HR = TOTAL; semanal = "/sem")

Convenção: **"HA"/"HR" sem sufixo = total do componente**; valores **semanais** levam **"/sem"**.

**2a. `templates/courses/matrix/detail.html:88-89`** — cabeçalhos já são "HA"/"HR" (total).
**Manter** (agora coerentes com a convenção). Nada a mudar aqui além da Tarefa 1.

**2b. `templates/courses/matrix/form.html:179-180`** — hoje:
```django
<th class="px-4 py-3">CH</th>   {# carga_horaria (total) #}
<th class="px-4 py-3">HA</th>   {# carga_horaria_semanal (semanal) #}
```
trocar para:
```django
<th class="px-4 py-3">HA</th>       {# total — igual ao detalhe #}
<th class="px-4 py-3">HA/sem</th>   {# semanal #}
```
(Só o texto dos `<th>`. Não mexer nas células/inputs do `_formset_row.html`.)

**2c. `templates/allocations/alloc_curricular.html:89-90`** — hoje "HA"/"HR" (são **semanais**):
```django
<th ...>HA</th>
<th ...>HR</th>
```
trocar para:
```django
<th ...>HA/sem</th>
<th ...>HR/sem</th>
```
(Só o texto dos `<th>`. Não mexer nas células `ha_semanal`/`hr_semanal`.)

**Aceite 2:** o total (80) aparece como "HA" tanto no form quanto no detalhe; toda coluna
semanal (form e alocações) mostra o sufixo "/sem".

---

## Tarefa 3 — `carga_horaria_semanal` = hora-aula semanal real (não créditos)

> ⚠️ **SUPERADA pela ENTREGA 2 (ver seção no fim deste doc).** A decisão do cliente mudou:
> `carga_horaria_semanal` (e `creditos`) passam a ser **digitados pela DESUP e respeitados**,
> não recalculados no `save()`. O `save()` só preenche esses campos quando vierem **em branco**.
> Implementar conforme a ENTREGA 2, não como abaixo.

**3a. `apps/courses/models.py`**, no `save()` de `MatrixComponent` (linha ~266), trocar:
```python
        if self.carga_horaria is not None:
            self.creditos = self.carga_horaria // 20
            self.carga_horaria_semanal = self.creditos
```
por:
```python
        if self.carga_horaria is not None:
            self.creditos = self.carga_horaria // 20
            self.carga_horaria_semanal = round(self.carga_horaria / 20, 2)
```

`creditos` continua `// 20`. `carga_horaria_semanal` passa a bater com `ha_semanal` e com os
seeds (`round(ch/20, 2)`). **Não altera** `ha_semanal`/`hr_semanal` nem o cálculo de alocação.

**Aceite 3:** salvar um componente com `carga_horaria=48` → `carga_horaria_semanal == 2.4` e
`creditos == 2`. Para `carga_horaria=80` → `carga_horaria_semanal == 4.0`.

> Observação (não implementar agora, só registrar no relatório de entrega): o input
> `carga_horaria_semanal` no form é editável mas sempre sobrescrito pelo `save()` — é campo
> derivado. Fica como observação; não é escopo desta entrega.

---

## Tarefa 4 — Testes (em `apps/courses/tests.py`)

Seguir o estilo de `CurriculumMatrixComponentTests` (usa `Unidade`, `Course`, `CourseUnit`,
`CurricularComponent`, `CurriculumMatrix`, `MatrixComponent`). Adicionar uma classe nova, ex.
`HoraAulaHoraRelogioTests`, com:

1. `test_hr_total_dois_decimais`: criar `MatrixComponent` com `carga_horaria` 80/48/40 e conferir
   `render` de `floatformat:2` (ou comparar `hr_total` quantizado) → "66.67", "40.00", "33.33".
2. `test_carga_horaria_semanal_bate_com_ha_semanal`: componente com `carga_horaria=48` após
   `save()` → `carga_horaria_semanal == Decimal("2.4")` (ou `2.4`), `creditos == 2`; e
   `carga_horaria=80` → `carga_horaria_semanal == 4.0`.
3. (opcional) render do `detail.html` de um componente de 80h e assert que aparece `66,67` /
   `66.67` (não `67`).

---

## Verificação final (o coder DEVE rodar e colar a saída)

```bash
cd project_root
../.venv/Scripts/python.exe manage.py makemigrations --check --dry-run   # esperado: No changes detected
../.venv/Scripts/python.exe manage.py test apps.courses --noinput
../.venv/Scripts/python.exe manage.py check
```

- `makemigrations --check` **deve** dizer "No changes detected" (nenhuma mudança de schema).
- Testes de `apps.courses` verdes (incluindo os novos).
- `check` sem issues.

## Fora de escopo (NÃO tocar)
- `ha_semanal`, `hr_semanal` (properties) e qualquer cálculo de carga do professor / 20h–40h.
- Inputs/células do `_formset_row.html` (só os `<th>` de cabeçalho mudam). **[atualizado na ENTREGA 2 — agora o `_formset_row.html` MUDA]**
- Schema / migrações (não deve haver nenhuma nova).

---
---

# ENTREGA 2 — DESUP digita Crédito/HA/HA-sem; HR calcula sozinho (read-only) no form

> **Status:** a ENTREGA 1 já está aplicada e verde. Esta ENTREGA 2 é a próxima e **supersede
> a Tarefa 3** da Entrega 1.
> **Decisão do cliente:** no **formulário** da matriz, a DESUP **digita** `Crédito`, `HA`
> (carga_horaria) e `HA/sem` (carga_horaria_semanal) — todos **respeitados**, editáveis. Só o
> **HR** (nova coluna) calcula automaticamente (`HA × 50/60`), **read-only, não é input**.
> "Nenhum campo sobrescreve o que a DESUP digitou; HR é a única coluna calculada."

## T2.1 — `apps/courses/forms.py` (classe `MatrixComponentForm`)

Objetivo: parar de sobrescrever `creditos`/`carga_horaria_semanal` e torná-los editáveis.

1. **Widgets** (Meta.widgets): remover `'readonly': 'readonly'` de **`creditos`** e de
   **`carga_horaria_semanal`** (mantendo `class`, `min`, `step`). Eles viram inputs editáveis.
2. **Método `clean()`** (hoje sobrescreve `cleaned_data['creditos']` e
   `cleaned_data['carga_horaria_semanal']` = `ch // 20`): **remover essas duas atribuições**
   (pode remover o método inteiro, já que ele só fazia isso). A DESUP passa a mandar os valores.
3. **Método `save()` custom** (hoje faz `instance.creditos = ch // 20` e
   `instance.carga_horaria_semanal = instance.creditos`): **remover o método `save()` inteiro**
   — deixar o `ModelForm.save()` padrão. Respeita o input.
4. **`__init__`**: adicionar `self.fields['carga_horaria_semanal'].required = False`
   (`creditos.required = False` já existe). Assim, em branco não dá erro de validação.

## T2.2 — `apps/courses/models.py` (`MatrixComponent.save()`)

Trocar o bloco atual (que SEMPRE recalcula) por um que **só preenche quando vier em branco**
(respeita valores digitados, inclusive `0` explícito; evita erro de not-null quando em branco):

```python
    def save(self, *args, **kwargs):
        if not self.codigo:
            cc = self.componente_curricular
            self.codigo = cc.codigo or ''
        if self.carga_horaria is None:
            self.carga_horaria = self.componente_curricular.carga_horaria_padrao
        # Só preenche os calculados quando NÃO informados (respeita o que a DESUP digitou).
        if self.carga_horaria is not None:
            if self.creditos is None:
                self.creditos = self.carga_horaria // 20
            if self.carga_horaria_semanal is None:
                self.carga_horaria_semanal = round(self.carga_horaria / 20, 2)
        super().save(*args, **kwargs)
```

- **Não** alterar a property `hr_total` (criada na Entrega 1) nem `ha_semanal`/`hr_semanal`.

## T2.3 — `templates/courses/matrix/form.html` (cabeçalho da tabela)

Após o `<th ...>HA/sem</th>` (o segundo, criado na Entrega 1, ~linha 180), adicionar:
```django
              <th class="px-4 py-3">HR</th>
```
Fica: `Período | Cód | Disciplina | Crédito | HA | HA/sem | HR | (ações)`.

## T2.4 — `templates/courses/matrix/partials/_formset_row.html` (nova célula HR read-only)

Após a célula de `carga_horaria_semanal` (bloco "HA (CH Semanal)", ~linhas 37-41), **antes** da
célula de Ações, adicionar uma célula **somente-leitura** (NÃO é input):
```django
  {# HR (hora-relógio total) — AUTO, read-only, NÃO é input. Recalcula via JS ao digitar HA. #}
  <td class="p-2 align-top w-28">
    <span class="js-hr-total inline-block px-2 py-1 font-semibold text-slate-600">{% if form_row.instance.pk %}{{ form_row.instance.hr_total|floatformat:2 }}{% else %}0.00{% endif %}</span>
  </td>
```
As células de `creditos` e `carga_horaria_semanal` **não mudam no HTML** — ao remover o
`readonly` do widget (T2.1) elas já ficam editáveis.

## T2.5 — JS de cálculo do HR ao vivo (`templates/courses/matrix/form.html`, bloco `<script>`)

Adicionar (dentro do `{% block extra_js %}`, junto às outras funções) um listener **delegado**
(cobre linhas adicionadas via HTMX automaticamente). HR = `HA × 50/60`, 2 casas, mesmo formato
do detalhe (ponto decimal, como o `floatformat:2`):
```javascript
  // HR (hora-relógio total) = HA × 50/60 — read-only, recalcula ao digitar a HA (carga_horaria).
  function updateHrTotal(input) {
    const row = input.closest('tr');
    if (!row) return;
    const span = row.querySelector('.js-hr-total');
    if (!span) return;
    const ha = parseFloat(input.value) || 0;
    span.textContent = (ha * 50 / 60).toFixed(2);   // ex.: 80 -> "66.67"
  }
  document.addEventListener('input', function (e) {
    const t = e.target;
    if (t && t.name && t.name.endsWith('-carga_horaria')) {
      updateHrTotal(t);
    }
  });
```

## T2.6 — Testes (`apps/courses/tests.py`)

1. **Manter** `test_hr_total_dois_decimais` (inalterado).
2. **Substituir** `test_carga_horaria_semanal_bate_com_ha_semanal` por
   `test_save_respeita_creditos_e_carga_horaria_semanal_digitados`:
   - criar `MatrixComponent` com `carga_horaria=48, creditos=7, carga_horaria_semanal=Decimal("3.5")`;
   - `refresh_from_db()`; assert `creditos == 7` e `carga_horaria_semanal == Decimal("3.5")`
     (ou seja, **NÃO** sobrescritos por `48//20=2` / `2.4`).
3. **Adicionar** `test_save_preenche_calculados_quando_em_branco`:
   - `comp = MatrixComponent(matriz=..., componente_curricular=..., carga_horaria=48, creditos=None, carga_horaria_semanal=None)`; `comp.save()`; `refresh_from_db()`;
   - assert `creditos == 2` e `carga_horaria_semanal == Decimal("2.4")` (fallback quando em branco).
4. (opcional) teste de form/formset: enviar `creditos`/`carga_horaria_semanal` explícitos e
   confirmar que persistem (respeitados), não recalculados.

> Atenção: os testes existentes `test_matrix_formset_connects_multiple_components_to_one_matrix`
> e `test_matrix_component_uses_component_defaults_when_fields_are_blank` devem **continuar
> verdes** (o primeiro manda `creditos='4'` explícito → respeitado; o segundo deixa em branco →
> fallback). Não alterá-los, apenas garantir que passam.

## Verificação final da Entrega 2 (rodar e colar a saída)
```
cd project_root
../.venv/Scripts/python.exe manage.py makemigrations --check --dry-run   # esperado: No changes detected
../.venv/Scripts/python.exe manage.py test apps.courses --noinput
../.venv/Scripts/python.exe manage.py check
```

## Fora de escopo da Entrega 2 (NÃO tocar)
- `ha_semanal`/`hr_semanal` e cálculo de carga do professor / regras 20h–40h.
- Telas de detalhe (`detail.html`) e de alocações (`alloc_curricular.html`) — já ajustadas na
  Entrega 1; a coluna HR nova é **só no formulário**.
- Schema / migrações — não deve haver nenhuma nova (só widgets, lógica de `save()`, template e JS).
