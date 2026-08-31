# Relatório — Bloqueio de Justificativas Extracurriculares + Seeds Completas

**Papel:** Agente CORRECTOR/CODER (Regra de Negócio + Dados de Base)
**Data:** 2026-07-07
**Escopo:** (1) Trava de edição/exclusão de justificativas extracurriculares enviadas em definitivo; (2) Seed completa da estrutura curricular de todas as unidades; (3) Limpeza de dados parciais de Paracambi; (4) Seed completa de professores.

---

## 1. 🔒 Bloqueio de justificativas enviadas em definitivo

### Requisito
Após o envio definitivo de uma justificativa extracurricular (botão vermelho → DESUP), a **unidade não pode mais editar nem excluir** o que foi enviado. Novas justificativas (TCC, extensão, redução) ainda podem ser **adicionadas à parte**, enquanto a janela de entrega estiver aberta. Bloqueio **por item**, não pela pendência inteira.

### Implementação
- **Modelo** (`apps/extra_curricular/models.py`): campo `bloqueado` (BooleanField, default False) em `OrientacaoTCC`, `AtividadeExtensionista` e `ReducaoCargaHoraria` + método `PendenciaExtra.bloquear_itens_enviados()`.
- **Migração**: `extra_curricular/migrations/0002_...` (aplicada).
- **Views** (`apps/extra_curricular/views.py`):
  - `EnviarParaDesupView` e `EnviarParaDesupLoteView` → marcam `bloqueado=True` nos itens no envio.
  - `DeletarItemView` e `DeletarItemLoteView` → recusam excluir item bloqueado (mensagem + redirect).
  - `_BaseItemSaveView` e `PendenciaDetailView` → formset de edição filtrado por `bloqueado=False` (itens travados não entram no formulário editável).
- **Templates**: nos 6 acordeões (TCC/Extensão/Redução, individual + lote), o botão de excluir vira um **cadeado 🔒** para itens bloqueados.

### Comportamento resultante
| Item | Editar | Excluir | Adicionar novo |
|---|---|---|---|
| Já enviado (bloqueado) | ❌ | ❌ | — |
| Novo (após envio, janela aberta) | ✅ | ✅ | ✅ |

### Validação (professor Adilson Ricardo da Silva)
- Envio definitivo → item `bloqueado=True` ✅
- Excluir item enviado → recusado, item permanece ✅
- Editar item enviado → item fora do formset editável ✅
- Adicionar nova justificativa após envio → permitida, começa desbloqueada ✅
- Excluir a nova (ainda não enviada) → permitida ✅
- `manage.py check` limpo; 2 testes do app passam.

---

## 2. 🗂️ Seed completa da estrutura curricular (todas as unidades)

Portados os dados do dump `seeds/sql/seed_supabase.sql` (gerado dos PPCs, mas incompatível com o schema atual pós multi-unidade) para uma seed **Python compatível**, via ORM.

- **Arquivo**: `seeds/seed_matrizes_completo.py` — parseia o SQL e carrega no schema novo:
  - `courses_course` (por unidade) → `Course` **global deduplicado** + `CourseUnit(curso, unidade)`.
  - `courses_curriculummatrix.curso_id` → `CurriculumMatrix.curso` (Course global) + `matriz.unidades.add(unidade)` (M2M nova).
  - Componentes e vínculos matriz-componente mapeados por ID antigo.
  - Idempotente (get_or_create por chaves naturais).

- **Resultado**: **13 unidades, 8 cursos, 385 componentes curriculares, 14 matrizes, 586 vínculos** — cobrindo ADS, Gestão Ambiental, Sistemas para Internet, Gestão Portuária, Processos Gerenciais, TIC, Logística e Licenciatura em Pedagogia (6 unidades).

---

## 3. 🧹 Limpeza de dados parciais de Paracambi

A `seed_paracambi` executada anteriormente havia deixado matrizes parciais/duplicadas. Removidas em transação:
- `Matriz ADS 2026` (5 componentes — obsoleta) e `Matriz TGA 2026` (37 componentes).
- Curso duplicado **TGA** "Tecnologia em Gestão Ambiental" + seu `CourseUnit`.
- **8 componentes órfãos** (grafias divergentes, ex.: `Química geral` vs a oficial `Química Geral`).

**Estado final de Paracambi**: ADS `MC-AEDDS-2026.1` (36 comps) + Gestão Ambiental `MC-GA-2026.1` (37 comps). Sem duplicatas. Confirmado que 0 componentes do catálogo do SQL foram removidos por engano.

---

## 4. 👥 Seed completa de professores (todas as unidades)

- **Arquivo**: `seeds/seed_professores_completo.py` — porta os **191 professores** e **4 tipos de contrato** do SQL. Reaproveita o parser da seed de matrizes.
- **Não-duplicante**: usa `update_or_create_professor` casando por `id_funcional`/matrícula e, como fallback, por **nome dentro da unidade** — assim os professores de Paracambi já existentes são **reconciliados** (recebem id_funcional/matrícula/contrato reais) em vez de duplicados.
- **Resultado**: **170 criados + 21 reconciliados** (191 processados). 4 tipos de contrato.
- **Limpeza dos "N/A"**: os 6 professores remanescentes do seed antigo de Paracambi (Elizangela Simões, Henrique de Medeiros, Paulo Calixto, Rubens Saviano, Selma Gomes, Silvestre de Mello de Souza) — que não constam no dump SQL e só tinham `id_funcional`/matrícula fictícios (`IDF-N-A_*`) — foram **removidos**. Nenhum era docente em matriz (FK PROTECT); cada um tinha 1 pendência extracurricular de teste, removida em cascata.
- **Total final no banco**: **190 professores**, 0 remanescentes "N/A".

---

## 5. Arquivos alterados/criados

| Arquivo | Tipo |
|---|---|
| `apps/extra_curricular/models.py` | alterado (campo `bloqueado` + método) |
| `apps/extra_curricular/migrations/0002_...` | novo (migração) |
| `apps/extra_curricular/views.py` | alterado (trava no envio, recusa edição/exclusão, filtro do formset) |
| `templates/extra_curricular/partials/_accordion_{tcc,extensao,reducao}{,_lote}.html` | alterados (6 partials, cadeado) |
| `seeds/seed_matrizes_completo.py` | novo (seed estrutura curricular) |
| `seeds/seed_professores_completo.py` | novo (seed professores) |

> Todas as mudanças estão no working tree e no banco local. Sem commit (fica a cargo do desenvolvedor).

---

## 6. Como reproduzir os dados de base (banco limpo)

```bash
python manage.py migrate
python seeds/seed_matrizes_completo.py       # unidades, cursos, componentes, matrizes
python seeds/seed_professores_completo.py     # tipos de contrato + professores
```
