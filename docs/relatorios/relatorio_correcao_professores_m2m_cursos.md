# Relatório de Correção — Erro 500 em `/professores/` (M2M `Professor.cursos` com schema defasado)

**Papel:** Agente CORRECTOR / QA (Diagnóstico de banco e reparo de schema)
**Data:** 2026-07-07
**Ambiente:** Desenvolvimento local — PostgreSQL `harpia_db @ localhost`
**Rota afetada:** `GET /professores/` (perfil Coordenador de Unidade; afeta todos os perfis)
**Severidade:** Alta (tela inteira de professores inacessível — HTTP 500)

---

## 1. Sintoma Reportado

Ao acessar a tela de professores com o perfil **Coordenador de Unidade**, o servidor
retornava **HTTP 500**:

```
[07/Jul/2026 10:08:49] "GET /professores/ HTTP/1.1" 500 190483
```

Traceback essencial (encadeamento resumido):

```
psycopg2.errors.UndefinedColumn:
  ERRO:  coluna professors_professor_cursos.course_id não existe
LINE 1: ...ors_professor_cursos" ON ("courses_course"."id" = "professor...

django.db.utils.ProgrammingError:
  ERRO:  coluna professors_professor_cursos.course_id não existe

  File ".../apps/professors/views.py", line 66, in get_context_data
    professores_list = list(ctx['professores'])
  ...
  File ".../django/db/models/query.py", line 1369, in _prefetch_related_objects
    prefetch_related_objects(...)
```

O erro era **determinístico**: ocorria em toda requisição a `/professores/`.

---

## 2. Ponto de Falha no Código

A `ProfessorListView` (uma `ListView`) faz `prefetch_related` do M2M `cursos` e depois
**materializa** o queryset no `get_context_data`:

```python
# apps/professors/views.py (get_context_data)
professores_list = list(ctx['professores'])   # ← linha 66: dispara o prefetch de 'cursos'
```

O `list(...)` força a avaliação do `QuerySet`, e o Django executa a query de prefetch da
relação `cursos`. É nessa query que o Postgres reclama da coluna inexistente `course_id`.

O campo no model:

```python
# apps/professors/models.py
cursos = models.ManyToManyField(
    'courses.Course',
    blank=True,
    related_name='professores_cursos',
    verbose_name="Cursos",
)
```

Um `ManyToManyField` sem `through` explícito gera uma **tabela intermediária automática**
(`professors_professor_cursos`) com as colunas `id`, `professor_id` e — por apontar para
`courses.Course` — **`course_id`**.

---

## 3. Diagnóstico (Causa Raiz)

O problema **não é de código** — model e migrações estão corretos. É de **estado físico do
banco**: a tabela intermediária real está desalinhada do que as migrações declaram.

### 3.1 O que o histórico de migrações diz (correto)

- `showmigrations professors courses` → **todas aplicadas** (`[X]`):
  ```
  professors
   [X] 0001_initial
   [X] 0002_professor_email_optional_limite_horas
  courses
   [X] 0001_initial ... 0004_...
  ```
- A migração `professors/0001_initial.py` já declara o alvo **`courses.course`**:
  ```python
  ('cursos', models.ManyToManyField(blank=True, related_name='professores_cursos',
            to='courses.course', verbose_name='Cursos')),
  ```
- `makemigrations --check --dry-run` → **"No changes detected"** (model × migrações em
  sincronia).

### 3.2 O que a tabela física realmente tinha (defasado)

Inspeção do schema real **antes** do reparo:

```
=== colunas de professors_professor_cursos ===
('id', 'bigint')
('professor_id', 'bigint')
('courseunit_id', 'bigint')      ← deveria ser course_id

=== FKs de professors_professor_cursos ===
courseunit_id  →  courses_courseunit(id)   ← deveria apontar para courses_course(id)
professor_id   →  professors_professor(id)

=== linhas na tabela M2M ===  0
courses_course     rows: 2
courses_courseunit rows: 2
```

Ou seja: a coluna física era **`courseunit_id`** com FK para **`courses_courseunit`**, não
`course_id` → `courses_course`.

### 3.3 Conclusão da causa raiz

Este banco local foi **criado a partir de uma versão anterior do código**, em que o M2M
`Professor.cursos` apontava para **`courses.CourseUnit`** (gerando a coluna `courseunit_id`).
Posteriormente, a definição foi alterada para **`courses.Course`** e a migração
`0001_initial` foi **editada no lugar** (in-place), sem:

1. gerar uma nova migração de alteração do M2M; **e**
2. reconstruir/alterar o schema deste banco já existente.

Como o Django controla o estado pela tabela `django_migrations` (que marcava `0001_initial`
como aplicada) e a migração **editada** já casa com o model atual, tanto `showmigrations`
quanto `makemigrations --check` reportam tudo "em ordem" — mascarando a divergência. O
descompasso só aparece **em tempo de execução**, quando a query real bate na coluna que não
existe.

