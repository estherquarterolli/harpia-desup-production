-- SQLite3 Database Schema Export
-- Generated from db.sqlite3

-- Table: accounts_passwordresetrequest
CREATE TABLE "accounts_passwordresetrequest" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "token" char(32) NOT NULL UNIQUE, "criado_em" datetime NOT NULL, "finalizado" bool NOT NULL, "finalizado_em" datetime NULL, "aprovado_por_id" bigint NULL REFERENCES "accounts_user" ("id") DEFERRABLE INITIALLY DEFERRED, "user_id" bigint NOT NULL REFERENCES "accounts_user" ("id") DEFERRABLE INITIALLY DEFERRED);

-- Table: accounts_selfpasswordchangerequest
CREATE TABLE "accounts_selfpasswordchangerequest" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "token" char(32) NOT NULL UNIQUE, "criado_em" datetime NOT NULL, "usado" bool NOT NULL, "usado_em" datetime NULL, "solicitado_ip" char(39) NULL, "user_id" bigint NOT NULL REFERENCES "accounts_user" ("id") DEFERRABLE INITIALLY DEFERRED);

-- Table: accounts_user
CREATE TABLE "accounts_user" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "password" varchar(128) NOT NULL, "last_login" datetime NULL, "is_superuser" bool NOT NULL, "username" varchar(150) NOT NULL UNIQUE, "first_name" varchar(150) NOT NULL, "last_name" varchar(150) NOT NULL, "is_staff" bool NOT NULL, "is_active" bool NOT NULL, "date_joined" datetime NOT NULL, "email" varchar(254) NOT NULL UNIQUE, "perfil" varchar(30) NOT NULL, "dados_submetidos" bool NOT NULL, "unidade_id" bigint NULL REFERENCES "core_unidade" ("id") DEFERRABLE INITIALLY DEFERRED, "forcar_troca_senha" bool NOT NULL);

-- Table: accounts_user_groups
CREATE TABLE "accounts_user_groups" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "user_id" bigint NOT NULL REFERENCES "accounts_user" ("id") DEFERRABLE INITIALLY DEFERRED, "group_id" integer NOT NULL REFERENCES "auth_group" ("id") DEFERRABLE INITIALLY DEFERRED);

-- Table: accounts_user_user_permissions
CREATE TABLE "accounts_user_user_permissions" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "user_id" bigint NOT NULL REFERENCES "accounts_user" ("id") DEFERRABLE INITIALLY DEFERRED, "permission_id" integer NOT NULL REFERENCES "auth_permission" ("id") DEFERRABLE INITIALLY DEFERRED);

-- Table: allocations_alocacaocurricular
CREATE TABLE "allocations_alocacaocurricular" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "semestre" varchar(10) NOT NULL, "turno" varchar(1) NOT NULL, "status" varchar(20) NOT NULL, "sei_numero" varchar(50) NULL, "data_criacao" datetime NOT NULL, "data_ultimo_ajuste" datetime NOT NULL, "curso_id" bigint NOT NULL REFERENCES "courses_course" ("id") DEFERRABLE INITIALLY DEFERRED, "unidade_id" bigint NOT NULL REFERENCES "core_unidade" ("id") DEFERRABLE INITIALLY DEFERRED);

-- Table: auth_group
CREATE TABLE "auth_group" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "name" varchar(150) NOT NULL UNIQUE);

-- Table: auth_group_permissions
CREATE TABLE "auth_group_permissions" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "group_id" integer NOT NULL REFERENCES "auth_group" ("id") DEFERRABLE INITIALLY DEFERRED, "permission_id" integer NOT NULL REFERENCES "auth_permission" ("id") DEFERRABLE INITIALLY DEFERRED);

-- Table: auth_permission
CREATE TABLE "auth_permission" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "content_type_id" integer NOT NULL REFERENCES "django_content_type" ("id") DEFERRABLE INITIALLY DEFERRED, "codename" varchar(100) NOT NULL, "name" varchar(255) NOT NULL);

-- Table: core_auditoriaglobal
CREATE TABLE "core_auditoriaglobal" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "email" varchar(254) NOT NULL, "acao" varchar(120) NOT NULL, "detalhes" text NOT NULL, "ip" char(39) NULL, "user_agent" text NOT NULL, "criado_em" datetime NOT NULL, "usuario_id" bigint NULL REFERENCES "accounts_user" ("id") DEFERRABLE INITIALLY DEFERRED);

-- Table: core_janelaentrega
CREATE TABLE "core_janelaentrega" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "semestre" varchar(10) NOT NULL, "data_inicio" date NOT NULL, "data_fim" date NOT NULL, "status" varchar(20) NOT NULL, "unidade_id" bigint NULL REFERENCES "core_unidade" ("id") DEFERRABLE INITIALLY DEFERRED);

-- Table: core_notificacao
CREATE TABLE "core_notificacao" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "titulo" varchar(255) NOT NULL, "mensagem" text NOT NULL, "lida" bool NOT NULL, "url_acao" varchar(255) NULL, "data_criacao" datetime NOT NULL, "destinatario_id" bigint NULL REFERENCES "accounts_user" ("id") DEFERRABLE INITIALLY DEFERRED, "unidade_destino_id" bigint NULL REFERENCES "core_unidade" ("id") DEFERRABLE INITIALLY DEFERRED);

-- Table: core_unidade
CREATE TABLE "core_unidade" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "nome" varchar(255) NOT NULL UNIQUE, "sigla" varchar(20) NOT NULL, "status" bool NOT NULL);

-- Table: courses_classgroup
CREATE TABLE "courses_classgroup" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "ano_semestre" varchar(20) NOT NULL, "identificador" varchar(50) NOT NULL, "matriz_curricular_id" bigint NOT NULL REFERENCES "courses_curriculummatrix" ("id") DEFERRABLE INITIALLY DEFERRED, "matriz_componente_id" bigint NULL REFERENCES "courses_matrixcomponent" ("id") DEFERRABLE INITIALLY DEFERRED);

-- Table: courses_course
CREATE TABLE "courses_course" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "nome" varchar(255) NOT NULL, "sigla" varchar(20) NOT NULL, "unidade_id" bigint NOT NULL REFERENCES "core_unidade" ("id") DEFERRABLE INITIALLY DEFERRED);

-- Table: courses_curricularcomponent
CREATE TABLE "courses_curricularcomponent" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "nome" varchar(255) NOT NULL, "sigla" varchar(20) NOT NULL, "carga_horaria_padrao" integer unsigned NOT NULL CHECK ("carga_horaria_padrao" >= 0), "codigo" varchar(50) NOT NULL, "creditos" smallint unsigned NOT NULL CHECK ("creditos" >= 0), "ementa" text NOT NULL);

-- Table: courses_curricularcomponent_pre_requisitos
CREATE TABLE "courses_curricularcomponent_pre_requisitos" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "from_curricularcomponent_id" bigint NOT NULL REFERENCES "courses_curricularcomponent" ("id") DEFERRABLE INITIALLY DEFERRED, "to_curricularcomponent_id" bigint NOT NULL REFERENCES "courses_curricularcomponent" ("id") DEFERRABLE INITIALLY DEFERRED);

-- Table: courses_curriculummatrix
CREATE TABLE "courses_curriculummatrix" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "curso_id" bigint NOT NULL REFERENCES "courses_course" ("id") DEFERRABLE INITIALLY DEFERRED, "criada_em" datetime NULL, "is_vigente" bool NOT NULL, "nome" varchar(100) NOT NULL, "periodo_letivo" varchar(20) NULL, "is_rascunho" bool NOT NULL, "turno" varchar(1) NULL);

-- Table: courses_matrixcomponent
CREATE TABLE "courses_matrixcomponent" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "codigo" varchar(50) NOT NULL, "creditos" smallint unsigned NOT NULL CHECK ("creditos" >= 0), "compartilhado" bool NOT NULL, "carga_horaria_semanal" decimal NOT NULL, "distribuicao_semanal" text NOT NULL, "status" varchar(20) NOT NULL, "observacoes" text NOT NULL, "componente_curricular_id" bigint NOT NULL REFERENCES "courses_curricularcomponent" ("id") DEFERRABLE INITIALLY DEFERRED, "curso_compartilhado_id" bigint NULL REFERENCES "courses_course" ("id") DEFERRABLE INITIALLY DEFERRED, "docente_id" bigint NULL REFERENCES "professors_professor" ("id") DEFERRABLE INITIALLY DEFERRED, "matriz_id" bigint NOT NULL REFERENCES "courses_curriculummatrix" ("id") DEFERRABLE INITIALLY DEFERRED, "periodo" varchar(50) NOT NULL, "carga_horaria" integer unsigned NOT NULL CHECK ("carga_horaria" >= 0));

-- Table: courses_matrixcomponent_pre_requisitos
CREATE TABLE "courses_matrixcomponent_pre_requisitos" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "matrixcomponent_id" bigint NOT NULL REFERENCES "courses_matrixcomponent" ("id") DEFERRABLE INITIALLY DEFERRED, "curricularcomponent_id" bigint NOT NULL REFERENCES "courses_curricularcomponent" ("id") DEFERRABLE INITIALLY DEFERRED);

-- Table: django_admin_log
CREATE TABLE "django_admin_log" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "object_id" text NULL, "object_repr" varchar(200) NOT NULL, "action_flag" smallint unsigned NOT NULL CHECK ("action_flag" >= 0), "change_message" text NOT NULL, "content_type_id" integer NULL REFERENCES "django_content_type" ("id") DEFERRABLE INITIALLY DEFERRED, "user_id" bigint NOT NULL REFERENCES "accounts_user" ("id") DEFERRABLE INITIALLY DEFERRED, "action_time" datetime NOT NULL);

-- Table: django_content_type
CREATE TABLE "django_content_type" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "app_label" varchar(100) NOT NULL, "model" varchar(100) NOT NULL);

-- Table: django_migrations
CREATE TABLE "django_migrations" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "app" varchar(255) NOT NULL, "name" varchar(255) NOT NULL, "applied" datetime NOT NULL);

-- Table: django_session
CREATE TABLE "django_session" ("session_key" varchar(40) NOT NULL PRIMARY KEY, "session_data" text NOT NULL, "expire_date" datetime NOT NULL);

-- Table: extra_curricular_atividadeextensionista
CREATE TABLE "extra_curricular_atividadeextensionista" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "num_estudantes" integer unsigned NOT NULL CHECK ("num_estudantes" >= 0), "carga_horaria" decimal NOT NULL, "parecer_desup" varchar(20) NOT NULL, "motivo_parecer" text NOT NULL, "data_atualizacao" datetime NOT NULL, "pendencia_id" bigint NOT NULL REFERENCES "extra_curricular_pendenciaextra" ("id") DEFERRABLE INITIALLY DEFERRED, "horas_aprovadas" decimal NULL);

-- Table: extra_curricular_orientacaotcc
CREATE TABLE "extra_curricular_orientacaotcc" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "num_orientandos" smallint unsigned NOT NULL CHECK ("num_orientandos" >= 0), "carga_horaria" decimal NOT NULL, "parecer_desup" varchar(20) NOT NULL, "motivo_parecer" text NOT NULL, "data_atualizacao" datetime NOT NULL, "pendencia_id" bigint NOT NULL REFERENCES "extra_curricular_pendenciaextra" ("id") DEFERRABLE INITIALLY DEFERRED, "horas_aprovadas" decimal NULL);

-- Table: extra_curricular_pendenciaextra
CREATE TABLE "extra_curricular_pendenciaextra" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "semestre" varchar(10) NOT NULL, "sei_numero" varchar(50) NULL, "status" varchar(20) NOT NULL, "data_criacao" datetime NOT NULL, "data_atualizacao" datetime NOT NULL, "criado_por_id" bigint NULL REFERENCES "accounts_user" ("id") DEFERRABLE INITIALLY DEFERRED, "professor_id" bigint NOT NULL REFERENCES "professors_professor" ("id") DEFERRABLE INITIALLY DEFERRED, "unidade_id" bigint NOT NULL REFERENCES "core_unidade" ("id") DEFERRABLE INITIALLY DEFERRED, "motivo_status_desup" text NOT NULL);

-- Table: extra_curricular_reducaocargahoraria
CREATE TABLE "extra_curricular_reducaocargahoraria" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "motivo_reducao" text NOT NULL, "horas_reduzidas" decimal NOT NULL, "parecer_desup" varchar(20) NOT NULL, "motivo_parecer" text NOT NULL, "data_atualizacao" datetime NOT NULL, "pendencia_id" bigint NOT NULL REFERENCES "extra_curricular_pendenciaextra" ("id") DEFERRABLE INITIALLY DEFERRED, "horas_aprovadas" decimal NULL);

