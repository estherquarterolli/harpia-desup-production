# Guia de Tabelas Associativas - Modelagem Completa

## 📋 Visão Geral

A nova migração cria **6 tabelas associativas + 2 lookup tables** para uma modelagem muito mais robusta e escalável.

---

## 🔄 Tabelas Associativas Criadas

### 1️⃣ **professor_unidade_assoc**
**Propósito:** Um professor pode trabalhar em múltiplas unidades

```sql
CREATE TABLE "professor_unidade_assoc" (
    "id" BIGSERIAL PRIMARY KEY,
    "professor_id" BIGINT NOT NULL,
    "unidade_id" BIGINT NOT NULL,
    "eh_principal" BOOLEAN DEFAULT FALSE,  -- Unidade principal
    "data_inicio" DATE NOT NULL,
    "data_fim" DATE,                        -- NULL = ativo
    UNIQUE("professor_id", "unidade_id")
);
```

**Exemplo:**
```
Prof. João:
  - FAETERJ Paracambi (principal) → 2024-01-01 até agora
  - FAETERJ Duque de Caxias (secundária) → 2024-06-01 até agora
```

**Benefício:** Antes `professors_professor.unidade_principal_id` (1 unidade). Agora: **múltiplas unidades** ✅

---

### 2️⃣ **alocacao_professor_assoc**
**Propósito:** Alocar professores para alocações curriculares

```sql
CREATE TABLE "alocacao_professor_assoc" (
    "id" BIGSERIAL PRIMARY KEY,
    "alocacao_id" BIGINT NOT NULL,         -- Alocação curricular
    "professor_id" BIGINT NOT NULL,        -- Professor
    "componente_id" BIGINT,                -- Componente específico (opcional)
    "data_alocacao" TIMESTAMP,
    "data_remocao" TIMESTAMP,              -- NULL = ativo
    UNIQUE("alocacao_id", "professor_id", "componente_id")
);
```

**Exemplo:**
```
Alocação "ADS 2026.1 Noite":
  - Prof. João → Banco de Dados (alocado em 2026-01-15)
  - Prof. Maria → Programação (alocado em 2026-01-15)
  - Prof. Pedro → Redes (removido em 2026-02-01, substituído por Prof. Ana)
```

**Benefício:** Antes não havia relação direta professor↔alocação. Agora: **tracking completo de alocações** ✅

---

### 3️⃣ **classgroup_professor_assoc**
**Propósito:** Atribuir professores a turmas específicas

```sql
CREATE TABLE "classgroup_professor_assoc" (
    "id" BIGSERIAL PRIMARY KEY,
    "classgroup_id" BIGINT NOT NULL,       -- Turma
    "professor_id" BIGINT NOT NULL,        -- Professor
    "componente_id" BIGINT,                -- Componente da turma
    "data_inicio" DATE NOT NULL,
    "data_fim" DATE,                       -- NULL = ativo
    UNIQUE("classgroup_id", "professor_id", "componente_id")
);
```

**Exemplo:**
```
Turma "ADS2024.1-A" (2º período):
  - Prof. João → Banco de Dados I (2024-02-01 até 2024-07-30)
  - Prof. Maria → Programação OO (2024-02-01 até 2024-07-30)
```

**Benefício:** Antes não havia. Agora: **saber exatamente qual professor leciona qual turma** ✅

---

### 4️⃣ **professor_availability_v2**
**Propósito:** Disponibilidade normalizada (referencia lookup tables)

```sql
CREATE TABLE "professor_availability_v2" (
    "id" BIGSERIAL PRIMARY KEY,
    "professor_id" BIGINT NOT NULL,
    "dia_semana_id" BIGINT NOT NULL,      -- FK para ref_dia_semana
    "turno_id" BIGINT NOT NULL,           -- FK para ref_turno
    "ativo" BOOLEAN DEFAULT TRUE,
    UNIQUE("professor_id", "dia_semana_id", "turno_id")
);
```

**Antes (SQLite):**
```sql
"dia_semana" INTEGER (1-7?)  -- Ambíguo!
"turno" VARCHAR(1) ('M','N','V')  -- String mágica
```

**Depois (PostgreSQL):**
```sql
dia_semana_id → ref_dia_semana.id
  ↓ (FK válida)
ref_dia_semana: (seg=1, ter=2, qua=3, qui=4, sex=5)

turno_id → ref_turno.id
  ↓ (FK válida)
ref_turno: (M=Manhã 07:00-12:00, N=Noite 19:00-23:00, V=Vespertino 13:00-18:00)
```

