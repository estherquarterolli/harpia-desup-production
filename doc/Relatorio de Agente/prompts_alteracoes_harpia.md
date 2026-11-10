 Bloco base obrigatório para todos os prompts


Trabalhe no repositório Harpia DESUP, uma aplicação Django 6 com templates Django, Tailwind CSS, HTMX, Celery e banco relacional. Antes de alterar qualquer arquivo, examine os modelos, formulários, serviços, views, URLs, templates, migrações e testes relacionados. Reaproveite as estruturas existentes quando forem adequadas e não duplique regras de negócio.

Requisitos obrigatórios de qualidade:

1. Responsividade: toda interface criada ou alterada deve funcionar sem perda de conteúdo ou ações em celular, tablet e computador. Valide, no mínimo, larguras próximas de 360 px, 768 px, 1024 px e 1440 px. Formulários devem empilhar campos em telas pequenas; tabelas devem usar uma solução acessível, como cartões responsivos ou rolagem horizontal controlada; botões e áreas clicáveis devem ser utilizáveis por toque; nenhum texto, modal ou menu pode ultrapassar a largura da tela.

2. Segurança: aplique autenticação, autorização e escopo por unidade no servidor, nunca apenas no template. Proteja operações mutáveis com POST, CSRF e validação de propriedade do objeto. Evite IDOR, escalada de privilégio, enumeração de registros, redirecionamento aberto, XSS, SQL injection, mass assignment, vazamento de dados entre unidades, exposição de segredos e condições de corrida. Use transações e restrições no banco quando houver risco de duplicidade ou inconsistência. Não registre senhas, tokens, credenciais ou dados pessoais desnecessários em logs.

3. Perfis: ADMIN é técnico e opera pelo Django Admin; DESUP possui visão institucional; COORDENADOR_UNIDADE só pode acessar dados e operações permitidos para sua própria unidade. Qualquer exceção a esse escopo deve estar explicitamente prevista na regra de negócio e coberta por teste.

4. Texto e acessibilidade: revise todos os textos alterados conforme a norma-padrão do português brasileiro, com acentuação e terminologia institucional consistentes. Não use linguagem vulgar, jocosa ou ambígua. Associe labels aos campos, preserve navegação por teclado, foco visível, mensagens compreensíveis e contraste suficiente. Não comunique estado somente por cor: use também texto, ícone ou atributo acessível.

5. Integridade e compatibilidade: crie migrações reversíveis e seguras para dados existentes. Evite exclusões destrutivas. Quando uma definição administrativa não estiver disponível, não invente dados; prepare a estrutura e documente a dependência. Preserve funcionalidades e testes já existentes.

6. Testes: inclua testes de modelo, serviço e view, além de cenários de autorização e isolamento entre unidades. Teste caminhos válidos, inválidos, concorrentes e tentativas de acesso indevido. Quando houver interface relevante, acrescente teste de fluxo ou E2E compatível com a suíte atual.

7. Verificação: ao finalizar, execute `python manage.py check`, `python manage.py makemigrations --check --dry-run` e `python manage.py test --settings=config.settings._tmp_test`. Se alterar classes Tailwind, execute também `npm run build:css`. Corrija as falhas causadas pela alteração; não oculte erros nem enfraqueça testes.

8. Se for necessario alguma alteração no banco de dados (supabase) é bom informar!!: 
ATUAL SQL:


-- WARNING: This schema is for context only and is not meant to be run.
-- Table order and constraints may not be valid for execution.

