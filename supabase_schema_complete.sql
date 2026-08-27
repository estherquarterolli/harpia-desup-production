-- ============================================================================
-- ALLOCGEST COMPLETE SCHEMA FOR SUPABASE (PostgreSQL)
-- ============================================================================
-- This SQL script creates:
-- - ENUM types for data integrity
-- - Lookup/Reference tables
-- - Original application tables (optimized)
-- - Associative/Junction tables for many-to-many relationships
-- - Indexes for performance
-- ============================================================================

-- Step 1: Create ENUM Types
-- ============================================================================

CREATE TYPE user_perfil AS ENUM ('COORDENADOR_UNIDADE', 'DESUP');
CREATE TYPE professor_status AS ENUM ('Ativo', 'Inativo', 'Licença');
CREATE TYPE parecer_status AS ENUM ('PENDENTE', 'APROVADO', 'REJEITADO');
CREATE TYPE alocacao_status AS ENUM ('Rascunho', 'Enviado', 'Aprovado', 'Rejeitado');
CREATE TYPE pendencia_status AS ENUM ('RASCUNHO', 'ENVIADO', 'APROVADO', 'REJEITADO');
CREATE TYPE turno_enum AS ENUM ('M', 'N', 'V');
CREATE TYPE dia_semana_enum AS ENUM ('seg', 'ter', 'qua', 'qui', 'sex');

-- Step 2: Create Lookup/Reference Tables
-- ============================================================================