**Benefício:** Sem strings mágicas! Dados consistentes com horários! ✅

---

### 5️⃣ **extracurricular_professor_horas**
**Propósito:** Rastrear horas extracurriculares por tipo

```sql
CREATE TABLE "extracurricular_professor_horas" (
    "id" BIGSERIAL PRIMARY KEY,
    "professor_id" BIGINT NOT NULL,
    "pendencia_id" BIGINT NOT NULL,
    "tipo" VARCHAR(50) NOT NULL,          -- orientacao_tcc, atividade_extensionista, etc
    "horas_solicitadas" NUMERIC(8,2),
    "horas_aprovadas" NUMERIC(8,2),
    "data_solicitacao" TIMESTAMP,
    UNIQUE("professor_id", "pendencia_id", "tipo")
);
```

**Exemplo:**
```
Prof. João - Pendência Extra 2026.1:
  - orientacao_tcc: 8h solicitadas → 8h aprovadas
  - atividade_extensionista: 10h solicitadas → 5h aprovadas
  - reducao_cargahoraria: 4h solicitadas → 4h aprovadas
```

**Benefício:** Antes dados espalhados em 3 tabelas. Agora: **visão 360° de horas** ✅

---

### 6️⃣ **curso_componente_assoc**
**Propósito:** Curso tem muitos componentes (muitos-para-muitos)

```sql
CREATE TABLE "curso_componente_assoc" (
    "id" BIGSERIAL PRIMARY KEY,
    "curso_id" BIGINT NOT NULL,
    "componente_id" BIGINT NOT NULL,
    "periodo" SMALLINT,                   -- 1º, 2º, 3º semestre
    "obrigatorio" BOOLEAN DEFAULT TRUE,
    UNIQUE("curso_id", "componente_id")
);
```

**Exemplo:**
```
Curso "ADS":
  - Algoritmos (componente 1) → Período 1, Obrigatório
  - Banco de Dados I (componente 6) → Período 2, Obrigatório
  - Projeto Integrador (componente 10) → Período 4, Obrigatório
```

**Benefício:** Normalização completa! ✅

---

## 📊 Lookup/Reference Tables

### **ref_turno**
```sql
CREATE TABLE "ref_turno" (
    "id" BIGSERIAL PRIMARY KEY,
    "codigo" turno_enum UNIQUE,        -- 'M', 'N', 'V'
    "nome" VARCHAR(50),                -- 'Manhã', 'Noite', 'Vespertino'
    "horario_inicio" TIME,             -- '07:00'
    "horario_fim" TIME,                -- '12:00'
    "criado_em" TIMESTAMP
);
```

**Dados pré-populados:**
| id | código | nome | início | fim |
|----|--------|------|--------|-----|
| 1 | M | Manhã | 07:00 | 12:00 |
| 2 | N | Noite | 19:00 | 23:00 |
| 3 | V | Vespertino | 13:00 | 18:00 |

---

### **ref_dia_semana**
```sql
CREATE TABLE "ref_dia_semana" (
    "id" BIGSERIAL PRIMARY KEY,
    "codigo" dia_semana_enum UNIQUE,   -- 'seg', 'ter', 'qua', 'qui', 'sex'
    "nome" VARCHAR(20),                -- 'Segunda', 'Terça', etc
    "ordem" SMALLINT UNIQUE            -- 1-5 (para ordenar)
);
```

**Dados pré-populados:**
| id | código | nome | ordem |
|----|--------|------|-------|
| 1 | seg | Segunda | 1 |
| 2 | ter | Terça | 2 |
| 3 | qua | Quarta | 3 |
| 4 | qui | Quinta | 4 |
| 5 | sex | Sexta | 5 |

---

## 🔗 Diagrama de Relações

```
professor ──┬─→ professor_unidade_assoc ──→ unidade
            │
            ├─→ alocacao_professor_assoc ──→ alocacao_curricular
            │                             └──→ matrix_componente
            │
            ├─→ classgroup_professor_assoc ──→ classgroup
            │
            ├─→ professor_availability_v2 ──┬─→ ref_turno
            │                               └─→ ref_dia_semana
            │
            └─→ extracurricular_professor_horas ──→ pendencia_extra
```