> **Importante:** bancos **novos/limpos** (criados a partir do código atual) nascem
> **corretos** — a migração vigente já cria `course_id`. O defeito é exclusivo de bancos que
> foram materializados **antes** da troca `CourseUnit → Course`. Este banco local era um
> desses.

---

## 4. Correção Aplicada

Como a tabela intermediária estava **vazia (0 linhas)**, não havia dados a preservar/migrar,
tornando o reparo trivial e seguro. O alinhamento foi feito **diretamente no schema físico**
do banco local (não é necessária nova migração — bancos limpos já funcionam), dentro de uma
**transação atômica**:

```sql
BEGIN;

-- 1) remove a FK antiga (courseunit → courses_courseunit)
ALTER TABLE professors_professor_cursos
  DROP CONSTRAINT IF EXISTS professors_professor_courseunit_id_f996437b_fk_courses_c;

-- 2) renomeia a coluna para o nome que o Django/ORM espera
ALTER TABLE professors_professor_cursos
  RENAME COLUMN courseunit_id TO course_id;

-- 3) recria a FK apontando para courses_course
ALTER TABLE professors_professor_cursos
  ADD CONSTRAINT professors_professor_cursos_course_id_fk_courses_course
  FOREIGN KEY (course_id) REFERENCES courses_course(id) DEFERRABLE INITIALLY DEFERRED;

COMMIT;
```

Resultado imediato (colunas após o reparo):

```
colunas agora: ['id', 'professor_id', 'course_id']
```

**Nenhuma alteração de código, model ou migração foi necessária** — o reparo foi apenas de
dados/estrutura no banco local, para colocá-lo em conformidade com o que as migrações já
descrevem.

---

## 5. Validação

| Verificação | Comando | Resultado |
|---|---|---|
| Query que quebrava (prefetch de `cursos`) | `Professor.objects.prefetch_related('cursos')` materializado | **26 professores carregados, sem erro** |
| Model × migrações em sincronia | `manage.py makemigrations --check --dry-run` | **"No changes detected"** |
| Outras colunas `courseunit` órfãs no schema | varredura em `information_schema.columns` | **Nenhuma** (era a única) |

Trecho da validação da ORM:

```
Professores carregados: 26
 - 3  Adilson Ricardo da Silva            | cursos: []
 - 4  Alessandro de Almeida C. Cerqueira  | cursos: []
 - 5  Artur Sergio Lopes                  | cursos: []
 ...
OK: prefetch de cursos funcionou sem erro
```

A tela `/professores/` volta a responder normalmente para o perfil Coordenador de Unidade
(e demais perfis).

---

## 6. Resíduos Cosméticos (conhecidos, sem impacto funcional)

Como o reparo foi um **rename de coluna** (e não um drop/recreate da tabela), alguns objetos
auxiliares **mantiveram o nome antigo** com "courseunit", embora estejam **funcionalmente
corretos** (no PostgreSQL, índices e constraints acompanham a coluna renomeada e passam a
operar sobre `course_id`):

```
constraints:
  professors_professor_cursos_course_id_fk_courses_course              (FK — NOVA, correta)
  professors_professor_professor_id_4ad24c01_fk_professor              (FK professor — ok)
  professors_professor_cur_professor_id_courseunit__6318cef7_uniq      (UNIQUE professor_id+course_id — nome antigo)
  professors_professor_cursos_courseunit_id_not_null                   (NOT NULL sobre course_id — nome antigo)
  professors_professor_cursos_pkey                                     (PK — ok)

indexes:
  professors_professor_cursos_courseunit_id_f996437b                   (índice sobre course_id — nome antigo)
  professors_professor_cur_professor_id_courseunit__6318cef7_uniq
  professors_professor_cursos_pkey
  professors_professor_cursos_professor_id_4ad24c01
```

**Impacto:** nenhum em runtime. O Django introspecta constraints/índices por definição
(colunas/tipo), não pelo nome literal, então o funcionamento e futuras migrações não são
afetados. É apenas ruído de nomenclatura.

**Opção de limpeza (não obrigatória):** renomear esses objetos para refletir `course_id`, ou
— alternativa mais limpa por a tabela estar vazia — **dropar e recriar** a tabela M2M via
`schema_editor`, obtendo nomes 100% na convenção do Django. Não executado para manter o
reparo mínimo e reversível.

---

## 7. Impacto em Outros Ambientes (⚠️ atenção para Produção/Supabase)

Se o banco de **produção (Supabase)** — ou o de qualquer outro desenvolvedor — também foi
criado **antes** da troca `CourseUnit → Course`, ele terá **a mesma coluna defasada
`courseunit_id`** e falhará em `/professores/` com o mesmo 500.

