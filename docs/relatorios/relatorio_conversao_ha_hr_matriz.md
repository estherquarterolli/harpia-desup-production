# Relatório — Conversão Hora-Aula → Hora-Relógio e inconsistências de rótulo na Matriz Curricular

> **Escopo:** app `courses` (Matriz Curricular) e telas de Alocação.
> **Data:** 2026-07-09
> **Origem:** verificação solicitada — "os campos Hora-Aula e Hora-Relógio funcionam como
> esperado? A DESUP insere horas-aula (80, 48, 40) e converte para horas-relógio (66,67 / 40 /
> 33,33)?"
> **Conclusão rápida:** a **fórmula está correta** (`HR = HA × 50/60`), mas a exibição
> **arredonda para inteiro** (67, 40, 33) em vez de 2 casas; e há **rótulos inconsistentes**
> para o mesmo dado entre as telas. Este relatório documenta o diagnóstico e a correção
> enviada ao agente CODER.

---

## 1. Como a conversão funciona hoje

A tela de **detalhe da matriz** (`templates/courses/matrix/detail.html:100`) converte a carga
horária de hora-aula para hora-relógio assim:

```django
<td>{{ comp.carga_horaria }}h</td>                    {# coluna "HA" — total, ex.: 80 #}
<td>{% widthratio comp.carga_horaria 6 5 %}h</td>     {# coluna "HR" — total convertido #}
```

`{% widthratio X 6 5 %}` calcula `X ÷ 6 × 5 = X × 5/6 = X × 50/60`. **A fórmula é exatamente a
conversão hora-aula → hora-relógio** (1 hora-aula = 50 min; 1 hora-relógio = 60 min).

### O problema: `widthratio` arredonda para o inteiro mais próximo

Verificado rodando o próprio Django:

| HA (carga_horaria) | HR exato (× 50/60) | HR **exibido hoje** (`widthratio`) | Esperado (2 casas) |
|---:|---:|---:|---:|
| 80  | 66,6667  | **67**  | 66,67  |
| 48  | 40,0000  | **40**  | 40,00  |
| 40  | 33,3333  | **33**  | 33,33  |
| 100 | 83,3333  | **83**  | 83,33  |
| 20  | 16,6667  | **17**  | 16,67  |
| 50  | 41,6667  | **42**  | 41,67  |

Ou seja: a matemática está certa, mas o resultado perde as casas decimais e chega a arredondar
`66,67 → 67` (para cima) e `33,33 → 33` (para baixo). O esperado é **66,67 / 40,00 / 33,33**.

**Correção:** substituir `widthratio` por uma property no modelo + `floatformat:2`, que arredonda
half-up (verificado: `66,6667 → 66,67`, `41,6667 → 41,67`, `33,3333 → 33,33`).

---

## 2. Inconsistências de rótulo encontradas (o mesmo dado com nomes diferentes)

Durante a verificação, encontrei que "HA" e "HR" significam **coisas diferentes em telas
diferentes**. Existem **dois pares HA/HR** no sistema:

### (a) TOTAL por componente — Matriz (detalhe)
`templates/courses/matrix/detail.html` mostra o **total do componente** no semestre:
- "HA" = `carga_horaria` (80) — hora-aula total
- "HR" = `carga_horaria × 50/60` (66,67) — hora-relógio total

### (b) SEMANAL (carga de trabalho) — Alocações
`templates/allocations/alloc_curricular.html:89-90,152-153` mostra a carga **semanal**:
- "HA" = `ha_semanal` = `carga_horaria / 20` (ex.: 4) — hora-aula **semanal**
- "HR" = `hr_semanal` = `ha_semanal × 50/60` (ex.: 3,3) — hora-relógio **semanal**

### (c) Formulário da matriz — mistura os dois nomes
`templates/courses/matrix/form.html:179-180`:
- "CH" = `carga_horaria` (80) — o **total** (mesmo dado que o detalhe chama de "HA")
- "HA" = `carga_horaria_semanal` (semanal) — o **semanal** (mesmo dado que Alocações chama de "HA")

**Resumo do conflito:**