---

## ✨ Melhorias na Modelagem

| Aspecto | Antes | Depois |
|---------|-------|--------|
| **Professor × Unidade** | 1:1 (unidade_principal_id) | **N:N (com datas)** ✅ |
| **Professor × Alocação** | Não existe | **N:N (com rastreamento)** ✅ |
| **Professor × Turma** | Não existe | **N:N (com componente)** ✅ |
| **Disponibilidade** | INTEGER/VARCHAR mágico | **FK para lookup tables** ✅ |
| **Horas Extracurriculares** | 3 tabelas separadas | **1 tabela centralizada** ✅ |
| **Componente × Curso** | Não formalizado | **N:N (com período)** ✅ |
| **Integridade Referencial** | Parcial | **Completa com CASCADE** ✅ |
| **Performance** | Sem índices | **Índices em todas FKs** ✅ |

---

## 🚀 Como Usar

```bash
# 1. Rodar migração completa
cd project_root
python migrate_to_supabase_complete.py

# 2. Marcar migrations
python manage.py migrate --fake-initial

# 3. Testar
python manage.py shell
>>> from professors.models import Professor
>>> from django.db import connection
>>> connection.ensure_connection()
>>> print("✓ Conectado com sucesso!")
```

---

## 🔍 Queries Úteis (no Django Shell)

```python
# 1. Todos os professores que trabalham na unidade X
from professor_unidade_assoc.models import ProfessorUnidadeAssoc
from core.models import Unidade

unidade = Unidade.objects.get(sigla='FAETERJ-PCB')
professores = ProfessorUnidadeAssoc.objects.filter(
    unidade=unidade, 
    data_fim__isnull=True
).values_list('professor__rh_nome', flat=True)

# 2. Disponibilidade de um professor
from professor_availability_v2.models import ProfessorAvailabilityV2

prof = Professor.objects.get(rh_matricula='MAT-123')
disponibilidade = ProfessorAvailabilityV2.objects.filter(
    professor=prof,
    ativo=True
).select_related('dia_semana', 'turno')

# 3. Total de horas extracurriculares de um professor
from extracurricular_professor_horas.models import ExtracurricularProfessorHoras

prof = Professor.objects.get(rh_matricula='MAT-123')
horas = ExtracurricularProfessorHoras.objects.filter(
    professor=prof
).values('tipo').annotate(
    total=Sum('horas_aprovadas')
)

# 4. Professores alocados a uma alocação curricular
from alocacao_professor_assoc.models import AlocacaoProfessorAssoc

alocacao = AlocacaoCurricular.objects.get(id=1)
professores = AlocacaoProfessorAssoc.objects.filter(
    alocacao=alocacao,
    data_remocao__isnull=True
).select_related('professor', 'componente')
```

---

## ✅ Checklist de Verificação

- [ ] Script rodou sem erros
- [ ] Todas 6 tabelas associativas criadas
- [ ] 2 lookup tables criadas e populadas
- [ ] Todos os índices criados
- [ ] Dados migrados para tabelas v2
- [ ] 0 constraint violations
- [ ] Django migrations aplicadas (`--fake-initial`)
- [ ] Tests locais passando
- [ ] Supabase dashboard mostra todas as tabelas
- [ ] Performance OK em queries complexas

---

## 📝 Notas Importantes

1. **As tabelas antigas (professors_availability, etc) ainda existem** - para compatibilidade com migrations do Django. Você pode deletá-las depois de confirmar tudo funcionando.

2. **Django ORM pode não reconhecer as novas tabelas** - crie models Django para as novas tabelas:
   ```python
   # apps/professors/models.py
   class ProfessorUnidadeAssoc(models.Model):
       professor = models.ForeignKey(Professor, on_delete=models.CASCADE)
       unidade = models.ForeignKey(Unidade, on_delete=models.CASCADE)
       eh_principal = models.BooleanField(default=False)
       data_inicio = models.DateField()
       data_fim = models.DateField(null=True, blank=True)
       
       class Meta:
           unique_together = ('professor', 'unidade')
   ```

3. **Lookup tables são imutáveis** - não mudem os valores em `ref_turno` ou `ref_dia_semana` uma vez em produção, pois quebra referências.

4. **Data Integrity** - Com CASCADE ON DELETE, deletar um professor deleta todos os registros relacionados. Use com cuidado em produção!

---

Pronto para produção! 🚀