-- Table: professors_absencerecord
CREATE TABLE "professors_absencerecord" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "data_inicio" date NOT NULL, "data_fim" date NOT NULL, "motivo" text NOT NULL, "comprovante" varchar(100) NULL, "professor_id" bigint NOT NULL REFERENCES "professors_professor" ("id") DEFERRABLE INITIALLY DEFERRED);

-- Table: professors_availability
CREATE TABLE "professors_availability" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "dia_semana" integer NOT NULL, "turno" varchar(1) NOT NULL, "professor_id" bigint NOT NULL REFERENCES "professors_professor" ("id") DEFERRABLE INITIALLY DEFERRED);

-- Table: professors_contracttype
CREATE TABLE "professors_contracttype" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "nome" varchar(100) NOT NULL, "regime_trabalho" varchar(20) NOT NULL, "max_class_hours" integer unsigned NOT NULL CHECK ("max_class_hours" >= 0), "max_total_hours" integer unsigned NOT NULL CHECK ("max_total_hours" >= 0), "max_classes" integer unsigned NOT NULL CHECK ("max_classes" >= 0), "categoria" varchar(20) NOT NULL, "dias_presenca_obrigatorios" smallint unsigned NOT NULL CHECK ("dias_presenca_obrigatorios" >= 0));

-- Table: professors_professor
CREATE TABLE "professors_professor" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "status" varchar(20) NOT NULL, "tipo_contrato_id" bigint NOT NULL REFERENCES "professors_contracttype" ("id") DEFERRABLE INITIALLY DEFERRED, "unidade_principal_id" bigint NULL REFERENCES "core_unidade" ("id") DEFERRABLE INITIALLY DEFERRED, "desup_email" varchar(254) NULL, "desup_nome" varchar(255) NULL, "is_cedido" bool NOT NULL, "rh_email" varchar(254) NOT NULL, "rh_matricula" varchar(50) NOT NULL UNIQUE, "rh_nome" varchar(255) NOT NULL, "ha" integer unsigned NOT NULL CHECK ("ha" >= 0), "materia" varchar(20) NOT NULL, "ID_FUNCIONAL" varchar(50) NOT NULL UNIQUE);

-- Table: professors_professor_cursos
CREATE TABLE "professors_professor_cursos" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "professor_id" bigint NOT NULL REFERENCES "professors_professor" ("id") DEFERRABLE INITIALLY DEFERRED, "course_id" bigint NOT NULL REFERENCES "courses_course" ("id") DEFERRABLE INITIALLY DEFERRED);

-- Table: sqlite_sequence
CREATE TABLE sqlite_sequence(name,seq);