-- Turnos (Manhã, Noite, Vespertino)
CREATE TABLE IF NOT EXISTS "ref_turno" (
    "id" BIGSERIAL PRIMARY KEY,
    "codigo" turno_enum UNIQUE NOT NULL,
    "nome" VARCHAR(50) NOT NULL,
    "horario_inicio" TIME,
    "horario_fim" TIME,
    "criado_em" TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO "ref_turno" ("codigo", "nome", "horario_inicio", "horario_fim") VALUES
('M', 'Manhã', '07:00', '12:00'),
('N', 'Noite', '19:00', '23:00'),
('V', 'Vespertino', '13:00', '18:00')
ON CONFLICT DO NOTHING;

-- Dias da Semana
CREATE TABLE IF NOT EXISTS "ref_dia_semana" (
    "id" BIGSERIAL PRIMARY KEY,
    "codigo" dia_semana_enum UNIQUE NOT NULL,
    "nome" VARCHAR(20) NOT NULL,
    "ordem" SMALLINT UNIQUE
);

INSERT INTO "ref_dia_semana" ("codigo", "nome", "ordem") VALUES
('seg', 'Segunda', 1),
('ter', 'Terça', 2),
('qua', 'Quarta', 3),
('qui', 'Quinta', 4),
('sex', 'Sexta', 5)
ON CONFLICT DO NOTHING;

-- Step 3: Create Core Tables
-- ============================================================================

-- Unidades
CREATE TABLE IF NOT EXISTS "core_unidade" (
    "id" BIGSERIAL PRIMARY KEY,
    "nome" VARCHAR(255) NOT NULL UNIQUE,
    "sigla" VARCHAR(20) NOT NULL,
    "status" BOOLEAN NOT NULL DEFAULT TRUE
);

-- Cursos
CREATE TABLE IF NOT EXISTS "courses_course" (
    "id" BIGSERIAL PRIMARY KEY,
    "nome" VARCHAR(255) NOT NULL,
    "sigla" VARCHAR(20) NOT NULL,
    "unidade_id" BIGINT NOT NULL REFERENCES "core_unidade"("id") ON DELETE CASCADE
);

-- Componentes Curriculares
CREATE TABLE IF NOT EXISTS "courses_curricularcomponent" (
    "id" BIGSERIAL PRIMARY KEY,
    "nome" VARCHAR(255) NOT NULL,
    "sigla" VARCHAR(20) NOT NULL,
    "carga_horaria_padrao" INTEGER NOT NULL CHECK ("carga_horaria_padrao" >= 0),
    "codigo" VARCHAR(50) NOT NULL,
    "creditos" SMALLINT NOT NULL CHECK ("creditos" >= 0),
    "ementa" TEXT NOT NULL DEFAULT ''
);

-- Relação de Pré-requisitos entre Componentes
CREATE TABLE IF NOT EXISTS "courses_curricularcomponent_pre_requisitos" (
    "id" BIGSERIAL PRIMARY KEY,
    "from_curricularcomponent_id" BIGINT NOT NULL REFERENCES "courses_curricularcomponent"("id") ON DELETE CASCADE,
    "to_curricularcomponent_id" BIGINT NOT NULL REFERENCES "courses_curricularcomponent"("id") ON DELETE CASCADE
);

-- Matrizes Curriculares
CREATE TABLE IF NOT EXISTS "courses_curriculummatrix" (
    "id" BIGSERIAL PRIMARY KEY,
    "curso_id" BIGINT NOT NULL REFERENCES "courses_course"("id") ON DELETE CASCADE,
    "criada_em" TIMESTAMP,
    "is_vigente" BOOLEAN NOT NULL DEFAULT TRUE,
    "nome" VARCHAR(100) NOT NULL,
    "periodo_letivo" VARCHAR(20),
    "is_rascunho" BOOLEAN NOT NULL DEFAULT FALSE,
    "turno" turno_enum
);

-- Tipos de Contrato de Professor
CREATE TABLE IF NOT EXISTS "professors_contracttype" (
    "id" BIGSERIAL PRIMARY KEY,
    "nome" VARCHAR(100) NOT NULL,
    "regime_trabalho" VARCHAR(20) NOT NULL,
    "max_class_hours" INTEGER NOT NULL CHECK ("max_class_hours" >= 0),
    "max_total_hours" INTEGER NOT NULL CHECK ("max_total_hours" >= 0),
    "max_classes" INTEGER NOT NULL CHECK ("max_classes" >= 0),
    "categoria" VARCHAR(20) NOT NULL,
    "dias_presenca_obrigatorios" SMALLINT NOT NULL CHECK ("dias_presenca_obrigatorios" >= 0)
);

-- Professores
CREATE TABLE IF NOT EXISTS "professors_professor" (
    "id" BIGSERIAL PRIMARY KEY,
    "status" professor_status NOT NULL DEFAULT 'Ativo',
    "tipo_contrato_id" BIGINT NOT NULL REFERENCES "professors_contracttype"("id") ON DELETE CASCADE,
    "unidade_principal_id" BIGINT REFERENCES "core_unidade"("id") ON DELETE SET NULL,
    "desup_email" VARCHAR(254),
    "desup_nome" VARCHAR(255),
    "is_cedido" BOOLEAN NOT NULL DEFAULT FALSE,
    "rh_email" VARCHAR(254) NOT NULL,
    "rh_matricula" VARCHAR(50) NOT NULL UNIQUE,
    "rh_nome" VARCHAR(255) NOT NULL,
    "ha" INTEGER NOT NULL CHECK ("ha" >= 0) DEFAULT 0,
    "materia" VARCHAR(20) NOT NULL,
    "ID_FUNCIONAL" VARCHAR(50) NOT NULL UNIQUE
);

-- Componentes da Matriz
CREATE TABLE IF NOT EXISTS "courses_matrixcomponent" (
    "id" BIGSERIAL PRIMARY KEY,
    "codigo" VARCHAR(50) NOT NULL,
    "creditos" SMALLINT NOT NULL CHECK ("creditos" >= 0),
    "compartilhado" BOOLEAN NOT NULL DEFAULT FALSE,
    "carga_horaria_semanal" NUMERIC(8,2) NOT NULL,
    "distribuicao_semanal" TEXT NOT NULL DEFAULT '',
    "status" VARCHAR(20) NOT NULL DEFAULT 'COMPLETO',
    "observacoes" TEXT NOT NULL DEFAULT '',
    "componente_curricular_id" BIGINT NOT NULL REFERENCES "courses_curricularcomponent"("id") ON DELETE CASCADE,
    "curso_compartilhado_id" BIGINT REFERENCES "courses_course"("id") ON DELETE SET NULL,
    "docente_id" BIGINT REFERENCES "professors_professor"("id") ON DELETE SET NULL,
    "matriz_id" BIGINT NOT NULL REFERENCES "courses_curriculummatrix"("id") ON DELETE CASCADE,
    "periodo" VARCHAR(50) NOT NULL,
    "carga_horaria" INTEGER NOT NULL CHECK ("carga_horaria" >= 0)
);

-- Pré-requisitos de Componentes de Matriz
CREATE TABLE IF NOT EXISTS "courses_matrixcomponent_pre_requisitos" (
    "id" BIGSERIAL PRIMARY KEY,
    "matrixcomponent_id" BIGINT NOT NULL REFERENCES "courses_matrixcomponent"("id") ON DELETE CASCADE,
    "curricularcomponent_id" BIGINT NOT NULL REFERENCES "courses_curricularcomponent"("id") ON DELETE CASCADE
);

-- Turmas
CREATE TABLE IF NOT EXISTS "courses_classgroup" (
    "id" BIGSERIAL PRIMARY KEY,
    "ano_semestre" VARCHAR(20) NOT NULL,
    "identificador" VARCHAR(50) NOT NULL,
    "matriz_curricular_id" BIGINT NOT NULL REFERENCES "courses_curriculummatrix"("id") ON DELETE CASCADE,
    "matriz_componente_id" BIGINT REFERENCES "courses_matrixcomponent"("id") ON DELETE SET NULL
);

-- Usuários (Accounts)
CREATE TABLE IF NOT EXISTS "accounts_user" (
    "id" BIGSERIAL PRIMARY KEY,
    "password" VARCHAR(128) NOT NULL,
    "last_login" TIMESTAMP,
    "is_superuser" BOOLEAN NOT NULL DEFAULT FALSE,
    "username" VARCHAR(150) NOT NULL UNIQUE,
    "first_name" VARCHAR(150) NOT NULL DEFAULT '',
    "last_name" VARCHAR(150) NOT NULL DEFAULT '',
    "is_staff" BOOLEAN NOT NULL DEFAULT FALSE,
    "is_active" BOOLEAN NOT NULL DEFAULT TRUE,
    "date_joined" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "email" VARCHAR(254) NOT NULL UNIQUE,
    "perfil" user_perfil NOT NULL,
    "dados_submetidos" BOOLEAN NOT NULL DEFAULT FALSE,
    "unidade_id" BIGINT REFERENCES "core_unidade"("id") ON DELETE SET NULL,
    "forcar_troca_senha" BOOLEAN NOT NULL DEFAULT FALSE
);

-- Grupos de Usuários
CREATE TABLE IF NOT EXISTS "auth_group" (
    "id" BIGSERIAL PRIMARY KEY,
    "name" VARCHAR(150) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS "accounts_user_groups" (
    "id" BIGSERIAL PRIMARY KEY,
    "user_id" BIGINT NOT NULL REFERENCES "accounts_user"("id") ON DELETE CASCADE,
    "group_id" BIGINT NOT NULL REFERENCES "auth_group"("id") ON DELETE CASCADE
);

-- Permissões
CREATE TABLE IF NOT EXISTS "auth_permission" (
    "id" BIGSERIAL PRIMARY KEY,
    "content_type_id" INTEGER NOT NULL,
    "codename" VARCHAR(100) NOT NULL,
    "name" VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS "accounts_user_user_permissions" (
    "id" BIGSERIAL PRIMARY KEY,
    "user_id" BIGINT NOT NULL REFERENCES "accounts_user"("id") ON DELETE CASCADE,
    "permission_id" BIGINT NOT NULL REFERENCES "auth_permission"("id") ON DELETE CASCADE
);

-- Solicitação de Reset de Senha
CREATE TABLE IF NOT EXISTS "accounts_passwordresetrequest" (
    "id" BIGSERIAL PRIMARY KEY,
    "token" CHAR(32) NOT NULL UNIQUE,
    "criado_em" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "finalizado" BOOLEAN NOT NULL DEFAULT FALSE,
    "finalizado_em" TIMESTAMP,
    "aprovado_por_id" BIGINT REFERENCES "accounts_user"("id") ON DELETE SET NULL,
    "user_id" BIGINT NOT NULL REFERENCES "accounts_user"("id") ON DELETE CASCADE
);

-- Solicitação de Troca de Senha
CREATE TABLE IF NOT EXISTS "accounts_selfpasswordchangerequest" (
    "id" BIGSERIAL PRIMARY KEY,
    "token" CHAR(32) NOT NULL UNIQUE,
    "criado_em" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "usado" BOOLEAN NOT NULL DEFAULT FALSE,
    "usado_em" TIMESTAMP,
    "solicitado_ip" INET,
    "user_id" BIGINT NOT NULL REFERENCES "accounts_user"("id") ON DELETE CASCADE
);

-- Alocação Curricular
CREATE TABLE IF NOT EXISTS "allocations_alocacaocurricular" (
    "id" BIGSERIAL PRIMARY KEY,
    "semestre" VARCHAR(10) NOT NULL,
    "turno" turno_enum NOT NULL,
    "status" alocacao_status NOT NULL DEFAULT 'Rascunho',
    "sei_numero" VARCHAR(50),
    "data_criacao" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "data_ultimo_ajuste" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "curso_id" BIGINT NOT NULL REFERENCES "courses_course"("id") ON DELETE CASCADE,
    "unidade_id" BIGINT NOT NULL REFERENCES "core_unidade"("id") ON DELETE CASCADE
);

-- Janela de Entrega
CREATE TABLE IF NOT EXISTS "core_janelaentrega" (
    "id" BIGSERIAL PRIMARY KEY,
    "semestre" VARCHAR(10) NOT NULL,
    "data_inicio" DATE NOT NULL,
    "data_fim" DATE NOT NULL,
    "status" VARCHAR(20) NOT NULL DEFAULT 'Aberto',
    "unidade_id" BIGINT REFERENCES "core_unidade"("id") ON DELETE CASCADE
);

-- Notificações
CREATE TABLE IF NOT EXISTS "core_notificacao" (
    "id" BIGSERIAL PRIMARY KEY,
    "titulo" VARCHAR(255) NOT NULL,
    "mensagem" TEXT NOT NULL,
    "lida" BOOLEAN NOT NULL DEFAULT FALSE,
    "url_acao" VARCHAR(255),
    "data_criacao" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "destinatario_id" BIGINT REFERENCES "accounts_user"("id") ON DELETE CASCADE,
    "unidade_destino_id" BIGINT REFERENCES "core_unidade"("id") ON DELETE CASCADE
);

-- Auditoria Global
CREATE TABLE IF NOT EXISTS "core_auditoriaglobal" (
    "id" BIGSERIAL PRIMARY KEY,
    "email" VARCHAR(254) NOT NULL,
    "acao" VARCHAR(120) NOT NULL,
    "detalhes" TEXT NOT NULL,
    "ip" INET,
    "user_agent" TEXT NOT NULL,
    "criado_em" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "usuario_id" BIGINT REFERENCES "accounts_user"("id") ON DELETE SET NULL
);

-- Disponibilidade de Professor (ORIGINAL - mantida para compatibilidade)
CREATE TABLE IF NOT EXISTS "professors_availability" (
    "id" BIGSERIAL PRIMARY KEY,
    "dia_semana" INTEGER NOT NULL,
    "turno" turno_enum NOT NULL,
    "professor_id" BIGINT NOT NULL REFERENCES "professors_professor"("id") ON DELETE CASCADE
);

-- Cursos de Professor
CREATE TABLE IF NOT EXISTS "professors_professor_cursos" (
    "id" BIGSERIAL PRIMARY KEY,
    "professor_id" BIGINT NOT NULL REFERENCES "professors_professor"("id") ON DELETE CASCADE,
    "course_id" BIGINT NOT NULL REFERENCES "courses_course"("id") ON DELETE CASCADE
);

-- Registro de Ausência de Professor
CREATE TABLE IF NOT EXISTS "professors_absencerecord" (
    "id" BIGSERIAL PRIMARY KEY,
    "data_inicio" DATE NOT NULL,
    "data_fim" DATE NOT NULL,
    "motivo" TEXT NOT NULL,
    "comprovante" VARCHAR(100),
    "professor_id" BIGINT NOT NULL REFERENCES "professors_professor"("id") ON DELETE CASCADE
);

-- Pendência Extracurricular
CREATE TABLE IF NOT EXISTS "extra_curricular_pendenciaextra" (
    "id" BIGSERIAL PRIMARY KEY,
    "semestre" VARCHAR(10) NOT NULL,
    "sei_numero" VARCHAR(50),
    "status" pendencia_status NOT NULL DEFAULT 'RASCUNHO',
    "data_criacao" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "data_atualizacao" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "criado_por_id" BIGINT REFERENCES "accounts_user"("id") ON DELETE SET NULL,
    "professor_id" BIGINT NOT NULL REFERENCES "professors_professor"("id") ON DELETE CASCADE,
    "unidade_id" BIGINT NOT NULL REFERENCES "core_unidade"("id") ON DELETE CASCADE,
    "motivo_status_desup" TEXT NOT NULL DEFAULT ''
);

-- Orientação de TCC
CREATE TABLE IF NOT EXISTS "extra_curricular_orientacaotcc" (
    "id" BIGSERIAL PRIMARY KEY,
    "num_orientandos" SMALLINT NOT NULL CHECK ("num_orientandos" >= 0),
    "carga_horaria" NUMERIC(8,2) NOT NULL,
    "parecer_desup" parecer_status NOT NULL DEFAULT 'PENDENTE',
    "motivo_parecer" TEXT NOT NULL DEFAULT '',
    "data_atualizacao" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "pendencia_id" BIGINT NOT NULL REFERENCES "extra_curricular_pendenciaextra"("id") ON DELETE CASCADE,
    "horas_aprovadas" NUMERIC(8,2)
);

-- Atividade Extensionista
CREATE TABLE IF NOT EXISTS "extra_curricular_atividadeextensionista" (
    "id" BIGSERIAL PRIMARY KEY,
    "num_estudantes" INTEGER NOT NULL CHECK ("num_estudantes" >= 0),
    "carga_horaria" NUMERIC(8,2) NOT NULL,
    "parecer_desup" parecer_status NOT NULL DEFAULT 'PENDENTE',
    "motivo_parecer" TEXT NOT NULL DEFAULT '',
    "data_atualizacao" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "pendencia_id" BIGINT NOT NULL REFERENCES "extra_curricular_pendenciaextra"("id") ON DELETE CASCADE,
    "horas_aprovadas" NUMERIC(8,2)
);

-- Redução de Carga Horária
CREATE TABLE IF NOT EXISTS "extra_curricular_reducaocargahoraria" (
    "id" BIGSERIAL PRIMARY KEY,
    "motivo_reducao" TEXT NOT NULL,
    "horas_reduzidas" NUMERIC(8,2) NOT NULL,
    "parecer_desup" parecer_status NOT NULL DEFAULT 'PENDENTE',
    "motivo_parecer" TEXT NOT NULL DEFAULT '',
    "data_atualizacao" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "pendencia_id" BIGINT NOT NULL REFERENCES "extra_curricular_pendenciaextra"("id") ON DELETE CASCADE,
    "horas_aprovadas" NUMERIC(8,2)
);

-- ============================================================================
-- Step 4: Create Associative/Junction Tables for Better Normalization
-- ============================================================================

-- Professor works in multiple units
CREATE TABLE IF NOT EXISTS "professor_unidade_assoc" (
    "id" BIGSERIAL PRIMARY KEY,
    "professor_id" BIGINT NOT NULL REFERENCES "professors_professor"("id") ON DELETE CASCADE,
    "unidade_id" BIGINT NOT NULL REFERENCES "core_unidade"("id") ON DELETE CASCADE,
    "eh_principal" BOOLEAN NOT NULL DEFAULT FALSE,
    "data_inicio" DATE NOT NULL DEFAULT CURRENT_DATE,
    "data_fim" DATE,
    UNIQUE("professor_id", "unidade_id")
);

-- Allocate professors to curriculum allocations
CREATE TABLE IF NOT EXISTS "alocacao_professor_assoc" (
    "id" BIGSERIAL PRIMARY KEY,
    "alocacao_id" BIGINT NOT NULL REFERENCES "allocations_alocacaocurricular"("id") ON DELETE CASCADE,
    "professor_id" BIGINT NOT NULL REFERENCES "professors_professor"("id") ON DELETE CASCADE,
    "componente_id" BIGINT REFERENCES "courses_matrixcomponent"("id") ON DELETE SET NULL,
    "data_alocacao" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "data_remocao" TIMESTAMP,
    UNIQUE("alocacao_id", "professor_id", "componente_id")
);

-- Assign professors to class groups
CREATE TABLE IF NOT EXISTS "classgroup_professor_assoc" (
    "id" BIGSERIAL PRIMARY KEY,
    "classgroup_id" BIGINT NOT NULL REFERENCES "courses_classgroup"("id") ON DELETE CASCADE,
    "professor_id" BIGINT NOT NULL REFERENCES "professors_professor"("id") ON DELETE CASCADE,
    "componente_id" BIGINT REFERENCES "courses_matrixcomponent"("id") ON DELETE SET NULL,
    "data_inicio" DATE NOT NULL DEFAULT CURRENT_DATE,
    "data_fim" DATE,
    UNIQUE("classgroup_id", "professor_id", "componente_id")
);

-- Normalized professor availability (references lookup tables)
CREATE TABLE IF NOT EXISTS "professor_availability_v2" (
    "id" BIGSERIAL PRIMARY KEY,
    "professor_id" BIGINT NOT NULL REFERENCES "professors_professor"("id") ON DELETE CASCADE,
    "dia_semana_id" BIGINT NOT NULL REFERENCES "ref_dia_semana"("id") ON DELETE CASCADE,
    "turno_id" BIGINT NOT NULL REFERENCES "ref_turno"("id") ON DELETE CASCADE,
    "ativo" BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE("professor_id", "dia_semana_id", "turno_id")
);

-- Track extracurricular hours by type
CREATE TABLE IF NOT EXISTS "extracurricular_professor_horas" (
    "id" BIGSERIAL PRIMARY KEY,
    "professor_id" BIGINT NOT NULL REFERENCES "professors_professor"("id") ON DELETE CASCADE,
    "pendencia_id" BIGINT NOT NULL REFERENCES "extra_curricular_pendenciaextra"("id") ON DELETE CASCADE,
    "tipo" VARCHAR(50) NOT NULL,
    "horas_solicitadas" NUMERIC(8,2) NOT NULL,
    "horas_aprovadas" NUMERIC(8,2),
    "data_solicitacao" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE("professor_id", "pendencia_id", "tipo")
);

-- Courses have many components
CREATE TABLE IF NOT EXISTS "curso_componente_assoc" (
    "id" BIGSERIAL PRIMARY KEY,
    "curso_id" BIGINT NOT NULL REFERENCES "courses_course"("id") ON DELETE CASCADE,
    "componente_id" BIGINT NOT NULL REFERENCES "courses_curricularcomponent"("id") ON DELETE CASCADE,
    "periodo" SMALLINT,
    "obrigatorio" BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE("curso_id", "componente_id")
);

-- ============================================================================
-- Step 5: Create Indexes for Performance
-- ============================================================================

-- Core tables
CREATE INDEX idx_accounts_user_email ON "accounts_user" ("email");
CREATE INDEX idx_accounts_user_username ON "accounts_user" ("username");
CREATE INDEX idx_professors_professor_rh_matricula ON "professors_professor" ("rh_matricula");
CREATE INDEX idx_professors_professor_id_funcional ON "professors_professor" ("ID_FUNCIONAL");
CREATE INDEX idx_courses_course_unidade_id ON "courses_course" ("unidade_id");
CREATE INDEX idx_core_unidade_sigla ON "core_unidade" ("sigla");
CREATE INDEX idx_allocations_alocacaocurricular_curso_id ON "allocations_alocacaocurricular" ("curso_id");
CREATE INDEX idx_allocations_alocacaocurricular_unidade_id ON "allocations_alocacaocurricular" ("unidade_id");
CREATE INDEX idx_extra_curricular_pendenciaextra_professor_id ON "extra_curricular_pendenciaextra" ("professor_id");
CREATE INDEX idx_extra_curricular_pendenciaextra_unidade_id ON "extra_curricular_pendenciaextra" ("unidade_id");
CREATE INDEX idx_courses_matrixcomponent_matriz_id ON "courses_matrixcomponent" ("matriz_id");
CREATE INDEX idx_courses_matrixcomponent_docente_id ON "courses_matrixcomponent" ("docente_id");

-- Associative tables
CREATE INDEX idx_professor_unidade_assoc_professor_id ON "professor_unidade_assoc" ("professor_id");
CREATE INDEX idx_professor_unidade_assoc_unidade_id ON "professor_unidade_assoc" ("unidade_id");
CREATE INDEX idx_alocacao_professor_assoc_alocacao_id ON "alocacao_professor_assoc" ("alocacao_id");
CREATE INDEX idx_alocacao_professor_assoc_professor_id ON "alocacao_professor_assoc" ("professor_id");
CREATE INDEX idx_classgroup_professor_assoc_classgroup_id ON "classgroup_professor_assoc" ("classgroup_id");
CREATE INDEX idx_classgroup_professor_assoc_professor_id ON "classgroup_professor_assoc" ("professor_id");
CREATE INDEX idx_professor_availability_v2_professor_id ON "professor_availability_v2" ("professor_id");
CREATE INDEX idx_professor_availability_v2_dia_semana_id ON "professor_availability_v2" ("dia_semana_id");
CREATE INDEX idx_extracurricular_professor_horas_professor_id ON "extracurricular_professor_horas" ("professor_id");
CREATE INDEX idx_curso_componente_assoc_curso_id ON "curso_componente_assoc" ("curso_id");

-- ============================================================================
-- Step 6: Migrate Data to New Normalized Tables (Optional - comment out if not needed)
-- ============================================================================

-- Migrate availability data to normalized table
-- INSERT INTO professor_availability_v2 (professor_id, dia_semana_id, turno_id, ativo)
-- SELECT pa.professor_id, rd.id, rt.id, true
-- FROM professors_availability pa
-- JOIN ref_dia_semana rd ON rd.codigo = pa.dia_semana::text
-- JOIN ref_turno rt ON rt.codigo = pa.turno
-- ON CONFLICT DO NOTHING;

-- Migrate professor units
-- INSERT INTO professor_unidade_assoc (professor_id, unidade_id, eh_principal)
-- SELECT id, unidade_principal_id, true
-- FROM professors_professor
-- WHERE unidade_principal_id IS NOT NULL
-- ON CONFLICT DO NOTHING;

-- ============================================================================
-- Done! Schema is ready for production.
-- ============================================================================
-- Created:
-- - 7 ENUM types for data integrity
-- - 2 lookup/reference tables with default data
-- - 25+ core application tables
-- - 6 associative/junction tables for normalization
-- - 20+ indexes for performance optimization
-- ============================================================================