**Antes de aplicar o reparo em produção, há uma diferença crítica:** verificar se
`professors_professor_cursos` **contém dados**.

- **Se estiver vazia:** o mesmo procedimento da Seção 4 é seguro.
- **Se tiver linhas:** um simples `RENAME` manteria valores que são **IDs de CourseUnit** sob
  uma FK que agora aponta para **Course** — semanticamente incorreto (e provavelmente
  violando a FK, pois os IDs podem não existir em `courses_course`). Nesse caso o reparo
  **precisa mapear/limpar os dados** primeiro (ex.: converter `courseunit_id` para o
  `course_id` correspondente via `courses_courseunit.course_id`, ou esvaziar a relação se ela
  puder ser recadastrada).

Para isso foi criado um **script idempotente de verificação + reparo**:

**`project_root/scripts/data_fixes/fix_professor_cursos_m2m.py`**

Comportamento:
- **DRY-RUN por padrão** (só diagnostica; não altera nada). Sempre rode assim primeiro.
- **Idempotente:** se a tabela já estiver correta (`course_id`), não faz nada.
- **Tabela vazia + defasada:** com `--apply`, faz o reparo trivial (drop FK → rename →
  add FK), tudo em transação, e verifica o resultado.
- **Tabela com dados + defasada:** exige `--apply --migrate-data`; mapeia
  `courseunit_id → courses_courseunit.course_id`, **deduplica** pares
  `(professor, course)` e recria FK/UNIQUE. Se houver linhas **órfãs** (courseunit
  inexistente) ou sem `course_id`, **aborta com rollback** e reporta para tratamento manual.
- Imprime o banco alvo (`NAME @ HOST`) antes de agir — confirme que é o ambiente certo.

Uso em produção (Supabase) — sempre dry-run antes:

```bash
set DJANGO_SETTINGS_MODULE=config.settings.production
..\.venv\Scripts\python.exe fix_professor_cursos_m2m.py                    # 1) diagnóstico
..\.venv\Scripts\python.exe fix_professor_cursos_m2m.py --apply            # 2) se vazia
..\.venv\Scripts\python.exe fix_professor_cursos_m2m.py --apply --migrate-data  # 2') se tiver dados
```

> Validado localmente no ciclo completo: dry-run detecta o estado defasado → `--apply`
> repara e confirma `estado=ok` → nova execução reporta idempotente ("nada a fazer").

---

## 8. Prevenção / Recomendações

1. **Nunca editar migração já aplicada in-place** quando o alvo de uma relação muda. O certo
   é gerar uma nova migração (`makemigrations`) que o Django materializa em `AlterField`/
   recriação da tabela M2M — assim o histórico reflete a troca e todos os bancos convergem.
2. **Padronizar a recriação de ambientes** a partir do zero periodicamente (drop + `migrate`)
   para flagrar divergências entre migrações e bancos legados antes que cheguem em produção.
3. **Smoke test pós-deploy** cobrindo as telas de listagem que usam `prefetch_related`
   (professores, alocações), já que esse tipo de erro só aparece na avaliação da query.
4. **Auditoria única** dos bancos legados (dev de cada dev + Supabase) buscando colunas
   `*courseunit*` remanescentes na tabela M2M, aplicando o reparo da Seção 7 conforme o caso.

---

## 9. Resumo das Alterações

| Item | Alteração |
|---|---|
| Código (`models.py`, `views.py`) | **Nenhuma** — já estava correto |
| Migrações | **Nenhuma** — já descrevem `course_id` corretamente |
| Banco local `harpia_db` | Tabela `professors_professor_cursos`: coluna `courseunit_id` → **`course_id`**; FK antiga (→ `courses_courseunit`) substituída por FK → **`courses_course`** |

---

## 10. Apêndice — Comandos de Diagnóstico e Reparo

Todos executados com o Python do venv e settings de desenvolvimento
(`DJANGO_SETTINGS_MODULE=config.settings.development`).

**Diagnóstico (somente leitura):**

```sql
-- colunas reais da tabela intermediária
SELECT column_name, data_type FROM information_schema.columns
WHERE table_name = 'professors_professor_cursos' ORDER BY ordinal_position;

-- FKs da tabela
SELECT tc.constraint_name, kcu.column_name, ccu.table_name AS foreign_table
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage ccu ON ccu.constraint_name = tc.constraint_name
WHERE tc.table_name = 'professors_professor_cursos' AND tc.constraint_type = 'FOREIGN KEY';

-- contagem (confirma que estava vazia)
SELECT COUNT(*) FROM professors_professor_cursos;
```

**Reparo (transação):** ver Seção 4.

**Validação:**

```bash
python manage.py makemigrations --check --dry-run          # → No changes detected
python manage.py shell -c "from apps.professors.models import Professor; \
  print(len(list(Professor.objects.prefetch_related('cursos'))))"   # → 26
```