-- Data Export
INSERT INTO accounts_passwordresetrequest (id, token, criado_em, finalizado, finalizado_em, aprovado_por_id, user_id) VALUES ('1', '665826ab39464397b00ba69f56c181c9', '2026-06-03 16:58:09.862048', '0', NULL, NULL, '6');
INSERT INTO accounts_user (id, password, last_login, is_superuser, username, first_name, last_name, is_staff, is_active, date_joined, email, perfil, dados_submetidos, unidade_id, forcar_troca_senha) VALUES ('1', 'pbkdf2_sha256$1200000$MxGLBmsjpi4ZvSis9LSe1E$1mI9g27O+RCwWhM6+5RvfT5U58PE0jQszbslF+azC7Q=', '2026-05-27 18:22:59.158592', '0', 'unidadefatec@desup.com', '', '', '0', '1', '2026-05-27 16:53:03.369424', 'unidadefatec@desup.com', 'COORDENADOR_UNIDADE', '0', '1', '0');
INSERT INTO accounts_user (id, password, last_login, is_superuser, username, first_name, last_name, is_staff, is_active, date_joined, email, perfil, dados_submetidos, unidade_id, forcar_troca_senha) VALUES ('3', 'pbkdf2_sha256$1200000$OfT9JKwn7gAf1SFN2xLiyC$GorCILxwRkOcq1JXZKjYHhi1auvffNDFY2WJmw93BSI=', NULL, '0', 'coordenador_paracambi@desup.com', 'Coordenador', 'Paracambi', '0', '1', '2026-06-03 14:57:33.108367', 'coordenador_paracambi@desup.com', 'COORDENADOR_UNIDADE', '0', '2', '0');
INSERT INTO accounts_user (id, password, last_login, is_superuser, username, first_name, last_name, is_staff, is_active, date_joined, email, perfil, dados_submetidos, unidade_id, forcar_troca_senha) VALUES ('5', 'pbkdf2_sha256$1200000$KoqKLDD0YpCLO5C1YrX2iR$dA1ae25Fta2otVrX6ZT+jt8mhwXKQqC+ZHFjTuEbyKQ=', NULL, '1', 'estagio.analista2@desup.faetec.rj.gov.br', 'Analista 2', 'Estágio', '1', '1', '2026-06-03 16:33:51.511244', 'estagio.analista2@desup.faetec.rj.gov.br', 'DESUP', '0', NULL, '0');
INSERT INTO accounts_user (id, password, last_login, is_superuser, username, first_name, last_name, is_staff, is_active, date_joined, email, perfil, dados_submetidos, unidade_id, forcar_troca_senha) VALUES ('6', 'pbkdf2_sha256$1200000$bnReJCxYJ92ZH8wfGeDRnb$sTS974UZEm0hzQLNCbFv5SWNYKEHMeiE/OIEPQ7JAMM=', '2026-06-03 17:03:41.578758', '0', 'academica.coordenacao@desup.faetec.rj.gov.br', 'Coordenação', 'Acadêmica', '1', '1', '2026-06-03 16:33:53.632579', 'academica.coordenacao@desup.faetec.rj.gov.br', 'DESUP', '0', NULL, '0');
INSERT INTO accounts_user (id, password, last_login, is_superuser, username, first_name, last_name, is_staff, is_active, date_joined, email, perfil, dados_submetidos, unidade_id, forcar_troca_senha) VALUES ('7', 'pbkdf2_sha256$1200000$N2w55ebCPGgZ6aUbASl2Wb$qalx+YsmaOp/VYn0U4mDPD9ZcHQ8rtK2Ud3gxb66GWM=', '2026-06-10 14:49:54.272219', '0', 'paracambi.unidade@faeterj-pr.edu.br', 'Coordenador', 'Paracambi', '0', '1', '2026-06-03 16:33:55.470029', 'paracambi.unidade@faeterj-pr.edu.br', 'COORDENADOR_UNIDADE', '0', '2', '0');
INSERT INTO accounts_user (id, password, last_login, is_superuser, username, first_name, last_name, is_staff, is_active, date_joined, email, perfil, dados_submetidos, unidade_id, forcar_troca_senha) VALUES ('8', 'pbkdf2_sha256$1200000$lg9j7W95zZRMpci0cOv75c$yfyWdWFIfc3RPNsiqhH0/lHmZaooMOxdp7IaMphGxEA=', '2026-06-15 14:35:54.956739', '1', 'estagio.analista1@desup.faetec.rj.gov.br', 'Esther', 'Santos', '1', '1', '2026-06-03 16:33:57.510324', 'estagio.analista1@desup.faetec.rj.gov.br', 'DESUP', '0', NULL, '0');
INSERT INTO accounts_user (id, password, last_login, is_superuser, username, first_name, last_name, is_staff, is_active, date_joined, email, perfil, dados_submetidos, unidade_id, forcar_troca_senha) VALUES ('9', 'pbkdf2_sha256$1200000$UjzQboJHtNaPHnzf0XMWcG$bEveUwp2U7EsF47wble9bSzOy99b6oCRflFQt7cQfkk=', '2026-06-15 14:28:02.306786', '0', 'alberto.alvaraes@desup.faetec.rj.gov.br', '', '', '1', '1', '2026-06-03 18:18:25.105167', 'alberto.alvaraes@desup.faetec.rj.gov.br', 'DESUP', '0', NULL, '0');
INSERT INTO accounts_user (id, password, last_login, is_superuser, username, first_name, last_name, is_staff, is_active, date_joined, email, perfil, dados_submetidos, unidade_id, forcar_troca_senha) VALUES ('10', 'pbkdf2_sha256$1200000$9caEh8Lmu77NzQNUrmGJmT$pd53putrI/aqiIX9AiJ7pnX/T+q+Kk2VJtQRGL7Lyao=', NULL, '0', 'direcao@faeterj-dcx.faetec.rj.gov.br', '', '', '0', '1', '2026-06-03 18:19:19', 'direcao@faeterj-dcx.faetec.rj.gov.br', 'COORDENADOR_UNIDADE', '0', '3', '1');
INSERT INTO allocations_alocacaocurricular (id, semestre, turno, status, sei_numero, data_criacao, data_ultimo_ajuste, curso_id, unidade_id) VALUES ('1', '2026.1', 'N', 'Rascunho', NULL, '2026-06-03 14:57:38.238380', '2026-06-15 15:03:07.365706', '2', '2');
INSERT INTO allocations_alocacaocurricular (id, semestre, turno, status, sei_numero, data_criacao, data_ultimo_ajuste, curso_id, unidade_id) VALUES ('2', '2026.1', 'N', 'Rascunho', NULL, '2026-06-03 14:57:38.250953', '2026-06-03 14:57:38.250987', '3', '2');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('1', '1', 'add_logentry', 'Can add log entry');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('2', '1', 'change_logentry', 'Can change log entry');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('3', '1', 'delete_logentry', 'Can delete log entry');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('4', '1', 'view_logentry', 'Can view log entry');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('5', '3', 'add_permission', 'Can add permission');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('6', '3', 'change_permission', 'Can change permission');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('7', '3', 'delete_permission', 'Can delete permission');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('8', '3', 'view_permission', 'Can view permission');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('9', '2', 'add_group', 'Can add group');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('10', '2', 'change_group', 'Can change group');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('11', '2', 'delete_group', 'Can delete group');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('12', '2', 'view_group', 'Can view group');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('13', '4', 'add_contenttype', 'Can add content type');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('14', '4', 'change_contenttype', 'Can change content type');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('15', '4', 'delete_contenttype', 'Can delete content type');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('16', '4', 'view_contenttype', 'Can view content type');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('17', '5', 'add_session', 'Can add session');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('18', '5', 'change_session', 'Can change session');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('19', '5', 'delete_session', 'Can delete session');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('20', '5', 'view_session', 'Can view session');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('21', '6', 'add_user', 'Can add Usuário');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('22', '6', 'change_user', 'Can change Usuário');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('23', '6', 'delete_user', 'Can delete Usuário');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('24', '6', 'view_user', 'Can view Usuário');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('25', '9', 'add_unidade', 'Can add Unidade');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('26', '9', 'change_unidade', 'Can change Unidade');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('27', '9', 'delete_unidade', 'Can delete Unidade');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('28', '9', 'view_unidade', 'Can view Unidade');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('29', '7', 'add_janelaentrega', 'Can add Janela de Entrega');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('30', '7', 'change_janelaentrega', 'Can change Janela de Entrega');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('31', '7', 'delete_janelaentrega', 'Can delete Janela de Entrega');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('32', '7', 'view_janelaentrega', 'Can view Janela de Entrega');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('33', '8', 'add_notificacao', 'Can add Notificação');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('34', '8', 'change_notificacao', 'Can change Notificação');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('35', '8', 'delete_notificacao', 'Can delete Notificação');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('36', '8', 'view_notificacao', 'Can view Notificação');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('37', '10', 'add_alocacaocurricular', 'Can add Alocação Curricular');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('38', '10', 'change_alocacaocurricular', 'Can change Alocação Curricular');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('39', '10', 'delete_alocacaocurricular', 'Can delete Alocação Curricular');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('40', '10', 'view_alocacaocurricular', 'Can view Alocação Curricular');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('41', '13', 'add_curricularcomponent', 'Can add Componente Curricular');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('42', '13', 'change_curricularcomponent', 'Can change Componente Curricular');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('43', '13', 'delete_curricularcomponent', 'Can delete Componente Curricular');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('44', '13', 'view_curricularcomponent', 'Can view Componente Curricular');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('45', '12', 'add_course', 'Can add Curso');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('46', '12', 'change_course', 'Can change Curso');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('47', '12', 'delete_course', 'Can delete Curso');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('48', '12', 'view_course', 'Can view Curso');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('49', '14', 'add_curriculummatrix', 'Can add Matriz Curricular');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('50', '14', 'change_curriculummatrix', 'Can change Matriz Curricular');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('51', '14', 'delete_curriculummatrix', 'Can delete Matriz Curricular');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('52', '14', 'view_curriculummatrix', 'Can view Matriz Curricular');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('53', '11', 'add_classgroup', 'Can add Turma');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('54', '11', 'change_classgroup', 'Can change Turma');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('55', '11', 'delete_classgroup', 'Can delete Turma');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('56', '11', 'view_classgroup', 'Can view Turma');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('57', '15', 'add_matrixcomponent', 'Can add Componente da Matriz');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('58', '15', 'change_matrixcomponent', 'Can change Componente da Matriz');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('59', '15', 'delete_matrixcomponent', 'Can delete Componente da Matriz');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('60', '15', 'view_matrixcomponent', 'Can view Componente da Matriz');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('61', '18', 'add_contracttype', 'Can add Tipo de Contrato');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('62', '18', 'change_contracttype', 'Can change Tipo de Contrato');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('63', '18', 'delete_contracttype', 'Can delete Tipo de Contrato');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('64', '18', 'view_contracttype', 'Can view Tipo de Contrato');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('65', '19', 'add_professor', 'Can add Professor');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('66', '19', 'change_professor', 'Can change Professor');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('67', '19', 'delete_professor', 'Can delete Professor');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('68', '19', 'view_professor', 'Can view Professor');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('69', '16', 'add_absencerecord', 'Can add Registro de Ausência');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('70', '16', 'change_absencerecord', 'Can change Registro de Ausência');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('71', '16', 'delete_absencerecord', 'Can delete Registro de Ausência');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('72', '16', 'view_absencerecord', 'Can view Registro de Ausência');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('73', '17', 'add_availability', 'Can add Disponibilidade');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('74', '17', 'change_availability', 'Can change Disponibilidade');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('75', '17', 'delete_availability', 'Can delete Disponibilidade');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('76', '17', 'view_availability', 'Can view Disponibilidade');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('77', '22', 'add_pendenciaextra', 'Can add Pendência Extracurricular');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('78', '22', 'change_pendenciaextra', 'Can change Pendência Extracurricular');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('79', '22', 'delete_pendenciaextra', 'Can delete Pendência Extracurricular');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('80', '22', 'view_pendenciaextra', 'Can view Pendência Extracurricular');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('81', '21', 'add_orientacaotcc', 'Can add Orientação de TCC');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('82', '21', 'change_orientacaotcc', 'Can change Orientação de TCC');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('83', '21', 'delete_orientacaotcc', 'Can delete Orientação de TCC');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('84', '21', 'view_orientacaotcc', 'Can view Orientação de TCC');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('85', '20', 'add_atividadeextensionista', 'Can add Atividade Extensionista');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('86', '20', 'change_atividadeextensionista', 'Can change Atividade Extensionista');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('87', '20', 'delete_atividadeextensionista', 'Can delete Atividade Extensionista');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('88', '20', 'view_atividadeextensionista', 'Can view Atividade Extensionista');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('89', '23', 'add_reducaocargahoraria', 'Can add Redução de Carga Horária');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('90', '23', 'change_reducaocargahoraria', 'Can change Redução de Carga Horária');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('91', '23', 'delete_reducaocargahoraria', 'Can delete Redução de Carga Horária');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('92', '23', 'view_reducaocargahoraria', 'Can view Redução de Carga Horária');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('93', '24', 'add_passwordresetrequest', 'Can add Solicitacao de Reset');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('94', '24', 'change_passwordresetrequest', 'Can change Solicitacao de Reset');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('95', '24', 'delete_passwordresetrequest', 'Can delete Solicitacao de Reset');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('96', '24', 'view_passwordresetrequest', 'Can view Solicitacao de Reset');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('97', '25', 'add_selfpasswordchangerequest', 'Can add Solicitacao de Troca de Senha');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('98', '25', 'change_selfpasswordchangerequest', 'Can change Solicitacao de Troca de Senha');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('99', '25', 'delete_selfpasswordchangerequest', 'Can delete Solicitacao de Troca de Senha');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('100', '25', 'view_selfpasswordchangerequest', 'Can view Solicitacao de Troca de Senha');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('101', '26', 'add_auditoriaglobal', 'Can add Auditoria Global');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('102', '26', 'change_auditoriaglobal', 'Can change Auditoria Global');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('103', '26', 'delete_auditoriaglobal', 'Can delete Auditoria Global');
INSERT INTO auth_permission (id, content_type_id, codename, name) VALUES ('104', '26', 'view_auditoriaglobal', 'Can view Auditoria Global');
INSERT INTO core_auditoriaglobal (id, email, acao, detalhes, ip, user_agent, criado_em, usuario_id) VALUES ('1', 'paracambi.unidade@faeterj-pr.edu.br', 'PASSWORD_CHANGED_FIRST_LOGIN', 'Senha alterada no fluxo obrigatorio do primeiro acesso.', '10.200.19.229', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36', '2026-06-03 16:37:31.468255', '7');
INSERT INTO core_auditoriaglobal (id, email, acao, detalhes, ip, user_agent, criado_em, usuario_id) VALUES ('2', 'academica.coordenacao@desup.faetec.rj.gov.br', 'PASSWORD_CHANGED_FIRST_LOGIN', 'Senha alterada no fluxo obrigatorio do primeiro acesso.', '10.200.19.229', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36', '2026-06-03 16:40:01.031813', '6');
INSERT INTO core_auditoriaglobal (id, email, acao, detalhes, ip, user_agent, criado_em, usuario_id) VALUES ('3', 'academica.coordenacao@desup.faetec.rj.gov.br', 'PASSWORD_CHANGED_FIRST_LOGIN', 'Senha alterada no fluxo obrigatorio do primeiro acesso.', '10.200.19.240', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36 OPR/131.0.0.0', '2026-06-03 17:02:38.996537', '6');
INSERT INTO core_janelaentrega (id, semestre, data_inicio, data_fim, status, unidade_id) VALUES ('1', '2026.1', '2026-06-10', '2026-06-10', 'Aberto', '2');
INSERT INTO core_notificacao (id, titulo, mensagem, lida, url_acao, data_criacao, destinatario_id, unidade_destino_id) VALUES ('1', 'Chamado - Justificativas', 'O gestor unidadefatec@desup.com solicitou abertura de chamado para criar pendência extracurricular fora da janela de entrega.

Área: Justificativas
Unidade: FAETEC-TESTE - Unidade de Teste
Alvo: pendência extracurricular
Detalhes: /extracurriculares/pendencias/nova/
Solicitante: unidadefatec@desup.com', '0', '/extracurriculares/pendencias/nova/', '2026-05-27 18:25:15.130709', NULL, NULL);
INSERT INTO core_notificacao (id, titulo, mensagem, lida, url_acao, data_criacao, destinatario_id, unidade_destino_id) VALUES ('2', 'Solicitação de Reset de Senha', 'O usuário Coordenação Acadêmica (academica.coordenacao@desup.faetec.rj.gov.br) solicitou a redefinição de senha.', '0', '/accounts/reset/aprovar/665826ab-3946-4397-b00b-a69f56c181c9/', '2026-06-03 16:58:09.892677', '6', NULL);
INSERT INTO core_notificacao (id, titulo, mensagem, lida, url_acao, data_criacao, destinatario_id, unidade_destino_id) VALUES ('4', 'Solicitação de Reset de Senha', 'O usuário Coordenação Acadêmica (academica.coordenacao@desup.faetec.rj.gov.br) solicitou a redefinição de senha.', '0', '/accounts/reset/aprovar/665826ab-3946-4397-b00b-a69f56c181c9/', '2026-06-03 16:58:09.921259', '8', NULL);
INSERT INTO core_notificacao (id, titulo, mensagem, lida, url_acao, data_criacao, destinatario_id, unidade_destino_id) VALUES ('5', 'Solicitação de Reset de Senha', 'O usuário Coordenação Acadêmica (academica.coordenacao@desup.faetec.rj.gov.br) solicitou a redefinição de senha.', '0', '/accounts/reset/aprovar/665826ab-3946-4397-b00b-a69f56c181c9/', '2026-06-03 16:58:09.935439', '5', NULL);
INSERT INTO core_notificacao (id, titulo, mensagem, lida, url_acao, data_criacao, destinatario_id, unidade_destino_id) VALUES ('6', 'Chamado - Justificativas', 'O gestor Coordenador Paracambi solicitou abertura de chamado para criar pendência extracurricular fora da janela de entrega.

Área: Justificativas
Unidade: FAETERJ-PCB - FAETERJ Paracambi
Alvo: pendência extracurricular
Detalhes: /extracurriculares/pendencias/nova/
Solicitante: paracambi.unidade@faeterj-pr.edu.br', '0', '/extracurriculares/pendencias/nova/', '2026-06-10 14:50:48.211728', NULL, NULL);
INSERT INTO core_unidade (id, nome, sigla, status) VALUES ('1', 'Unidade de Teste', 'FAETEC-TESTE', '1');
INSERT INTO core_unidade (id, nome, sigla, status) VALUES ('2', 'FAETERJ Paracambi', 'FAETERJ-PCB', '1');
INSERT INTO core_unidade (id, nome, sigla, status) VALUES ('3', 'FAETERJ DUQUE DE CAXIAS', 'FAETERJ DCX', '1');
INSERT INTO core_unidade (id, nome, sigla, status) VALUES ('4', 'Teste Th', 'Th', '1');
INSERT INTO courses_course (id, nome, sigla, unidade_id) VALUES ('1', 'Técnico em Informática', 'TI', '1');
INSERT INTO courses_course (id, nome, sigla, unidade_id) VALUES ('2', 'Tecnologia em Análise e Desenvolvimento de Sistemas', 'ADS', '2');
INSERT INTO courses_course (id, nome, sigla, unidade_id) VALUES ('3', 'Tecnologia em Gestão Ambiental', 'TGA', '2');
INSERT INTO courses_course (id, nome, sigla, unidade_id) VALUES ('4', 'Tecnologia em Processos Gerenciais', 'PGE', '3');
INSERT INTO courses_course (id, nome, sigla, unidade_id) VALUES ('5', 'Copo da Felicidade de Uva', 'CFU', '4');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('1', 'Algoritmos e Lógica de Programação', 'ALGO', '80', 'ALP001', '4', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('2', 'Fundamentos de Hardware', 'HARD', '60', 'HRD001', '3', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('3', 'Matemática Aplicada', 'MAT', '80', 'MAT001', '4', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('4', 'Programação Orientada a Objetos', 'POO', '80', 'POO001', '4', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('5', 'Sistemas Operacionais', 'SO', '60', 'SO001', '3', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('6', 'Banco de Dados I', 'BD1', '60', 'BD001', '3', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('7', 'Desenvolvimento Web Front-end', 'WEB', '80', 'WEB001', '4', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('8', 'Banco de Dados II', 'BD2', '60', 'BD002', '3', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('9', 'Redes de Computadores', 'REDES', '60', 'RDS001', '3', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('10', 'Projeto Integrador', 'PROJ', '80', 'PRJ001', '4', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('11', 'Segurança da Informação', 'SEG', '60', 'SEG001', '3', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('12', 'Estágio Supervisionado', 'EST', '160', 'EST001', '8', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('13', 'Modelagem Conceitual de Dados', 'BDA-I', '80', 'BDA-I', '4', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('14', 'Arquitetura de Computadores', 'HSO-I', '80', 'HSO-I', '4', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('15', 'Fundamentos de Sistemas de Informação', 'FGE-I', '40', 'FGE-I', '2', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('16', 'Programação Estruturada', 'PRG-I', '80', 'PRG-I', '4', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('17', 'Matemática Discreta', 'FGE-II', '80', 'FGE-II', '4', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('18', 'Ambiente de Edição Web', 'PRG-II', '80', 'PRG-II', '4', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('19', 'Português Instrumental', 'FGE-III', '40', 'FGE-III', '2', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('20', 'Modelo Relacional e Projeto Lógico de Banco de Dados', 'BDA-II', '80', 'BDA-II', '4', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('21', 'Fundamentos de Engenharia de Software', 'ENS-I', '80', 'ENS-I', '4', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('22', 'Modelo e Programação Orientados a Objetos', 'ENS-II', '80', 'ENS-II', '4', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('23', 'Estruturas de Dados', 'PRG-III', '80', 'PRG-III', '4', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('24', 'Sistemas Operacionais e Serviços de Virtualização', 'HSO-II', '80', 'HSO-II', '4', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('25', 'Estatística', 'FGE-IV', '40', 'FGE-IV', '2', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('26', 'Inglês Instrumental', 'FGE-V', '40', 'FGE-V', '2', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('27', 'Desenvolvimento Frontend', 'PRG-IV', '80', 'PRG-IV', '4', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('28', 'Interface Humano-Máquina e UI Design', 'PRG-V', '40', 'PRG-V', '2', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('29', 'Metodologia da Pesquisa', 'FGE-VI', '40', 'FGE-VI', '2', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('30', 'Técnicas de Análise e Projeto de Sistemas', 'ENS-III', '80', 'ENS-III', '4', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('31', 'Redes de Computadores', 'HSO-III', '80', 'HSO-III', '4', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('32', 'Métodos Ágeis', 'ENS-IV', '40', 'ENS-IV', '2', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('33', 'Projeto de Extensão I', 'EXT-I', '48', 'EXT-I', '2', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('34', 'Desenvolvimento Backend', 'PRG-VI', '80', 'PRG-VI', '4', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('35', 'Arquitetura de Software', 'ENS-V', '60', 'ENS-V', '3', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('36', 'Gestão de Processos de Negócios (BPM)', 'GTI-I', '60', 'GTI-I', '3', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('37', 'Padrões de Projeto', 'PRG-VII', '60', 'PRG-VII', '3', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('38', 'Testes de Software', 'ENS-VI', '60', 'ENS-VI', '3', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('39', 'Qualidade de Software', 'ENS-VII', '40', 'ENS-VII', '2', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('40', 'Projeto de Extensão II', 'EXT-II', '96', 'EXT-II', '4', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('41', 'Desenvolvimento Mobile', 'PRG-VIII', '80', 'PRG-VIII', '4', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('42', 'Abordagem DevOps e Entregas Contínuas', 'ENS-VIII', '80', 'ENS-VIII', '4', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('43', 'Empreendedorismo e Computação', 'FGE-VII', '40', 'FGE-VII', '2', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('44', 'Gestão e Governança de TI', 'GTI-II', '80', 'GTI-II', '4', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('45', 'Segurança da Informação', 'GTI-III', '80', 'GTI-III', '4', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('46', 'Gestão de Projetos', 'GTI-IV', '80', 'GTI-IV', '4', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('47', 'Direito e Legislação de Informática', 'FGE-VIII', '40', 'FGE-VIII', '2', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('48', 'Projeto de Extensão III', 'EXT-III', '96', 'EXT-III', '4', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('49', 'Química Geral', 'QUG', '40', 'QUG', '2', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('50', 'Noções de Direito', 'NOD', '40', 'NOD', '2', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('51', 'Língua Portuguesa', 'POR', '40', 'POR', '2', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('52', 'Segurança do Trabalho e Meio Ambiente', 'STM', '40', 'STM', '2', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('53', 'Ética', 'ETI', '40', 'ETI', '2', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('54', 'Educação Ambiental e Sustentabilidade', 'EDU', '60', 'EDU', '3', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('55', 'Geometria Aplicada ao Meio Ambiente', 'GAM', '60', 'GAM', '3', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('56', 'Energia e Sustentabilidade', 'ENS', '60', 'ENS-TGA', '3', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('57', 'Metodologia da Pesquisa Científica', 'MPC', '40', 'MPC', '2', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('58', 'Estatística Aplicada', 'EAP', '40', 'EAP', '2', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('59', 'Economia dos Recursos Naturais e Ambiente', 'MER', '60', 'MER', '3', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('60', 'Química Inorgânica', 'QIN', '40', 'QIN', '2', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('61', 'Biologia e Biotecnologia Aplicada', 'BBT', '60', 'BBT', '3', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('62', 'Botânica Geral', 'BOT', '40', 'BOT', '2', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('63', 'Geociência Ambiental', 'GEO', '40', 'GEO', '2', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('64', 'Zoologia Geral', 'ZGE', '60', 'ZGE', '3', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('65', 'Ecologia', 'ELA', '60', 'ELA', '3', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('66', 'Política e Legislação Ambiental', 'POL', '60', 'POL', '3', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('67', 'Extensão 1', 'EXT1', '40', 'EXT1-TGA', '2', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('68', 'Administração e Gerenciamento de Projetos', 'AGP', '60', 'AGP', '3', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('69', 'Gerenciamento de Resíduos', 'RES', '60', 'RES', '3', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('70', 'Gestão pela Qualidade de Equipes', 'GES', '40', 'GES', '2', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('71', 'Georreferenciamento', 'GRR', '60', 'GRR', '3', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('72', 'Química Analítica', 'QAN', '60', 'QAN', '3', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('73', 'Microbiologia Ambiental', 'MIC', '40', 'MIC', '2', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('74', 'Química Orgânica Ambiental', 'QOR', '40', 'QOR', '2', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('75', 'Limnologia', 'LAG', '40', 'LAG', '2', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('76', 'Controle Poluição da Água', 'CON', '60', 'CON', '3', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('77', 'Projeto de Extensão 2', 'EXT2', '80', 'EXT2-TGA', '4', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('78', 'Recuperação de Áreas Degradadas', 'REC', '60', 'REC', '3', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('79', 'Controle da Poluição Atmosférica', 'CAR', '60', 'CAR', '3', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('80', 'Manejo e Gerenciamento de Bacias Hidrográficas', 'MGB', '60', 'MGB', '3', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('81', 'Controle da Poluição do Solo', 'CSO', '60', 'CSO', '3', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('82', 'Saúde Pública e a Questão Ambiental', 'SPQ', '60', 'SPQ', '3', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('83', 'Licenciamento, Certificação e Auditoria Ambiental', 'LCA', '100', 'LCA', '5', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('84', 'Gestão de Unidades de Conservação', 'GUC', '40', 'GUC', '2', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('85', 'Projeto de Extensão 3', 'EXT3', '80', 'EXT3-TGA', '4', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('86', 'Introdução à Administração', 'INTRODUÇÃO À ADMINIS', '60', '', '3', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('87', 'Introdução à Economia', 'INTRODUÇÃO À ECONOMI', '60', '', '3', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('88', 'Contabilidade Gerencial', 'CONTABILIDADE GERENC', '60', '', '3', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('89', 'Gestão de Processos Organizacionais', 'GESTÃO DE PROCESSOS ', '60', '', '3', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('90', 'Gestão de Marketing', 'GESTÃO DE MARKETING', '60', '', '3', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('91', 'Matemática Aplicada à Administração', 'MATEMÁTICA APLICADA ', '60', '', '3', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('92', 'Planejamento e Gestão Estratégica', 'PLANEJAMENTO E GESTÃ', '60', '', '3', '');
INSERT INTO courses_curricularcomponent (id, nome, sigla, carga_horaria_padrao, codigo, creditos, ementa) VALUES ('93', 'Sistema de Informações Gerenciais', 'SISTEMA DE INFORMAÇÕ', '60', '', '3', '');
INSERT INTO courses_curriculummatrix (id, curso_id, criada_em, is_vigente, nome, periodo_letivo, is_rascunho, turno) VALUES ('1', '1', '2026-05-27 16:54:28.349356', '1', 'Matriz 2026.1', '2026.1', '0', 'M');
INSERT INTO courses_curriculummatrix (id, curso_id, criada_em, is_vigente, nome, periodo_letivo, is_rascunho, turno) VALUES ('2', '2', '2026-06-03 14:57:35.939217', '1', 'Matriz ADS 2023', '2026.1', '0', 'N');
INSERT INTO courses_curriculummatrix (id, curso_id, criada_em, is_vigente, nome, periodo_letivo, is_rascunho, turno) VALUES ('3', '3', '2026-06-03 14:57:36.880398', '1', 'Matriz TGA 2023', '2026.1', '0', 'N');
INSERT INTO courses_curriculummatrix (id, curso_id, criada_em, is_vigente, nome, periodo_letivo, is_rascunho, turno) VALUES ('4', '4', '2026-06-03 17:30:34.377556', '1', '', '', '0', '');
INSERT INTO courses_curriculummatrix (id, curso_id, criada_em, is_vigente, nome, periodo_letivo, is_rascunho, turno) VALUES ('5', '5', '2026-06-15 14:36:44.885684', '0', 'TH-CFU-2026', NULL, '1', NULL);
INSERT INTO courses_curriculummatrix (id, curso_id, criada_em, is_vigente, nome, periodo_letivo, is_rascunho, turno) VALUES ('6', '5', '2026-06-15 14:40:53.955109', '1', 'Copo da Felicidade de Uva', NULL, '0', NULL);
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('1', 'ALP001', '4', '0', '4', '', 'COMPLETO', '', '1', NULL, '1', '1', '1° Período', '80');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('2', 'HRD001', '3', '0', '3', '', 'COMPLETO', '', '2', NULL, '2', '1', '1° Período', '60');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('3', 'MAT001', '4', '0', '4', '', 'COMPLETO', '', '3', NULL, '3', '1', '1° Período', '80');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('4', 'POO001', '4', '0', '4', '', 'COMPLETO', '', '4', NULL, '4', '1', '2° Período', '80');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('5', 'SO001', '3', '0', '3', '', 'COMPLETO', '', '5', NULL, '5', '1', '2° Período', '60');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('6', 'BD001', '3', '0', '3', '', 'COMPLETO', '', '6', NULL, '1', '1', '2° Período', '60');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('7', 'WEB001', '4', '0', '4', '', 'COMPLETO', '', '7', NULL, '2', '1', '3° Período', '80');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('8', 'BD002', '3', '0', '3', '', 'COMPLETO', '', '8', NULL, '3', '1', '3° Período', '60');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('9', 'RDS001', '3', '0', '3', '', 'COMPLETO', '', '9', NULL, '4', '1', '3° Período', '60');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('10', 'PRJ001', '4', '0', '4', '', 'COMPLETO', '', '10', NULL, '5', '1', '4° Período', '80');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('11', 'SEG001', '3', '0', '3', '', 'COMPLETO', '', '11', NULL, '1', '1', '4° Período', '60');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('12', 'EST001', '8', '0', '8', '', 'COMPLETO', '', '12', NULL, '2', '1', '4° Período', '160');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('13', 'BDA-I', '4', '0', '0', '', 'COMPLETO', '', '13', NULL, '19', '2', '1º Período', '80');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('14', 'HSO-I', '4', '0', '0', '', 'COMPLETO', '', '14', NULL, '7', '2', '1º Período', '80');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('15', 'FGE-I', '2', '0', '0', '', 'COMPLETO', '', '15', NULL, '10', '2', '1º Período', '40');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('16', 'PRG-I', '4', '0', '0', '', 'COMPLETO', '', '16', NULL, '29', '2', '1º Período', '80');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('17', 'FGE-II', '4', '0', '0', '', 'COMPLETO', '', '17', NULL, '18', '2', '1º Período', '80');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('18', 'PRG-II', '4', '0', '0', '', 'COMPLETO', '', '18', NULL, '6', '2', '1º Período', '80');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('19', 'FGE-III', '2', '0', '0', '', 'COMPLETO', '', '19', NULL, '24', '2', '1º Período', '40');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('20', 'BDA-II', '4', '0', '0', '', 'COMPLETO', '', '20', NULL, '19', '2', '2º Período', '80');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('21', 'ENS-I', '4', '0', '0', '', 'COMPLETO', '', '21', NULL, '10', '2', '2º Período', '80');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('22', 'ENS-II', '4', '0', '0', '', 'COMPLETO', '', '22', NULL, '24', '2', '2º Período', '80');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('23', 'PRG-III', '4', '0', '0', '', 'COMPLETO', '', '23', NULL, '7', '2', '2º Período', '80');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('24', 'HSO-II', '4', '0', '0', '', 'COMPLETO', '', '24', NULL, '29', '2', '2º Período', '80');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('25', 'FGE-IV', '2', '0', '0', '', 'COMPLETO', '', '25', NULL, '6', '2', '2º Período', '40');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('26', 'FGE-V', '2', '0', '0', '', 'COMPLETO', '', '26', NULL, '18', '2', '2º Período', '40');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('27', 'PRG-IV', '4', '0', '0', '', 'SEM_PROFESSOR', '', '27', NULL, NULL, '2', '3º Período', '80');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('28', 'PRG-V', '2', '0', '0', '', 'SEM_PROFESSOR', '', '28', NULL, NULL, '2', '3º Período', '40');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('29', 'FGE-VI', '2', '0', '0', '', 'SEM_PROFESSOR', '', '29', NULL, NULL, '2', '3º Período', '40');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('30', 'ENS-III', '4', '0', '0', '', 'COMPLETO', '', '30', NULL, '15', '2', '3º Período', '80');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('31', 'HSO-III', '4', '0', '0', '', 'SEM_PROFESSOR', '', '31', NULL, NULL, '2', '3º Período', '80');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('32', 'ENS-IV', '2', '0', '0', '', 'SEM_PROFESSOR', '', '32', NULL, NULL, '2', '3º Período', '40');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('33', 'EXT-I', '2', '0', '0', '', 'SEM_PROFESSOR', '', '33', NULL, NULL, '2', '3º Período', '48');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('34', 'PRG-VI', '4', '0', '0', '', 'SEM_PROFESSOR', '', '34', NULL, NULL, '2', '4º Período', '80');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('35', 'ENS-V', '3', '0', '0', '', 'SEM_PROFESSOR', '', '35', NULL, NULL, '2', '4º Período', '60');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('36', 'GTI-I', '3', '0', '0', '', 'SEM_PROFESSOR', '', '36', NULL, NULL, '2', '4º Período', '60');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('37', 'PRG-VII', '3', '0', '0', '', 'SEM_PROFESSOR', '', '37', NULL, NULL, '2', '4º Período', '60');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('38', 'ENS-VI', '3', '0', '0', '', 'SEM_PROFESSOR', '', '38', NULL, NULL, '2', '4º Período', '60');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('39', 'ENS-VII', '2', '0', '0', '', 'SEM_PROFESSOR', '', '39', NULL, NULL, '2', '4º Período', '40');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('40', 'EXT-II', '4', '0', '0', '', 'SEM_PROFESSOR', '', '40', NULL, NULL, '2', '4º Período', '96');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('41', 'PRG-VIII', '4', '0', '0', '', 'SEM_PROFESSOR', '', '41', NULL, NULL, '2', '5º Período', '80');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('42', 'ENS-VIII', '4', '0', '0', '', 'SEM_PROFESSOR', '', '42', NULL, NULL, '2', '5º Período', '80');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('43', 'FGE-VII', '2', '0', '0', '', 'SEM_PROFESSOR', '', '43', NULL, NULL, '2', '5º Período', '40');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('44', 'GTI-II', '4', '0', '0', '', 'SEM_PROFESSOR', '', '44', NULL, NULL, '2', '5º Período', '80');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('45', 'GTI-III', '4', '0', '0', '', 'SEM_PROFESSOR', '', '45', NULL, NULL, '2', '5º Período', '80');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('46', 'GTI-IV', '4', '0', '0', '', 'SEM_PROFESSOR', '', '46', NULL, NULL, '2', '5º Período', '80');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('47', 'FGE-VIII', '2', '0', '0', '', 'SEM_PROFESSOR', '', '47', NULL, NULL, '2', '5º Período', '40');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('48', 'EXT-III', '4', '0', '0', '', 'SEM_PROFESSOR', '', '48', NULL, NULL, '2', '5º Período', '96');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('49', 'QUG', '2', '0', '0', '', 'COMPLETO', '', '49', NULL, '37', '3', '1º Período', '40');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('50', 'NOD', '2', '0', '0', '', 'COMPLETO', '', '50', NULL, '35', '3', '1º Período', '40');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('51', 'POR', '2', '0', '0', '', 'COMPLETO', '', '51', NULL, '33', '3', '1º Período', '40');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('52', 'STM', '2', '0', '0', '', 'COMPLETO', '', '52', NULL, '12', '3', '1º Período', '40');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('53', 'ETI', '2', '0', '0', '', 'COMPLETO', '', '53', NULL, '17', '3', '1º Período', '40');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('54', 'EDU', '3', '0', '0', '', 'COMPLETO', '', '54', NULL, '8', '3', '1º Período', '60');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('55', 'GAM', '3', '0', '0', '', 'COMPLETO', '', '55', NULL, '30', '3', '1º Período', '60');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('56', 'ENS-TGA', '3', '0', '0', '', 'COMPLETO', '', '56', NULL, '27', '3', '1º Período', '60');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('57', 'MPC', '2', '0', '0', '', 'COMPLETO', '', '57', NULL, '34', '3', '1º Período', '40');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('58', 'EAP', '2', '0', '0', '', 'SEM_PROFESSOR', '', '58', NULL, NULL, '3', '2º Período', '40');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('59', 'MER', '3', '0', '0', '', 'SEM_PROFESSOR', '', '59', NULL, NULL, '3', '2º Período', '60');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('60', 'QIN', '2', '0', '0', '', 'SEM_PROFESSOR', '', '60', NULL, NULL, '3', '2º Período', '40');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('61', 'BBT', '3', '0', '0', '', 'SEM_PROFESSOR', '', '61', NULL, NULL, '3', '2º Período', '60');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('62', 'BOT', '2', '0', '0', '', 'SEM_PROFESSOR', '', '62', NULL, NULL, '3', '2º Período', '40');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('63', 'GEO', '2', '0', '0', '', 'SEM_PROFESSOR', '', '63', NULL, NULL, '3', '2º Período', '40');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('64', 'ZGE', '3', '0', '0', '', 'SEM_PROFESSOR', '', '64', NULL, NULL, '3', '2º Período', '60');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('65', 'ELA', '3', '0', '0', '', 'SEM_PROFESSOR', '', '65', NULL, NULL, '3', '2º Período', '60');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('66', 'POL', '3', '0', '0', '', 'SEM_PROFESSOR', '', '66', NULL, NULL, '3', '2º Período', '60');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('67', 'EXT1-TGA', '2', '0', '0', '', 'SEM_PROFESSOR', '', '67', NULL, NULL, '3', '2º Período', '40');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('68', 'AGP', '3', '0', '0', '', 'SEM_PROFESSOR', '', '68', NULL, NULL, '3', '3º Período', '60');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('69', 'RES', '3', '0', '0', '', 'SEM_PROFESSOR', '', '69', NULL, NULL, '3', '3º Período', '60');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('70', 'GES', '2', '0', '0', '', 'SEM_PROFESSOR', '', '70', NULL, NULL, '3', '3º Período', '40');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('71', 'GRR', '3', '0', '0', '', 'SEM_PROFESSOR', '', '71', NULL, NULL, '3', '3º Período', '60');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('72', 'QAN', '3', '0', '0', '', 'SEM_PROFESSOR', '', '72', NULL, NULL, '3', '3º Período', '60');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('73', 'MIC', '2', '0', '0', '', 'SEM_PROFESSOR', '', '73', NULL, NULL, '3', '3º Período', '40');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('74', 'QOR', '2', '0', '0', '', 'SEM_PROFESSOR', '', '74', NULL, NULL, '3', '3º Período', '40');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('75', 'LAG', '2', '0', '0', '', 'SEM_PROFESSOR', '', '75', NULL, NULL, '3', '3º Período', '40');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('76', 'CON', '3', '0', '0', '', 'SEM_PROFESSOR', '', '76', NULL, NULL, '3', '3º Período', '60');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('77', 'EXT2-TGA', '4', '0', '0', '', 'SEM_PROFESSOR', '', '77', NULL, NULL, '3', '3º Período', '80');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('78', 'REC', '3', '0', '0', '', 'SEM_PROFESSOR', '', '78', NULL, NULL, '3', '4º Período', '60');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('79', 'CAR', '3', '0', '0', '', 'SEM_PROFESSOR', '', '79', NULL, NULL, '3', '4º Período', '60');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('80', 'MGB', '3', '0', '0', '', 'SEM_PROFESSOR', '', '80', NULL, NULL, '3', '4º Período', '60');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('81', 'CSO', '3', '0', '0', '', 'SEM_PROFESSOR', '', '81', NULL, NULL, '3', '4º Período', '60');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('82', 'SPQ', '3', '0', '0', '', 'SEM_PROFESSOR', '', '82', NULL, NULL, '3', '4º Período', '60');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('83', 'LCA', '5', '0', '0', '', 'SEM_PROFESSOR', '', '83', NULL, NULL, '3', '4º Período', '100');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('84', 'GUC', '2', '0', '0', '', 'SEM_PROFESSOR', '', '84', NULL, NULL, '3', '4º Período', '40');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('85', 'EXT3-TGA', '4', '0', '0', '', 'SEM_PROFESSOR', '', '85', NULL, NULL, '3', '4º Período', '80');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('86', '2024101', '3', '0', '3', '', 'SEM_PROFESSOR', '', '86', NULL, NULL, '4', '1º Semestre', '60');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('87', '2024102', '3', '0', '3', '', 'SEM_PROFESSOR', '', '87', NULL, NULL, '4', '1º Semestre', '60');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('88', '2024103', '3', '0', '3', '', 'SEM_PROFESSOR', '', '88', NULL, NULL, '4', '1º Semestre', '60');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('89', '2024104', '3', '0', '3', '', 'SEM_PROFESSOR', '', '89', NULL, NULL, '4', '1º Semestre', '60');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('90', '2024105', '3', '0', '3', '', 'SEM_PROFESSOR', '', '90', NULL, NULL, '4', '1º Semestre', '60');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('91', '2024106', '3', '0', '3', '', 'SEM_PROFESSOR', '', '91', NULL, NULL, '4', '1º Semestre', '60');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('92', '2024107', '3', '0', '3', '', 'SEM_PROFESSOR', '', '19', NULL, NULL, '4', '1º Semestre', '60');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('93', '2024108', '3', '0', '3', '', 'SEM_PROFESSOR', '', '57', NULL, NULL, '4', '1º Semestre', '60');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('94', '2024209', '3', '0', '3', '', 'SEM_PROFESSOR', '', '92', NULL, NULL, '4', '2º Semestre', '60');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('95', '2024210', '3', '0', '3', '', 'SEM_PROFESSOR', '', '93', NULL, NULL, '4', '2º Semestre', '60');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('96', 'PRG-II', '2', '0', '2', '', 'SEM_PROFESSOR', '', '18', NULL, NULL, '5', '', '40');
INSERT INTO courses_matrixcomponent (id, codigo, creditos, compartilhado, carga_horaria_semanal, distribuicao_semanal, status, observacoes, componente_curricular_id, curso_compartilhado_id, docente_id, matriz_id, periodo, carga_horaria) VALUES ('97', 'PRG-II', '2', '0', '2', '', 'SEM_PROFESSOR', '', '18', NULL, NULL, '6', '', '40');
INSERT INTO django_admin_log (id, object_id, object_repr, action_flag, change_message, content_type_id, user_id, action_time) VALUES ('1', '4', 'estagio.analista@desup.faetec.rj.gov.br (DESUP)', '3', '', '6', '8', '2026-06-03 16:46:42.654731');
INSERT INTO django_admin_log (id, object_id, object_repr, action_flag, change_message, content_type_id, user_id, action_time) VALUES ('2', '9', 'alberto.alvaraes@desup.faetec.rj.gov.br (DESUP)', '1', '[{"added": {}}]', '6', '8', '2026-06-03 18:18:27.131867');
INSERT INTO django_admin_log (id, object_id, object_repr, action_flag, change_message, content_type_id, user_id, action_time) VALUES ('3', '10', 'direcao@faeterj-dcx.faetec.rj.gov.br (Coordenador de Unidade)', '1', '[{"added": {}}]', '6', '8', '2026-06-03 18:19:20.920897');
INSERT INTO django_admin_log (id, object_id, object_repr, action_flag, change_message, content_type_id, user_id, action_time) VALUES ('4', '10', 'direcao@faeterj-dcx.faetec.rj.gov.br (Coordenador de Unidade)', '2', '[]', '6', '8', '2026-06-03 18:19:25.305197');
INSERT INTO django_admin_log (id, object_id, object_repr, action_flag, change_message, content_type_id, user_id, action_time) VALUES ('5', '2', 'coordenadordesup@desup.com (DESUP)', '3', '', '6', '8', '2026-06-03 18:19:57.755985');
INSERT INTO django_admin_log (id, object_id, object_repr, action_flag, change_message, content_type_id, user_id, action_time) VALUES ('6', '1', 'ADS - Noite (2026.1)', '2', '[]', '10', '8', '2026-06-15 15:03:07.377835');
INSERT INTO django_content_type (id, app_label, model) VALUES ('1', 'admin', 'logentry');
INSERT INTO django_content_type (id, app_label, model) VALUES ('2', 'auth', 'group');
INSERT INTO django_content_type (id, app_label, model) VALUES ('3', 'auth', 'permission');
INSERT INTO django_content_type (id, app_label, model) VALUES ('4', 'contenttypes', 'contenttype');
INSERT INTO django_content_type (id, app_label, model) VALUES ('5', 'sessions', 'session');
INSERT INTO django_content_type (id, app_label, model) VALUES ('6', 'accounts', 'user');
INSERT INTO django_content_type (id, app_label, model) VALUES ('7', 'core', 'janelaentrega');
INSERT INTO django_content_type (id, app_label, model) VALUES ('8', 'core', 'notificacao');
INSERT INTO django_content_type (id, app_label, model) VALUES ('9', 'core', 'unidade');
INSERT INTO django_content_type (id, app_label, model) VALUES ('10', 'allocations', 'alocacaocurricular');
INSERT INTO django_content_type (id, app_label, model) VALUES ('11', 'courses', 'classgroup');
INSERT INTO django_content_type (id, app_label, model) VALUES ('12', 'courses', 'course');
INSERT INTO django_content_type (id, app_label, model) VALUES ('13', 'courses', 'curricularcomponent');
INSERT INTO django_content_type (id, app_label, model) VALUES ('14', 'courses', 'curriculummatrix');
INSERT INTO django_content_type (id, app_label, model) VALUES ('15', 'courses', 'matrixcomponent');
INSERT INTO django_content_type (id, app_label, model) VALUES ('16', 'professors', 'absencerecord');
INSERT INTO django_content_type (id, app_label, model) VALUES ('17', 'professors', 'availability');
INSERT INTO django_content_type (id, app_label, model) VALUES ('18', 'professors', 'contracttype');
INSERT INTO django_content_type (id, app_label, model) VALUES ('19', 'professors', 'professor');
INSERT INTO django_content_type (id, app_label, model) VALUES ('20', 'extra_curricular', 'atividadeextensionista');
INSERT INTO django_content_type (id, app_label, model) VALUES ('21', 'extra_curricular', 'orientacaotcc');
INSERT INTO django_content_type (id, app_label, model) VALUES ('22', 'extra_curricular', 'pendenciaextra');
INSERT INTO django_content_type (id, app_label, model) VALUES ('23', 'extra_curricular', 'reducaocargahoraria');
INSERT INTO django_content_type (id, app_label, model) VALUES ('24', 'accounts', 'passwordresetrequest');
INSERT INTO django_content_type (id, app_label, model) VALUES ('25', 'accounts', 'selfpasswordchangerequest');
INSERT INTO django_content_type (id, app_label, model) VALUES ('26', 'core', 'auditoriaglobal');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('1', 'core', '0001_initial', '2026-05-27 16:48:47.422569');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('2', 'contenttypes', '0001_initial', '2026-05-27 16:48:47.441856');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('3', 'contenttypes', '0002_remove_content_type_name', '2026-05-27 16:48:47.463019');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('4', 'auth', '0001_initial', '2026-05-27 16:48:47.502780');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('5', 'auth', '0002_alter_permission_name_max_length', '2026-05-27 16:48:47.522968');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('6', 'auth', '0003_alter_user_email_max_length', '2026-05-27 16:48:47.547791');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('7', 'auth', '0004_alter_user_username_opts', '2026-05-27 16:48:47.565263');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('8', 'auth', '0005_alter_user_last_login_null', '2026-05-27 16:48:47.581894');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('9', 'auth', '0006_require_contenttypes_0002', '2026-05-27 16:48:47.594453');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('10', 'auth', '0007_alter_validators_add_error_messages', '2026-05-27 16:48:47.611718');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('11', 'auth', '0008_alter_user_username_max_length', '2026-05-27 16:48:47.630805');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('12', 'auth', '0009_alter_user_last_name_max_length', '2026-05-27 16:48:47.652764');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('13', 'auth', '0010_alter_group_name_max_length', '2026-05-27 16:48:47.677091');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('14', 'auth', '0011_update_proxy_permissions', '2026-05-27 16:48:47.695175');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('15', 'auth', '0012_alter_user_first_name_max_length', '2026-05-27 16:48:47.712619');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('16', 'accounts', '0001_initial', '2026-05-27 16:48:47.749514');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('17', 'accounts', '0002_alter_user_perfil', '2026-05-27 16:48:47.815314');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('18', 'accounts', '0003_alter_user_perfil', '2026-05-27 16:48:47.879395');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('19', 'admin', '0001_initial', '2026-05-27 16:48:47.933964');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('20', 'admin', '0002_logentry_remove_auto_add', '2026-05-27 16:48:47.964602');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('21', 'admin', '0003_logentry_add_action_flag_choices', '2026-05-27 16:48:47.983718');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('22', 'courses', '0001_initial', '2026-05-27 16:48:48.045949');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('23', 'core', '0002_janelaentrega', '2026-05-27 16:48:48.089082');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('24', 'allocations', '0001_initial', '2026-05-27 16:48:48.128298');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('25', 'allocations', '0002_alocacaocurricular_data_prazo_sei', '2026-05-27 16:48:48.150482');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('26', 'allocations', '0003_update_sei_and_matrix_deadline_rules', '2026-05-27 16:48:48.186154');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('27', 'allocations', '0004_alter_alocacaocurricular_sei_numero', '2026-05-27 16:48:48.215139');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('28', 'core', '0003_notificacao', '2026-05-27 16:48:48.345307');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('29', 'professors', '0001_initial', '2026-05-27 16:48:48.536511');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('30', 'professors', '0002_alter_professor_options_remove_professor_email_and_more', '2026-05-27 16:48:48.815954');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('31', 'courses', '0002_sync_curricular_component_schema', '2026-05-27 16:48:48.867496');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('32', 'courses', '0003_matrix_multiple_components', '2026-05-27 16:48:49.159887');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('33', 'courses', '0004_ha_hr_periodo_choices', '2026-05-27 16:48:49.304555');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('34', 'courses', '0005_split_periodo_add_horas_relogio', '2026-05-27 16:48:49.567930');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('35', 'courses', '0006_alter_matrixcomponent_options_and_more', '2026-05-27 16:48:49.953859');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('36', 'courses', '0007_alter_curriculummatrix_options_and_more', '2026-05-27 16:48:50.061267');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('37', 'courses', '0008_curriculummatrix_criada_em_and_more', '2026-05-27 16:48:50.118083');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('38', 'courses', '0009_curriculummatrix_periodo_letivo_and_more', '2026-05-27 16:48:50.155716');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('39', 'professors', '0003_professor_cursos_professor_ha', '2026-05-27 16:48:50.213758');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('40', 'professors', '0004_professor_eixo', '2026-05-27 16:48:50.246279');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('41', 'professors', '0005_alter_professor_eixo', '2026-05-27 16:48:50.278080');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('42', 'extra_curricular', '0001_initial', '2026-05-27 16:48:50.438077');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('43', 'extra_curricular', '0002_pendenciaextra_motivo_status_desup', '2026-05-27 16:48:50.494621');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('44', 'professors', '0006_contracttype_categoria_dias_presenca', '2026-05-27 16:48:50.534362');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('45', 'professors', '0007_alter_professor_rh_matricula', '2026-05-27 16:48:50.575823');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('46', 'professors', '0008_remove_professor_eixo_professor_materia', '2026-05-27 16:48:50.658385');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('47', 'professors', '0009_professor_id_funcional', '2026-05-27 16:48:50.770533');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('48', 'sessions', '0001_initial', '2026-05-27 16:48:50.793539');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('49', 'accounts', '0004_user_forcar_troca_senha', '2026-05-27 16:56:03.182407');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('50', 'accounts', '0005_remove_user_cpf_user_telefone', '2026-06-03 15:11:31.140104');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('51', 'accounts', '0006_passwordresetrequest', '2026-06-03 15:11:31.196075');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('52', 'accounts', '0007_alter_passwordresetrequest_options_and_more', '2026-06-03 15:11:31.318490');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('53', 'accounts', '0008_alter_passwordresetrequest_aprovado_por_and_more', '2026-06-03 15:11:31.476023');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('54', 'core', '0004_auditoriaglobal', '2026-06-03 15:11:31.524324');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('55', 'core', '0005_alter_auditoriaglobal_usuario_and_more', '2026-06-03 15:11:31.593151');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('56', 'extra_curricular', '0003_alter_pendenciaextra_status', '2026-06-03 15:11:31.628403');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('57', 'extra_curricular', '0004_alter_pendenciaextra_criado_por', '2026-06-03 15:11:31.670384');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('58', 'professors', '0010_alter_professor_materia', '2026-06-03 15:11:31.696506');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('59', 'accounts', '0009_alter_user_groups_alter_user_user_permissions', '2026-06-11 12:58:08.324375');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('60', 'courses', '0010_curriculummatrix_is_rascunho_and_more', '2026-06-11 12:58:08.413506');
INSERT INTO django_migrations (id, app, name, applied) VALUES ('61', 'extra_curricular', '0005_atividadeextensionista_horas_aprovadas_and_more', '2026-06-11 13:34:48.816376');
INSERT INTO django_session (session_key, session_data, expire_date) VALUES ('y0p3hc9xfv9ym25qhpwzxeasfticlpur', '.eJxVjLsOwjAMAP_FM4pKyMPpyM43RHZskQJKpaadEP-OKnWA9e50b8i0rTVvXZc8CYyAcPplTOWpbRfyoHafTZnbukxs9sQctpvbLPq6Hu3foFKvMIIlHJgTYkC2FqVIpOAppBR90eI4KMqFbQjeqydbBktJXFSMDtPZwecL51s3mQ:1wUohx:d60D_p2DG7xAGXBnvWVK5Pz2rLtuzDzQnqayqNXJJy8', '2026-06-17 16:44:45.397834');
INSERT INTO django_session (session_key, session_data, expire_date) VALUES ('29wji8clj0vzqast0j1ts6b9tyi6u50i', '.eJxVjLsOwjAMAP_FM4pKyMPpyM43RHZskQJKpaadEP-OKnWA9e50b8i0rTVvXZc8CYyAcPplTOWpbRfyoHafTZnbukxs9sQctpvbLPq6Hu3foFKvMIIlHJgTYkC2FqVIpOAppBR90eI4KMqFbQjeqydbBktJXFSMDtPZwecL51s3mQ:1wUq7X:QJGfwaU86T_kdfYE-K6qClFEhtv6ynE4gp4-tqZGDXg', '2026-06-17 18:15:15.765777');
INSERT INTO django_session (session_key, session_data, expire_date) VALUES ('gy1vy74qlbwx3ia5oepysu7i6oytlfu3', '.eJxVjLsOwjAMAP_FM4ryoE7Skb3fUDm1TQqolfqYEP-OKnWA9e50b-hp32q_r7L0I0MLES6_rNDwlOkQ_KDpPpthnrZlLOZIzGlX080sr9vZ_g0qrRVawJSdE5ag1iYfsiarnIIgF0bvroqeVBvSiDEgu0SKWrzlhrOQZPh8AekNOIA:1wXKFe:B1sSwflRaT04uR3-fUqk-eQvmVBb6luN9aRDSdwkvc8', '2026-06-24 14:49:54.285209');
INSERT INTO django_session (session_key, session_data, expire_date) VALUES ('sn8c4o7caz0tmfcke6omuh2kuh7oaaey', '.eJxVjEEOwiAQAP-yZ0MAAaFH776BLOwiVQNJaU_Gv5smPeh1ZjJviLitNW6DlzgTTBDg9MsS5ie3XdAD272L3Nu6zEnsiTjsELdO_Loe7d-g4qgwgURjlFPWczJnDMq74ixSKFyKVRdmdIQJdTHKeDLZa8nZFSLptU9Kw-cL8G04Zw:1wZ8IE:7UMPYQUX-RwJOFlrw6hd6On70Uq4kAB-davJezWLuT8', '2026-06-29 14:28:02.316148');
INSERT INTO django_session (session_key, session_data, expire_date) VALUES ('1tiesa5v0j08dlpqygfx3zsxz0a9v2gw', '.eJxVjEEOwiAQAP-yZ0PYFmjp0btvICy7SNXQpLQn499Nkx70OjOZN4S4byXsTdYwM0wwwuWXUUxPqYfgR6z3RaWlbutM6kjUaZu6LSyv69n-DUpsBSboECMbHEkEtSSN1pDPFF2WhC4nxswWO-qFsmdPyINxQ68FkzPeevh8AQiKOIw:1wZ8Pq:A9gBNTp7OuzR2mSxGRiXWJL8VzY8l8HJaKjo31e4dy8', '2026-06-29 14:35:54.958418');
INSERT INTO extra_curricular_atividadeextensionista (id, num_estudantes, carga_horaria, parecer_desup, motivo_parecer, data_atualizacao, pendencia_id, horas_aprovadas) VALUES ('1', '10', '5', 'PENDENTE', '', '2026-06-10 15:03:54.569618', '3', NULL);
INSERT INTO extra_curricular_orientacaotcc (id, num_orientandos, carga_horaria, parecer_desup, motivo_parecer, data_atualizacao, pendencia_id, horas_aprovadas) VALUES ('2', '4', '2', 'PENDENTE', '', '2026-06-10 15:03:54.559122', '3', NULL);
INSERT INTO extra_curricular_orientacaotcc (id, num_orientandos, carga_horaria, parecer_desup, motivo_parecer, data_atualizacao, pendencia_id, horas_aprovadas) VALUES ('3', '6', '3', 'PENDENTE', '', '2026-06-10 15:03:54.591930', '4', NULL);
INSERT INTO extra_curricular_orientacaotcc (id, num_orientandos, carga_horaria, parecer_desup, motivo_parecer, data_atualizacao, pendencia_id, horas_aprovadas) VALUES ('4', '8', '4', 'APROVADO', 'Documentação de orientação anexada corretamente e homologada.', '2026-06-10 15:03:54.623390', '5', NULL);
INSERT INTO extra_curricular_orientacaotcc (id, num_orientandos, carga_horaria, parecer_desup, motivo_parecer, data_atualizacao, pendencia_id, horas_aprovadas) VALUES ('5', '2', '1', 'REJEITADO', 'O docente não informou os nomes dos alunos nem apresentou os planos de orientação.', '2026-06-10 15:03:54.651449', '6', NULL);
INSERT INTO extra_curricular_pendenciaextra (id, semestre, sei_numero, status, data_criacao, data_atualizacao, criado_por_id, professor_id, unidade_id, motivo_status_desup) VALUES ('3', '2026.1', 'SEI-123456/123456/2026', 'RASCUNHO', '2026-06-10 15:03:54.547374', '2026-06-10 15:03:54.547422', '3', '6', '2', '');
INSERT INTO extra_curricular_pendenciaextra (id, semestre, sei_numero, status, data_criacao, data_atualizacao, criado_por_id, professor_id, unidade_id, motivo_status_desup) VALUES ('4', '2026.1', 'SEI-654321/654321/2026', 'ENVIADO', '2026-06-10 15:03:54.580778', '2026-06-10 15:03:54.580823', '3', '7', '2', '');
INSERT INTO extra_curricular_pendenciaextra (id, semestre, sei_numero, status, data_criacao, data_atualizacao, criado_por_id, professor_id, unidade_id, motivo_status_desup) VALUES ('5', '2026.1', 'SEI-111111/111111/2026', 'APROVADO', '2026-06-10 15:03:54.612624', '2026-06-10 15:03:54.612663', '3', '8', '2', '');
INSERT INTO extra_curricular_pendenciaextra (id, semestre, sei_numero, status, data_criacao, data_atualizacao, criado_por_id, professor_id, unidade_id, motivo_status_desup) VALUES ('6', '2026.1', 'SEI-222222/222222/2026', 'REJEITADO', '2026-06-10 15:03:54.641945', '2026-06-10 15:03:54.641983', '3', '9', '2', 'Justificativas rejeitadas devido à falta de comprovação legal.');
INSERT INTO extra_curricular_reducaocargahoraria (id, motivo_reducao, horas_reduzidas, parecer_desup, motivo_parecer, data_atualizacao, pendencia_id, horas_aprovadas) VALUES ('1', 'Redução de carga horária para Coordenador Adjunto de ADS conforme Resolução Interna.', '4', 'PENDENTE', '', '2026-06-10 15:03:54.601836', '4', NULL);
INSERT INTO extra_curricular_reducaocargahoraria (id, motivo_reducao, horas_reduzidas, parecer_desup, motivo_parecer, data_atualizacao, pendencia_id, horas_aprovadas) VALUES ('2', 'Redução de carga horária de 8h autorizada para Direção Adjunta de Unidade.', '8', 'APROVADO', 'Designação oficial anexada e conferida.', '2026-06-10 15:03:54.633037', '5', NULL);
INSERT INTO extra_curricular_reducaocargahoraria (id, motivo_reducao, horas_reduzidas, parecer_desup, motivo_parecer, data_atualizacao, pendencia_id, horas_aprovadas) VALUES ('3', 'Redução solicitada para projeto de pesquisa científica.', '6', 'REJEITADO', 'Não há portaria ou aprovação do projeto anexada no processo SEI.', '2026-06-10 15:03:54.661540', '6', NULL);
INSERT INTO professors_contracttype (id, nome, regime_trabalho, max_class_hours, max_total_hours, max_classes, categoria, dias_presenca_obrigatorios) VALUES ('1', 'Ensino Técnico - 40h', '40h DE', '20', '40', '6', 'EFETIVO', '3');
INSERT INTO professors_contracttype (id, nome, regime_trabalho, max_class_hours, max_total_hours, max_classes, categoria, dias_presenca_obrigatorios) VALUES ('2', 'Professor FAETEC Ensino Superior 40H', '40h', '20', '40', '6', 'EFETIVO', '3');
INSERT INTO professors_contracttype (id, nome, regime_trabalho, max_class_hours, max_total_hours, max_classes, categoria, dias_presenca_obrigatorios) VALUES ('3', 'Professor FAETEC I 20H', '20h', '12', '20', '4', 'EFETIVO', '2');
INSERT INTO professors_professor (id, status, tipo_contrato_id, unidade_principal_id, desup_email, desup_nome, is_cedido, rh_email, rh_matricula, rh_nome, ha, materia, ID_FUNCIONAL) VALUES ('1', 'Ativo', '1', '1', NULL, NULL, '0', 'ana.souza@faetec.rj.gov.br', 'MAT-P001', 'Ana Carolina Souza', '20', 'INFO', 'IDF-P001');
INSERT INTO professors_professor (id, status, tipo_contrato_id, unidade_principal_id, desup_email, desup_nome, is_cedido, rh_email, rh_matricula, rh_nome, ha, materia, ID_FUNCIONAL) VALUES ('2', 'Ativo', '1', '1', NULL, NULL, '0', 'bruno.lima@faetec.rj.gov.br', 'MAT-P002', 'Bruno Henrique Lima', '20', 'ELETRO', 'IDF-P002');
INSERT INTO professors_professor (id, status, tipo_contrato_id, unidade_principal_id, desup_email, desup_nome, is_cedido, rh_email, rh_matricula, rh_nome, ha, materia, ID_FUNCIONAL) VALUES ('3', 'Ativo', '1', '1', NULL, NULL, '0', 'carla.mendes@faetec.rj.gov.br', 'MAT-P003', 'Carla Regina Mendes', '20', 'ADMIN', 'IDF-P003');
INSERT INTO professors_professor (id, status, tipo_contrato_id, unidade_principal_id, desup_email, desup_nome, is_cedido, rh_email, rh_matricula, rh_nome, ha, materia, ID_FUNCIONAL) VALUES ('4', 'Ativo', '1', '1', NULL, NULL, '0', 'diego.rocha@faetec.rj.gov.br', 'MAT-P004', 'Diego Ferreira Rocha', '20', 'INFO', 'IDF-P004');
INSERT INTO professors_professor (id, status, tipo_contrato_id, unidade_principal_id, desup_email, desup_nome, is_cedido, rh_email, rh_matricula, rh_nome, ha, materia, ID_FUNCIONAL) VALUES ('5', 'Ativo', '1', '1', NULL, NULL, '0', 'elaine.barbosa@faetec.rj.gov.br', 'MAT-P005', 'Elaine Cristina Barbosa', '20', 'FORMACAO', 'IDF-P005');
INSERT INTO professors_professor (id, status, tipo_contrato_id, unidade_principal_id, desup_email, desup_nome, is_cedido, rh_email, rh_matricula, rh_nome, ha, materia, ID_FUNCIONAL) VALUES ('6', 'Ativo', '2', '2', NULL, NULL, '0', 'adilson.ricardo.da.silva@faeterj.edu.br', 'MAT-51381966', 'ADILSON RICARDO DA SILVA', '0', 'INFO', '51381966');
INSERT INTO professors_professor (id, status, tipo_contrato_id, unidade_principal_id, desup_email, desup_nome, is_cedido, rh_email, rh_matricula, rh_nome, ha, materia, ID_FUNCIONAL) VALUES ('7', 'Ativo', '2', '2', NULL, NULL, '0', 'alessandro.de.almeida.castro.cerqueira@faeterj.edu.br', '00-3152943-1', 'ALESSANDRO DE ALMEIDA CASTRO CERQUEIRA', '0', 'INFO', '51244861');
INSERT INTO professors_professor (id, status, tipo_contrato_id, unidade_principal_id, desup_email, desup_nome, is_cedido, rh_email, rh_matricula, rh_nome, ha, materia, ID_FUNCIONAL) VALUES ('8', 'Ativo', '3', '2', NULL, NULL, '0', 'andre.luis.vilanova.ribeiro@faeterj.edu.br', '00-0225379-7', 'ANDRE LUIS VILANOVA RIBEIRO', '0', 'QUIMICA', '44040920');
INSERT INTO professors_professor (id, status, tipo_contrato_id, unidade_principal_id, desup_email, desup_nome, is_cedido, rh_email, rh_matricula, rh_nome, ha, materia, ID_FUNCIONAL) VALUES ('9', 'Ativo', '2', '2', NULL, NULL, '0', 'artur.sergio.lopes@faeterj.edu.br', '00-0226581-7', 'ARTUR SERGIO LOPES', '0', 'FORMACAO', '44564465');
INSERT INTO professors_professor (id, status, tipo_contrato_id, unidade_principal_id, desup_email, desup_nome, is_cedido, rh_email, rh_matricula, rh_nome, ha, materia, ID_FUNCIONAL) VALUES ('10', 'Ativo', '2', '2', NULL, NULL, '0', 'carlos.eduardo.costa.vieira@faeterj.edu.br', '00-0225698-0', 'CARLOS EDUARDO COSTA VIEIRA', '0', 'INFO', '44058144');
INSERT INTO professors_professor (id, status, tipo_contrato_id, unidade_principal_id, desup_email, desup_nome, is_cedido, rh_email, rh_matricula, rh_nome, ha, materia, ID_FUNCIONAL) VALUES ('11', 'Ativo', '2', '2', NULL, NULL, '0', 'cinthia.da.silva.lisboa@faeterj.edu.br', '00-0225700-4', 'CINTHIA DA SILVA LISBOA', '0', 'OUTROS', '43591990');
INSERT INTO professors_professor (id, status, tipo_contrato_id, unidade_principal_id, desup_email, desup_nome, is_cedido, rh_email, rh_matricula, rh_nome, ha, materia, ID_FUNCIONAL) VALUES ('12', 'Ativo', '2', '2', NULL, NULL, '0', 'daniel.vazquez.figueiredo@faeterj.edu.br', '00-0224898-7', 'DANIEL VAZQUEZ FIGUEIREDO', '0', 'SAUDE', '32718632');
INSERT INTO professors_professor (id, status, tipo_contrato_id, unidade_principal_id, desup_email, desup_nome, is_cedido, rh_email, rh_matricula, rh_nome, ha, materia, ID_FUNCIONAL) VALUES ('13', 'Ativo', '2', '2', NULL, NULL, '0', 'daniele.silva.de.carvalho@faeterj.edu.br', '00-0223487-0', 'DANIELE SILVA DE CARVALHO', '0', 'FORMACAO', '5786495');
INSERT INTO professors_professor (id, status, tipo_contrato_id, unidade_principal_id, desup_email, desup_nome, is_cedido, rh_email, rh_matricula, rh_nome, ha, materia, ID_FUNCIONAL) VALUES ('14', 'Ativo', '2', '2', NULL, NULL, '0', 'diego.mota.lima@faeterj.edu.br', '00-0226421-6', 'DIEGO MOTA LIMA', '0', 'FORMACAO', '43300103');
INSERT INTO professors_professor (id, status, tipo_contrato_id, unidade_principal_id, desup_email, desup_nome, is_cedido, rh_email, rh_matricula, rh_nome, ha, materia, ID_FUNCIONAL) VALUES ('15', 'Ativo', '2', '2', NULL, NULL, '0', 'fabio.henrique.silva.dos.santos@faeterj.edu.br', '00-3080924-8', 'FABIO HENRIQUE SILVA DOS SANTOS', '0', 'OUTROS', '36876135');
INSERT INTO professors_professor (id, status, tipo_contrato_id, unidade_principal_id, desup_email, desup_nome, is_cedido, rh_email, rh_matricula, rh_nome, ha, materia, ID_FUNCIONAL) VALUES ('16', 'Ativo', '2', '2', NULL, NULL, '0', 'fausto.amaro.da.silva.araujo@faeterj.edu.br', '00-0226459-6', 'FAUSTO AMARO DA SILVA ARAUJO', '0', 'OUTROS', '43374158');
INSERT INTO professors_professor (id, status, tipo_contrato_id, unidade_principal_id, desup_email, desup_nome, is_cedido, rh_email, rh_matricula, rh_nome, ha, materia, ID_FUNCIONAL) VALUES ('17', 'Ativo', '2', '2', NULL, NULL, '0', 'franziska.huber@faeterj.edu.br', '00-0224901-9', 'FRANZISKA HUBER', '0', 'SAUDE', '42183960');
INSERT INTO professors_professor (id, status, tipo_contrato_id, unidade_principal_id, desup_email, desup_nome, is_cedido, rh_email, rh_matricula, rh_nome, ha, materia, ID_FUNCIONAL) VALUES ('18', 'Ativo', '2', '2', NULL, NULL, '0', 'frederico.guilherme.ferreira.lima@faeterj.edu.br', '00-0223657-8', 'FREDERICO GUILHERME FERREIRA LIMA', '0', 'INFO', '5763517');
INSERT INTO professors_professor (id, status, tipo_contrato_id, unidade_principal_id, desup_email, desup_nome, is_cedido, rh_email, rh_matricula, rh_nome, ha, materia, ID_FUNCIONAL) VALUES ('19', 'Ativo', '2', '2', NULL, NULL, '0', 'gisele.pontes.oggiano@faeterj.edu.br', '00-0223876-4', 'GISELE PONTES OGGIANO', '0', 'INFO', '5788501');
INSERT INTO professors_professor (id, status, tipo_contrato_id, unidade_principal_id, desup_email, desup_nome, is_cedido, rh_email, rh_matricula, rh_nome, ha, materia, ID_FUNCIONAL) VALUES ('20', 'Ativo', '2', '2', NULL, NULL, '0', 'hudson.dos.santos.barros@faeterj.edu.br', '00-0226075-0', 'HUDSON DOS SANTOS BARROS', '0', 'FORMACAO', '42052823');
INSERT INTO professors_professor (id, status, tipo_contrato_id, unidade_principal_id, desup_email, desup_nome, is_cedido, rh_email, rh_matricula, rh_nome, ha, materia, ID_FUNCIONAL) VALUES ('21', 'Ativo', '2', '2', NULL, NULL, '0', 'iamara.da.silva.andrade@faeterj.edu.br', '00-0225712-9', 'IAMARA DA SILVA ANDRADE', '0', 'SAUDE', '43883044');
INSERT INTO professors_professor (id, status, tipo_contrato_id, unidade_principal_id, desup_email, desup_nome, is_cedido, rh_email, rh_matricula, rh_nome, ha, materia, ID_FUNCIONAL) VALUES ('22', 'Ativo', '2', '2', NULL, NULL, '0', 'janaina.da.silva.vettorazzi@faeterj.edu.br', '00-0221410-4', 'JANAINA DA SILVA VETTORAZZI', '0', 'SAUDE', '40725251');
INSERT INTO professors_professor (id, status, tipo_contrato_id, unidade_principal_id, desup_email, desup_nome, is_cedido, rh_email, rh_matricula, rh_nome, ha, materia, ID_FUNCIONAL) VALUES ('23', 'Ativo', '2', '2', NULL, NULL, '0', 'joao.gabriel.monteiro.e.silva@faeterj.edu.br', '00-0225713-7', 'JOAO GABRIEL MONTEIRO E SILVA', '0', 'FORMACAO', '44058870');
INSERT INTO professors_professor (id, status, tipo_contrato_id, unidade_principal_id, desup_email, desup_nome, is_cedido, rh_email, rh_matricula, rh_nome, ha, materia, ID_FUNCIONAL) VALUES ('24', 'Ativo', '2', '2', NULL, NULL, '0', 'josimar.da.silva.ribeiro@faeterj.edu.br', '00-0226283-0', 'JOSIMAR DA SILVA RIBEIRO', '0', 'INFO', '43306373');
INSERT INTO professors_professor (id, status, tipo_contrato_id, unidade_principal_id, desup_email, desup_nome, is_cedido, rh_email, rh_matricula, rh_nome, ha, materia, ID_FUNCIONAL) VALUES ('25', 'Ativo', '3', '2', NULL, NULL, '0', 'katia.regina.araujo.da.silva@faeterj.edu.br', '00-0223758-4', 'KATIA REGINA ARAUJO DA SILVA', '0', 'SAUDE', '5777992');
INSERT INTO professors_professor (id, status, tipo_contrato_id, unidade_principal_id, desup_email, desup_nome, is_cedido, rh_email, rh_matricula, rh_nome, ha, materia, ID_FUNCIONAL) VALUES ('26', 'Ativo', '2', '2', NULL, NULL, '0', 'layla.advincula.candido.de.azevedo@faeterj.edu.br', '00-0226729-2', 'LAYLA ADVINCULA CANDIDO DE AZEVEDO', '0', 'ADMIN', '5789478');
INSERT INTO professors_professor (id, status, tipo_contrato_id, unidade_principal_id, desup_email, desup_nome, is_cedido, rh_email, rh_matricula, rh_nome, ha, materia, ID_FUNCIONAL) VALUES ('27', 'Ativo', '2', '2', NULL, NULL, '0', 'leonardo.fonseca.da.silva@faeterj.edu.br', '00-3156202-8', 'LEONARDO FONSECA DA SILVA', '0', 'QUIMICA', '50076310');
INSERT INTO professors_professor (id, status, tipo_contrato_id, unidade_principal_id, desup_email, desup_nome, is_cedido, rh_email, rh_matricula, rh_nome, ha, materia, ID_FUNCIONAL) VALUES ('28', 'Ativo', '2', '2', NULL, NULL, '0', 'leonardo.pinheiro.gomes@faeterj.edu.br', '00-0226456-2', 'LEONARDO PINHEIRO GOMES', '0', 'FORMACAO', '43449255');
INSERT INTO professors_professor (id, status, tipo_contrato_id, unidade_principal_id, desup_email, desup_nome, is_cedido, rh_email, rh_matricula, rh_nome, ha, materia, ID_FUNCIONAL) VALUES ('29', 'Ativo', '2', '2', NULL, NULL, '0', 'luciano.henrique.lourenco@faeterj.edu.br', '00-0223745-1', 'LUCIANO HENRIQUE LOURENCO', '0', 'INFO', '5777666');
INSERT INTO professors_professor (id, status, tipo_contrato_id, unidade_principal_id, desup_email, desup_nome, is_cedido, rh_email, rh_matricula, rh_nome, ha, materia, ID_FUNCIONAL) VALUES ('30', 'Ativo', '2', '2', NULL, NULL, '0', 'marcia.lie.ayukawa@faeterj.edu.br', '00-0226296-2', 'MARCIA LIE AYUKAWA', '0', 'QUIMICA', '44119259');
INSERT INTO professors_professor (id, status, tipo_contrato_id, unidade_principal_id, desup_email, desup_nome, is_cedido, rh_email, rh_matricula, rh_nome, ha, materia, ID_FUNCIONAL) VALUES ('31', 'Ativo', '2', '2', NULL, NULL, '0', 'marcio.de.brito.serafim@faeterj.edu.br', '00-0226654-2', 'MARCIO DE BRITO SERAFIM', '0', 'FORMACAO', '42648890');
INSERT INTO professors_professor (id, status, tipo_contrato_id, unidade_principal_id, desup_email, desup_nome, is_cedido, rh_email, rh_matricula, rh_nome, ha, materia, ID_FUNCIONAL) VALUES ('32', 'Ativo', '3', '2', NULL, NULL, '0', 'pablo.miranda.soares@faeterj.edu.br', '00-0226999-1', 'PABLO MIRANDA SOARES', '0', 'FORMACAO', '44168454');
INSERT INTO professors_professor (id, status, tipo_contrato_id, unidade_principal_id, desup_email, desup_nome, is_cedido, rh_email, rh_matricula, rh_nome, ha, materia, ID_FUNCIONAL) VALUES ('33', 'Ativo', '2', '2', NULL, NULL, '0', 'rafael.schirmer.de.paula.couto@faeterj.edu.br', '00-3152540-5', 'RAFAEL SCHIRMER DE PAULA COUTO', '0', 'QUIMICA', '51240360');
INSERT INTO professors_professor (id, status, tipo_contrato_id, unidade_principal_id, desup_email, desup_nome, is_cedido, rh_email, rh_matricula, rh_nome, ha, materia, ID_FUNCIONAL) VALUES ('34', 'Ativo', '3', '2', NULL, NULL, '0', 'rayanne.barros.setubal@faeterj.edu.br', '00-3151529-9', 'RAYANNE BARROS SETUBAL', '0', 'QUIMICA', '43480420');
INSERT INTO professors_professor (id, status, tipo_contrato_id, unidade_principal_id, desup_email, desup_nome, is_cedido, rh_email, rh_matricula, rh_nome, ha, materia, ID_FUNCIONAL) VALUES ('35', 'Ativo', '2', '2', NULL, NULL, '0', 'romilda.maria.alves.de.lemos@faeterj.edu.br', '00-0224903-5', 'ROMILDA MARIA ALVES DE LEMOS', '0', 'QUIMICA', '6165494');
INSERT INTO professors_professor (id, status, tipo_contrato_id, unidade_principal_id, desup_email, desup_nome, is_cedido, rh_email, rh_matricula, rh_nome, ha, materia, ID_FUNCIONAL) VALUES ('36', 'Ativo', '2', '2', NULL, NULL, '0', 'tereza.aparecida.ferreira.dornelas@faeterj.edu.br', '00-0224904-3', 'TEREZA APARECIDA FERREIRA DORNELAS', '0', 'SAUDE', '37114476');
INSERT INTO professors_professor (id, status, tipo_contrato_id, unidade_principal_id, desup_email, desup_nome, is_cedido, rh_email, rh_matricula, rh_nome, ha, materia, ID_FUNCIONAL) VALUES ('37', 'Ativo', '2', '2', NULL, NULL, '0', 'thiago.jose.jesus.rebello@faeterj.edu.br', 'MAT-51292467', 'THIAGO JOSE JESUS REBELLO', '0', 'QUIMICA', '51292467');
INSERT INTO professors_professor (id, status, tipo_contrato_id, unidade_principal_id, desup_email, desup_nome, is_cedido, rh_email, rh_matricula, rh_nome, ha, materia, ID_FUNCIONAL) VALUES ('38', 'Ativo', '2', '2', NULL, NULL, '0', 'tulio.queto.de.souza.pinto@faeterj.edu.br', '00-0226308-5', 'TULIO QUETO DE SOUZA PINTO', '0', 'SAUDE', '44119950');
INSERT INTO sqlite_sequence (name, seq) VALUES ('django_migrations', '61');
INSERT INTO sqlite_sequence (name, seq) VALUES ('django_content_type', '26');
INSERT INTO sqlite_sequence (name, seq) VALUES ('auth_permission', '104');
INSERT INTO sqlite_sequence (name, seq) VALUES ('auth_group', '0');
INSERT INTO sqlite_sequence (name, seq) VALUES ('django_admin_log', '6');
INSERT INTO sqlite_sequence (name, seq) VALUES ('courses_curricularcomponent', '93');
INSERT INTO sqlite_sequence (name, seq) VALUES ('courses_matrixcomponent', '97');
INSERT INTO sqlite_sequence (name, seq) VALUES ('extra_curricular_pendenciaextra', '6');
INSERT INTO sqlite_sequence (name, seq) VALUES ('professors_contracttype', '3');
INSERT INTO sqlite_sequence (name, seq) VALUES ('professors_professor', '38');
INSERT INTO sqlite_sequence (name, seq) VALUES ('core_unidade', '4');
INSERT INTO sqlite_sequence (name, seq) VALUES ('courses_course', '5');
INSERT INTO sqlite_sequence (name, seq) VALUES ('core_notificacao', '6');
INSERT INTO sqlite_sequence (name, seq) VALUES ('allocations_alocacaocurricular', '2');
INSERT INTO sqlite_sequence (name, seq) VALUES ('accounts_user', '10');
INSERT INTO sqlite_sequence (name, seq) VALUES ('core_auditoriaglobal', '3');
INSERT INTO sqlite_sequence (name, seq) VALUES ('accounts_passwordresetrequest', '1');
INSERT INTO sqlite_sequence (name, seq) VALUES ('core_janelaentrega', '1');
INSERT INTO sqlite_sequence (name, seq) VALUES ('extra_curricular_orientacaotcc', '5');
INSERT INTO sqlite_sequence (name, seq) VALUES ('extra_curricular_atividadeextensionista', '1');
INSERT INTO sqlite_sequence (name, seq) VALUES ('extra_curricular_reducaocargahoraria', '3');
INSERT INTO sqlite_sequence (name, seq) VALUES ('courses_curriculummatrix', '6');