| Dado | Matriz (detalhe) | Matriz (form) | Alocações |
|---|---|---|---|
| Total (80) | **HA** | **CH** | — |
| Semanal (4) | — | **HA** | **HA** |

O total (80) é "HA" numa tela e "CH" noutra; e "HA" significa *total* no detalhe mas *semanal*
no form e nas alocações. É a fonte de confusão.

> **Correção — convenção adotada** (alinhada com a sua descrição de que 80 = "hora-aula"):
> **"HA"/"HR" sem qualificador = TOTAL** do componente; os valores **semanais** recebem o
> sufixo **"/sem"**. Assim:
> - Detalhe da matriz: `HA` (80) / `HR` (66,67) — **já batem**, só corrige o arredondamento.
> - Form da matriz: `CH` → **`HA`** (total); coluna semanal `HA` → **`HA/sem`**.
> - Alocações: `HA` → **`HA/sem`**, `HR` → **`HR/sem`** (deixa explícito que é semanal).

---

## 3. Correção de diagnóstico anterior (transparência)

Numa análise inicial eu havia dito que as properties `ha_semanal`/`hr_semanal` seriam "código
paralelo não usado". **Isso estava incorreto** e foi verificado:

- `ha_semanal`/`hr_semanal` **são usadas** na tela de Alocações
  (`allocations/alloc_curricular.html:152-153`).
- `ha_semanal` **também** é usada no cálculo de carga do professor
  (`apps/professors/views.py:112` e `apps/professors/models.py:198`).

Portanto **essas properties NÃO serão alteradas** — mexer nelas afetaria a matemática de
alocação e as regras de 20h/40h. A correção foi desenhada para **não tocar** nesse cálculo.

---

## 4. Inconsistência adicional: `carga_horaria_semanal` (campo) ≠ `ha_semanal` (property)

No `save()` de `MatrixComponent` (`apps/courses/models.py:266`):

```python
self.carga_horaria_semanal = self.creditos   # créditos = carga_horaria // 20 (divisão inteira)
```

Mas a property `ha_semanal` usa `carga_horaria / 20.0` (divisão real). Para cargas que **não**
são múltiplas de 20, os dois divergem:

| carga_horaria | `creditos` (//20) → campo salvo | `ha_semanal` (/20.0) → usado nas alocações |
|---:|---:|---:|
| 80 | 4 | 4,0 |
| 48 | **2** | **2,4** |
| 40 | 2 | 2,0 |
| 50 | **2** | **2,5** |

O **form da matriz exibe o campo** (`carga_horaria_semanal` = 2 para 48h) enquanto **as
alocações exibem a property** (`ha_semanal` = 2,4). Os próprios seeds já gravam
`round(ch/20, 2)` (2,4), mas o `save()` sobrescreve com `creditos` (2).

> **Correção:** no `save()`, calcular `carga_horaria_semanal = round(carga_horaria / 20, 2)`
> (hora-aula semanal real, batendo com `ha_semanal` e com os seeds). `creditos` continua
> `carga_horaria // 20`. **Não afeta** a matemática de alocação (que usa a property). Linhas
> existentes se atualizam ao serem re-salvas (backfill opcional).

---

## 5. Resumo das correções enviadas ao CODER

| # | Correção | Arquivo(s) | Risco |
|---|---|---|---|
| 1 | **HR total com 2 casas, arredondado** (property `hr_total` + `floatformat:2`, no lugar de `widthratio`) | `apps/courses/models.py`, `templates/courses/matrix/detail.html` | Baixo (só exibição) |
| 2 | **Rótulos consistentes** (HA/HR = total; semanais com `/sem`) | `matrix/form.html`, `allocations/alloc_curricular.html` | Nenhum (só texto) |
| 3 | **`carga_horaria_semanal` = hora-aula semanal real** (não créditos) | `apps/courses/models.py` (`save()`) | Baixo (não toca cálculo de alocação) |

**Fora de escopo (não alterar):** properties `ha_semanal`/`hr_semanal` e qualquer cálculo de
carga do professor / regras 20h–40h. Sem alteração de schema → **nenhuma migração nova**.

**Spec detalhado para o coder:** `ia_workflow/checklist/tarefas-coder-conversao-ha-hr.md`.