CREATE TABLE public.django_migrations (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  app character varying NOT NULL,
  name character varying NOT NULL,
  applied timestamp with time zone NOT NULL,
  CONSTRAINT django_migrations_pkey PRIMARY KEY (id)
);
CREATE TABLE public.django_content_type (
  id integer GENERATED ALWAYS AS IDENTITY NOT NULL,
  app_label character varying NOT NULL,
  model character varying NOT NULL,
  CONSTRAINT django_content_type_pkey PRIMARY KEY (id)
);
CREATE TABLE public.auth_permission (
  id integer GENERATED ALWAYS AS IDENTITY NOT NULL,
  name character varying NOT NULL,
  content_type_id integer NOT NULL,
  codename character varying NOT NULL,
  CONSTRAINT auth_permission_pkey PRIMARY KEY (id),
  CONSTRAINT auth_permission_content_type_id_2f476e4b_fk_django_co FOREIGN KEY (content_type_id) REFERENCES public.django_content_type(id)
);
CREATE TABLE public.auth_group (
  id integer GENERATED ALWAYS AS IDENTITY NOT NULL,
  name character varying NOT NULL UNIQUE,
  CONSTRAINT auth_group_pkey PRIMARY KEY (id)
);
CREATE TABLE public.auth_group_permissions (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  group_id integer NOT NULL,
  permission_id integer NOT NULL,
  CONSTRAINT auth_group_permissions_pkey PRIMARY KEY (id),
  CONSTRAINT auth_group_permissions_group_id_b120cbf9_fk_auth_group_id FOREIGN KEY (group_id) REFERENCES public.auth_group(id),
  CONSTRAINT auth_group_permissio_permission_id_84c5c92e_fk_auth_perm FOREIGN KEY (permission_id) REFERENCES public.auth_permission(id)
);
CREATE TABLE public.harpiadb_contas_redefinicao_senha (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  token uuid NOT NULL UNIQUE,
  criado_em timestamp with time zone NOT NULL,
  finalizado boolean NOT NULL,
  finalizado_em timestamp with time zone,
  aprovado_por_id bigint,
  user_id bigint NOT NULL,
  CONSTRAINT harpiadb_contas_redefinicao_senha_pkey PRIMARY KEY (id),
  CONSTRAINT accounts_passwordres_aprovado_por_id_4f6af868_fk_accounts_ FOREIGN KEY (aprovado_por_id) REFERENCES public.harpiadb_contas_usuario(id),
  CONSTRAINT accounts_passwordres_user_id_d7f9b8ac_fk_accounts_ FOREIGN KEY (user_id) REFERENCES public.harpiadb_contas_usuario(id)
);
CREATE TABLE public.harpiadb_contas_alteracao_senha (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  token uuid NOT NULL UNIQUE,
  criado_em timestamp with time zone NOT NULL,
  usado boolean NOT NULL,
  usado_em timestamp with time zone,
  solicitado_ip inet,
  user_id bigint NOT NULL,
  CONSTRAINT harpiadb_contas_alteracao_senha_pkey PRIMARY KEY (id),
  CONSTRAINT accounts_selfpasswor_user_id_4abb0f79_fk_accounts_ FOREIGN KEY (user_id) REFERENCES public.harpiadb_contas_usuario(id)
);
CREATE TABLE public.harpiadb_contas_usuario (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  password character varying NOT NULL,
  last_login timestamp with time zone,
  is_superuser boolean NOT NULL,
  username character varying NOT NULL UNIQUE,
  first_name character varying NOT NULL,
  last_name character varying NOT NULL,
  is_staff boolean NOT NULL,
  is_active boolean NOT NULL,
  date_joined timestamp with time zone NOT NULL,
  email character varying NOT NULL UNIQUE,
  perfil character varying NOT NULL,
  dados_submetidos boolean NOT NULL,
  forcar_troca_senha boolean NOT NULL,
  unidade_id bigint,
  CONSTRAINT harpiadb_contas_usuario_pkey PRIMARY KEY (id),
  CONSTRAINT accounts_user_unidade_id_b0386923_fk_core_unidade_id FOREIGN KEY (unidade_id) REFERENCES public.harpiadb_nucleo_unidade(id)
);
CREATE TABLE public.harpiadb_contas_usuario_grupos (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  user_id bigint NOT NULL,
  group_id integer NOT NULL,
  CONSTRAINT harpiadb_contas_usuario_grupos_pkey PRIMARY KEY (id),
  CONSTRAINT accounts_user_groups_user_id_52b62117_fk_accounts_user_id FOREIGN KEY (user_id) REFERENCES public.harpiadb_contas_usuario(id),
  CONSTRAINT accounts_user_groups_group_id_bd11a704_fk_auth_group_id FOREIGN KEY (group_id) REFERENCES public.auth_group(id)
);
CREATE TABLE public.harpiadb_nucleo_unidade (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  nome character varying NOT NULL UNIQUE,
  sigla character varying NOT NULL,
  status boolean NOT NULL,
  CONSTRAINT harpiadb_nucleo_unidade_pkey PRIMARY KEY (id)
);
CREATE TABLE public.harpiadb_nucleo_auditoria (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  email character varying NOT NULL,
  acao character varying NOT NULL,
  detalhes text NOT NULL,
  ip inet,
  user_agent text NOT NULL,
  criado_em timestamp with time zone NOT NULL,
  usuario_id bigint,
  CONSTRAINT harpiadb_nucleo_auditoria_pkey PRIMARY KEY (id),
  CONSTRAINT core_auditoriaglobal_usuario_id_c0f97850_fk_accounts_user_id FOREIGN KEY (usuario_id) REFERENCES public.harpiadb_contas_usuario(id)
);
CREATE TABLE public.harpiadb_nucleo_notificacao (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  titulo character varying NOT NULL,
  mensagem text NOT NULL,
  lida boolean NOT NULL,
  url_acao character varying,
  data_criacao timestamp with time zone NOT NULL,
  destinatario_id bigint,
  unidade_destino_id bigint,
  CONSTRAINT harpiadb_nucleo_notificacao_pkey PRIMARY KEY (id),
  CONSTRAINT core_notificacao_destinatario_id_f3f2984a_fk_accounts_user_id FOREIGN KEY (destinatario_id) REFERENCES public.harpiadb_contas_usuario(id),
  CONSTRAINT core_notificacao_unidade_destino_id_28d94af4_fk_core_unidade_id FOREIGN KEY (unidade_destino_id) REFERENCES public.harpiadb_nucleo_unidade(id)
);
CREATE TABLE public.harpiadb_nucleo_janela_entrega (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  semestre character varying NOT NULL,
  data_inicio date NOT NULL,
  data_fim date NOT NULL,
  status character varying NOT NULL,
  unidade_id bigint,
  CONSTRAINT harpiadb_nucleo_janela_entrega_pkey PRIMARY KEY (id),
  CONSTRAINT core_janelaentrega_unidade_id_be265a7c_fk_core_unidade_id FOREIGN KEY (unidade_id) REFERENCES public.harpiadb_nucleo_unidade(id)
);
CREATE TABLE public.harpiadb_contas_usuario_permissoes (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  user_id bigint NOT NULL,
  permission_id integer NOT NULL,
  CONSTRAINT harpiadb_contas_usuario_permissoes_pkey PRIMARY KEY (id),
  CONSTRAINT accounts_user_user_p_user_id_e4f0a161_fk_accounts_ FOREIGN KEY (user_id) REFERENCES public.harpiadb_contas_usuario(id),
  CONSTRAINT accounts_user_user_p_permission_id_113bb443_fk_auth_perm FOREIGN KEY (permission_id) REFERENCES public.auth_permission(id)
);
CREATE TABLE public.django_admin_log (
  id integer GENERATED ALWAYS AS IDENTITY NOT NULL,
  action_time timestamp with time zone NOT NULL,
  object_id text,
  object_repr character varying NOT NULL,
  action_flag smallint NOT NULL CHECK (action_flag >= 0),
  change_message text NOT NULL,
  content_type_id integer,
  user_id bigint NOT NULL,
  CONSTRAINT django_admin_log_pkey PRIMARY KEY (id),
  CONSTRAINT django_admin_log_content_type_id_c4bce8eb_fk_django_co FOREIGN KEY (content_type_id) REFERENCES public.django_content_type(id),
  CONSTRAINT django_admin_log_user_id_c564eba6_fk_accounts_user_id FOREIGN KEY (user_id) REFERENCES public.harpiadb_contas_usuario(id)
);
CREATE TABLE public.harpiadb_cursos_curso (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  nome character varying NOT NULL UNIQUE,
  sigla character varying NOT NULL UNIQUE,
  atualizado_em timestamp with time zone,
  CONSTRAINT harpiadb_cursos_curso_pkey PRIMARY KEY (id)
);
CREATE TABLE public.harpiadb_cursos_curso_unidade (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  ativo boolean NOT NULL,
  curso_id bigint NOT NULL,
  unidade_id bigint NOT NULL,
  CONSTRAINT harpiadb_cursos_curso_unidade_pkey PRIMARY KEY (id),
  CONSTRAINT courses_courseunit_curso_id_c9b92a81_fk_courses_course_id FOREIGN KEY (curso_id) REFERENCES public.harpiadb_cursos_curso(id),
  CONSTRAINT courses_courseunit_unidade_id_6f74ccd6_fk_core_unidade_id FOREIGN KEY (unidade_id) REFERENCES public.harpiadb_nucleo_unidade(id)
);
CREATE TABLE public.harpiadb_cursos_componente_curricular (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  nome character varying NOT NULL,
  codigo character varying NOT NULL,
  carga_horaria_padrao integer NOT NULL CHECK (carga_horaria_padrao >= 0),
  creditos smallint NOT NULL CHECK (creditos >= 0),
  ementa text NOT NULL,
  obrigatoria boolean NOT NULL,
  atualizado_em timestamp with time zone,
  CONSTRAINT harpiadb_cursos_componente_curricular_pkey PRIMARY KEY (id)
);
CREATE TABLE public.harpiadb_cursos_componente_pre_requisitos (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  from_curricularcomponent_id bigint NOT NULL,
  to_curricularcomponent_id bigint NOT NULL,
  CONSTRAINT harpiadb_cursos_componente_pre_requisitos_pkey PRIMARY KEY (id),
  CONSTRAINT courses_curricularco_from_curricularcompo_bfc6b4d3_fk_courses_c FOREIGN KEY (from_curricularcomponent_id) REFERENCES public.harpiadb_cursos_componente_curricular(id),
  CONSTRAINT courses_curricularco_to_curricularcompone_4f8bed59_fk_courses_c FOREIGN KEY (to_curricularcomponent_id) REFERENCES public.harpiadb_cursos_componente_curricular(id)
);
CREATE TABLE public.harpiadb_cursos_matriz_curricular (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  nome character varying NOT NULL,
  is_vigente boolean NOT NULL,
  is_rascunho boolean NOT NULL,
  criada_em timestamp with time zone,
  periodo_letivo character varying,
  turno character varying CHECK (turno IS NULL OR (turno::text = ANY (ARRAY['M'::character varying::text, 'T'::character varying::text, 'N'::character varying::text]))),
  curso_id bigint,
  CONSTRAINT harpiadb_cursos_matriz_curricular_pkey PRIMARY KEY (id),
  CONSTRAINT courses_curriculummatrix_curso_id_75c22ec8_fk_courses_course_id FOREIGN KEY (curso_id) REFERENCES public.harpiadb_cursos_curso(id)
);
CREATE TABLE public.harpiadb_cursos_turma (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  ano_semestre character varying NOT NULL,
  identificador character varying NOT NULL,
  matriz_curricular_id bigint NOT NULL,
  matriz_componente_id bigint,
  CONSTRAINT harpiadb_cursos_turma_pkey PRIMARY KEY (id),
  CONSTRAINT courses_classgroup_matriz_curricular_id_7ef73a3e_fk_courses_c FOREIGN KEY (matriz_curricular_id) REFERENCES public.harpiadb_cursos_matriz_curricular(id),
  CONSTRAINT courses_classgroup_matriz_componente_id_156e9b54_fk_courses_m FOREIGN KEY (matriz_componente_id) REFERENCES public.harpiadb_cursos_componente_matriz(id)
);
CREATE TABLE public.harpiadb_cursos_componente_matriz (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  codigo character varying NOT NULL,
  periodo character varying NOT NULL,
  carga_horaria integer NOT NULL CHECK (carga_horaria >= 0),
  creditos smallint NOT NULL CHECK (creditos >= 0),
  compartilhado boolean NOT NULL,
  carga_horaria_semanal numeric NOT NULL,
  distribuicao_semanal text NOT NULL,
  status character varying NOT NULL,
  observacoes text NOT NULL,
  componente_curricular_id bigint,
  curso_compartilhado_id bigint,
  docente_id bigint,
  matriz_id bigint NOT NULL,
  atualizado_em timestamp with time zone,
  nome_temporario character varying NOT NULL DEFAULT ''::character varying,
  CONSTRAINT harpiadb_cursos_componente_matriz_pkey PRIMARY KEY (id),
  CONSTRAINT courses_matrixcompon_curso_compartilhado__ab2fef44_fk_courses_c FOREIGN KEY (curso_compartilhado_id) REFERENCES public.harpiadb_cursos_curso_unidade(id),
  CONSTRAINT courses_matrixcompon_docente_id_aca9e9a3_fk_professor FOREIGN KEY (docente_id) REFERENCES public.harpiadb_professores_professor(id),
  CONSTRAINT courses_matrixcompon_matriz_id_4f9e0c91_fk_courses_c FOREIGN KEY (matriz_id) REFERENCES public.harpiadb_cursos_matriz_curricular(id),
  CONSTRAINT harpiadb_cursos_comp_componente_curricula_18f458a9_fk_harpiadb_ FOREIGN KEY (componente_curricular_id) REFERENCES public.harpiadb_cursos_componente_curricular(id)
);
CREATE TABLE public.harpiadb_alocacoes_alocacao_curricular (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  semestre character varying NOT NULL,
  turno character varying NOT NULL,
  status character varying NOT NULL,
  sei_numero character varying CHECK (sei_numero IS NULL OR sei_numero::text ~ '^SEI-\d{6}/\d{6}/\d{4}$'::text) NOT VALI),
  data_criacao timestamp with time zone NOT NULL,
  data_ultimo_ajuste timestamp with time zone NOT NULL,
  curso_id bigint NOT NULL,
  unidade_id bigint NOT NULL,
  CONSTRAINT harpiadb_alocacoes_alocacao_curricular_pkey PRIMARY KEY (id),
  CONSTRAINT allocations_alocacao_curso_id_ce4864b5_fk_courses_c FOREIGN KEY (curso_id) REFERENCES public.harpiadb_cursos_curso_unidade(id),
  CONSTRAINT allocations_alocacao_unidade_id_81a9e624_fk_core_unid FOREIGN KEY (unidade_id) REFERENCES public.harpiadb_nucleo_unidade(id)
);
CREATE TABLE public.harpiadb_professores_tipo_contrato (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  nome character varying NOT NULL,
  categoria character varying NOT NULL,
  regime_trabalho character varying NOT NULL,
  dias_presenca_obrigatorios smallint NOT NULL CHECK (dias_presenca_obrigatorios >= 0),
  max_class_hours integer NOT NULL CHECK (max_class_hours >= 0),
  max_total_hours integer NOT NULL CHECK (max_total_hours >= 0),
  max_classes integer NOT NULL CHECK (max_classes >= 0),
  CONSTRAINT harpiadb_professores_tipo_contrato_pkey PRIMARY KEY (id)
);
CREATE TABLE public.harpiadb_professores_professor (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  ID_FUNCIONAL character varying UNIQUE,
  rh_matricula character varying UNIQUE,
  rh_nome character varying NOT NULL,
  rh_email character varying,
  desup_nome character varying,
  desup_email character varying,
  is_cedido boolean NOT NULL,
  ha integer NOT NULL CHECK (ha >= 0),
  status character varying NOT NULL,
  tipo_contrato_id bigint NOT NULL,
  unidade_principal_id bigint,
  atualizado_em timestamp with time zone,
  locais_lotacao text NOT NULL DEFAULT ''::text,
  carga_diferenciada boolean NOT NULL,
  carga_horaria_personalizada integer CHECK (carga_horaria_personalizada >= 0),
  CONSTRAINT harpiadb_professores_professor_pkey PRIMARY KEY (id),
  CONSTRAINT professors_professor_tipo_contrato_id_dc65d6f4_fk_professor FOREIGN KEY (tipo_contrato_id) REFERENCES public.harpiadb_professores_tipo_contrato(id),
  CONSTRAINT professors_professor_unidade_principal_id_0cd6f688_fk_core_unid FOREIGN KEY (unidade_principal_id) REFERENCES public.harpiadb_nucleo_unidade(id)
);
CREATE TABLE public.harpiadb_professores_professor_cursos (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  professor_id bigint NOT NULL,
  course_id bigint NOT NULL,
  CONSTRAINT harpiadb_professores_professor_cursos_pkey PRIMARY KEY (id),
  CONSTRAINT professors_professor_professor_id_4ad24c01_fk_professor FOREIGN KEY (professor_id) REFERENCES public.harpiadb_professores_professor(id),
  CONSTRAINT professors_professor_course_id_e5f04a8f_fk_courses_c FOREIGN KEY (course_id) REFERENCES public.harpiadb_cursos_curso(id)
);
CREATE TABLE public.harpiadb_professores_ausencia (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  data_inicio date NOT NULL,
  data_fim date NOT NULL,
  motivo text NOT NULL,
  comprovante character varying,
  professor_id bigint NOT NULL,
  CONSTRAINT harpiadb_professores_ausencia_pkey PRIMARY KEY (id),
  CONSTRAINT professors_absencere_professor_id_e5612963_fk_professor FOREIGN KEY (professor_id) REFERENCES public.harpiadb_professores_professor(id)
);
CREATE TABLE public.harpiadb_professores_disponibilidade (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  dia_semana integer NOT NULL,
  turno character varying NOT NULL,
  professor_id bigint NOT NULL,
  CONSTRAINT harpiadb_professores_disponibilidade_pkey PRIMARY KEY (id),
  CONSTRAINT professors_availabil_professor_id_c7fccd61_fk_professor FOREIGN KEY (professor_id) REFERENCES public.harpiadb_professores_professor(id)
);
CREATE TABLE public.harpiadb_cursos_matriz_pre_requisitos (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  matrixcomponent_id bigint NOT NULL,
  curricularcomponent_id bigint NOT NULL,
  CONSTRAINT harpiadb_cursos_matriz_pre_requisitos_pkey PRIMARY KEY (id),
  CONSTRAINT courses_matrixcompon_matrixcomponent_id_fd61333a_fk_courses_m FOREIGN KEY (matrixcomponent_id) REFERENCES public.harpiadb_cursos_componente_matriz(id),
  CONSTRAINT courses_matrixcompon_curricularcomponent__e9acc977_fk_courses_c FOREIGN KEY (curricularcomponent_id) REFERENCES public.harpiadb_cursos_componente_curricular(id)
);
CREATE TABLE public.harpiadb_cursos_matriz_unidades (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  curriculummatrix_id bigint NOT NULL,
  unidade_id bigint NOT NULL,
  CONSTRAINT harpiadb_cursos_matriz_unidades_pkey PRIMARY KEY (id),
  CONSTRAINT courses_curriculumma_curriculummatrix_id_f02095d0_fk_courses_c FOREIGN KEY (curriculummatrix_id) REFERENCES public.harpiadb_cursos_matriz_curricular(id),
  CONSTRAINT courses_curriculumma_unidade_id_7d75068a_fk_core_unid FOREIGN KEY (unidade_id) REFERENCES public.harpiadb_nucleo_unidade(id)
);
CREATE TABLE public.harpiadb_extracurricular_pendencia (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  semestre character varying NOT NULL,
  sei_numero character varying CHECK (sei_numero IS NULL OR sei_numero::text ~ '^SEI-\d{6}/\d{6}/\d{4}$'::text) NOT VALI),
  status character varying NOT NULL,
  motivo_status_desup text NOT NULL,
  data_criacao timestamp with time zone NOT NULL,
  data_atualizacao timestamp with time zone NOT NULL,
  criado_por_id bigint,
  professor_id bigint NOT NULL,
  unidade_id bigint NOT NULL,
  CONSTRAINT harpiadb_extracurricular_pendencia_pkey PRIMARY KEY (id),
  CONSTRAINT extra_curricular_pen_criado_por_id_777e3c68_fk_accounts_ FOREIGN KEY (criado_por_id) REFERENCES public.harpiadb_contas_usuario(id),
  CONSTRAINT extra_curricular_pen_professor_id_61560e6a_fk_professor FOREIGN KEY (professor_id) REFERENCES public.harpiadb_professores_professor(id),
  CONSTRAINT extra_curricular_pen_unidade_id_460fa385_fk_core_unid FOREIGN KEY (unidade_id) REFERENCES public.harpiadb_nucleo_unidade(id)
);
CREATE TABLE public.harpiadb_extracurricular_orientacao_tcc (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  num_orientandos smallint NOT NULL CHECK (num_orientandos >= 0),
  num_orientandos_aprovados smallint CHECK (num_orientandos_aprovados >= 0),
  carga_horaria numeric NOT NULL,
  horas_aprovadas numeric,
  parecer_desup character varying NOT NULL,
  motivo_parecer text NOT NULL,
  data_atualizacao timestamp with time zone NOT NULL,
  pendencia_id bigint NOT NULL,
  bloqueado boolean NOT NULL,
  CONSTRAINT harpiadb_extracurricular_orientacao_tcc_pkey PRIMARY KEY (id),
  CONSTRAINT extra_curricular_ori_pendencia_id_1400a884_fk_extra_cur FOREIGN KEY (pendencia_id) REFERENCES public.harpiadb_extracurricular_pendencia(id)
);
CREATE TABLE public.harpiadb_extracurricular_atividade_extensionista (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  num_estudantes integer NOT NULL CHECK (num_estudantes >= 0),
  num_estudantes_aprovados integer CHECK (num_estudantes_aprovados >= 0),
  carga_horaria numeric NOT NULL,
  horas_aprovadas numeric,
  parecer_desup character varying NOT NULL,
  motivo_parecer text NOT NULL,
  data_atualizacao timestamp with time zone NOT NULL,
  pendencia_id bigint NOT NULL,
  bloqueado boolean NOT NULL,
  CONSTRAINT harpiadb_extracurricular_atividade_extensionista_pkey PRIMARY KEY (id),
  CONSTRAINT extra_curricular_ati_pendencia_id_05d8cbd2_fk_extra_cur FOREIGN KEY (pendencia_id) REFERENCES public.harpiadb_extracurricular_pendencia(id)
);
CREATE TABLE public.harpiadb_extracurricular_reducao_carga_horaria (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  motivo_reducao text NOT NULL,
  horas_reduzidas numeric NOT NULL,
  horas_aprovadas numeric,
  parecer_desup character varying NOT NULL,
  motivo_parecer text NOT NULL,
  data_atualizacao timestamp with time zone NOT NULL,
  pendencia_id bigint NOT NULL,
  bloqueado boolean NOT NULL,
  CONSTRAINT harpiadb_extracurricular_reducao_carga_horaria_pkey PRIMARY KEY (id),
  CONSTRAINT extra_curricular_red_pendencia_id_79d03128_fk_extra_cur FOREIGN KEY (pendencia_id) REFERENCES public.harpiadb_extracurricular_pendencia(id)
);
CREATE TABLE public.django_session (
  session_key character varying NOT NULL,
  session_data text NOT NULL,
  expire_date timestamp with time zone NOT NULL,
  CONSTRAINT django_session_pkey PRIMARY KEY (session_key)
);
CREATE TABLE public.harpiadb_nucleo_atalho_dashboard (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  chave character varying NOT NULL,
  ordem integer NOT NULL CHECK (ordem >= 0),
  criado_em timestamp with time zone NOT NULL,
  user_id bigint NOT NULL,
  CONSTRAINT harpiadb_nucleo_atalho_dashboard_pkey PRIMARY KEY (id),
  CONSTRAINT core_atalhodashboard_user_id_8a784412_fk_accounts_user_id FOREIGN KEY (user_id) REFERENCES public.harpiadb_contas_usuario(id)
);
CREATE TABLE public.core_auditoriaglobal_arquivo (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  email character varying NOT NULL,
  acao character varying NOT NULL,
  detalhes text NOT NULL,
  ip inet,
  user_agent text NOT NULL,
  criado_em timestamp with time zone NOT NULL,
  usuario_id bigint,
  CONSTRAINT core_auditoriaglobal_arquivo_pkey PRIMARY KEY (id)
);
CREATE TABLE public.harpiadb_contas_token_redefinicao_email (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  token_hash character varying NOT NULL UNIQUE,
  criado_em timestamp with time zone NOT NULL,
  expira_em timestamp with time zone NOT NULL,
  usado boolean NOT NULL,
  usado_em timestamp with time zone,
  solicitado_ip inet,
  solicitado_por_id bigint,
  user_id bigint NOT NULL,
  CONSTRAINT harpiadb_contas_token_redefinicao_email_pkey PRIMARY KEY (id),
  CONSTRAINT harpiadb_contas_toke_solicitado_por_id_7f2df677_fk_harpiadb_ FOREIGN KEY (solicitado_por_id) REFERENCES public.harpiadb_contas_usuario(id),
  CONSTRAINT harpiadb_contas_toke_user_id_7ddd2972_fk_harpiadb_ FOREIGN KEY (user_id) REFERENCES public.harpiadb_contas_usuario(id)
);
CREATE TABLE public.harpiadb_nucleo_erro_sistema (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  email_usuario character varying NOT NULL,
  perfil_usuario character varying NOT NULL,
  unidade_usuario character varying NOT NULL,
  criado_em timestamp with time zone NOT NULL,
  metodo character varying NOT NULL,
  caminho character varying NOT NULL,
  status_http smallint NOT NULL CHECK (status_http >= 0),
  tipo_erro character varying NOT NULL,
  mensagem text NOT NULL,
  traceback text NOT NULL,
  ip inet,
  user_agent text NOT NULL,
  request_id character varying NOT NULL,
  fingerprint character varying NOT NULL,
  usuario_id bigint,
  CONSTRAINT harpiadb_nucleo_erro_sistema_pkey PRIMARY KEY (id),
  CONSTRAINT harpiadb_nucleo_erro_usuario_id_c278e321_fk_harpiadb_ FOREIGN KEY (usuario_id) REFERENCES public.harpiadb_contas_usuario(id)
);
CREATE TABLE public.harpiadb_professores_professor_unidades (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  professor_id bigint NOT NULL,
  unidade_id bigint NOT NULL,
  CONSTRAINT harpiadb_professores_professor_unidades_pkey PRIMARY KEY (id),
  CONSTRAINT harpiadb_professores_professor_id_d304c901_fk_harpiadb_ FOREIGN KEY (professor_id) REFERENCES public.harpiadb_professores_professor(id),
  CONSTRAINT harpiadb_professores_unidade_id_048e54ef_fk_harpiadb_ FOREIGN KEY (unidade_id) REFERENCES public.harpiadb_nucleo_unidade(id)
);


9. Registro obrigatório: crie `relatoriodemodificações.md` na raiz do repositório se ele não existir. Acrescente uma nova seção com a data local da execução no formato DD/MM/AAAA, um resumo, verificações realizadas e um bloco separado para cada arquivo criado ou alterado. Não sobrescreva registros anteriores. Use este formato:

## DD/MM/AAAA — Título da alteração

### `caminho/do/arquivo`
- Tipo: criado, alterado ou removido.
- Alteração: descrição objetiva.
- Motivo: relação com o requisito.

### Verificações
- Comando executado: resultado.

Ao concluir, informe: resumo da solução, decisões de segurança, migrações, arquivos alterados, testes executados e qualquer pendência real. Não declare sucesso de teste que não tenha sido executado.
```



