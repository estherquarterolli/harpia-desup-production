-- ATENÇÃO: rode antes verificar_professores_lista_2.sql para checar se alguém da lista é professor de verdade.
-- Remove do sistema os 199 servidores da lista informada (somente estes IDs funcionais)
-- e tudo que estiver ligado a eles. PostgreSQL.
-- É um único comando (tudo ou nada), para funcionar no editor SQL do Supabase.

WITH prof AS (
  SELECT id FROM harpiadb_professores_professor
  WHERE "ID_FUNCIONAL" IN (
'42629497', '5787734', '50370170', '44669526', '42495814', '20845677', '50351206', '5788374', '44606176', 
'41997166', '41475127', '44618867', '44160399', '41391080', '44232748', '44618808', '41997182', '41987446', 
'5788390', '44141491', '5788404', '39840182', '5789451', '5789460', '44126794', '44669208', '50352652', 
'41987470', '42096294', '50358189', '42638712', '51433311', '44118309', '44670664', '5788323', '20870876', 
'44669828', '5788900', '20754078', '50362410', '20948425', '50370790', '50351362', '50373021', '51242290', 
'44266553', '41475275', '39839966', '50362127', '44669836', '41766288', '51236818', '42593816', '44669283', 
'44669291', '8763950', '41987993', '41988094', '44309724', '20825366', '44662912', '51361396', '44669313', 
'44669518', '44669593', '44118759', '5786940', '50360108', '50352644', '44618778', '44266324', '44607695', 
'44246269', '41475542', '41475941', '20953968', '44309740', '5786622', '51296071', '20758219', '43342043', 
'42092434', '44618883', '5788102', '14350262', '42629080', '51366274', '20824785', '5788510', '51432986', 
'50205161', '44120460', '44176007', '44115172', '50352130', '42196574', '20872976', '44068859', '44607733', 
'44669623', '5788935', '5788838', '44129270', '44669631', '20852967', '50351575', '41766474', '43842313', 
'50352148', '43854141', '44165293', '51245930', '5788293', '41988248', '5788536', '5788048', '41766490', 
'5788552', '50370189', '41814827', '50352121', '32157738', '42056616', '44164050', '51274779', '41987691', 
'5788951', '44120850', '44618824', '44564430', '20841434', '20718284', '42640458', '50368508', '44115750', 
'44312920', '44119275', '50368338', '50370634', '5786789', '39895947', '39838145', '8767734', '51243423', 
'44003439', '44114478', '20782543', '41475445', '20726457', '50352504', '5788625', '50358324', '50351974', 
'42537614', '39849252', '50358766', '41988019', '44607687', '50352091', '5786967', '50352067', '41766970', 
'51237245', '20921748', '41988302', '44669372', '44315511', '42056624', '5788650', '44669640', '50358979', 
'20958846', '44119534', '50352016', '20715048', '44323697', '44618700', '42123518', '44626304', '44618697', 
'44246447', '50359169', '41475216', '50351737', '20882866', '44669380', '41988159', '44618727', '42016193', 
'50373005', '20717180', '50356674', '41474040', '20923058', '44606095', '41987985', '41997328', '41988280', 
'20852843'
  )
),
pend AS (
  SELECT id FROM harpiadb_extracurricular_pendencia WHERE professor_id IN (SELECT id FROM prof)
),
d01 AS (DELETE FROM harpiadb_professores_professor_unidades WHERE professor_id IN (SELECT id FROM prof)),
d02 AS (DELETE FROM harpiadb_professores_professor_cursos   WHERE professor_id IN (SELECT id FROM prof)),
d03 AS (DELETE FROM harpiadb_professores_disponibilidade    WHERE professor_id IN (SELECT id FROM prof)),
d04 AS (DELETE FROM harpiadb_professores_ausencia           WHERE professor_id IN (SELECT id FROM prof)),
d05 AS (DELETE FROM harpiadb_extracurricular_orientacao_tcc          WHERE pendencia_id IN (SELECT id FROM pend)),
d06 AS (DELETE FROM harpiadb_extracurricular_atividade_extensionista WHERE pendencia_id IN (SELECT id FROM pend)),
d07 AS (DELETE FROM harpiadb_extracurricular_reducao_carga_horaria   WHERE pendencia_id IN (SELECT id FROM pend)),
d08 AS (DELETE FROM harpiadb_extracurricular_licenca                 WHERE pendencia_id IN (SELECT id FROM pend)),
d09 AS (DELETE FROM harpiadb_extracurricular_pendencia               WHERE id IN (SELECT id FROM pend)),
d10 AS (DELETE FROM harpiadb_nucleo_ocupacao_diretiva            WHERE professor_id IN (SELECT id FROM prof)),
d11 AS (DELETE FROM harpiadb_nucleo_atividade_estagio_supervisao WHERE professor_id IN (SELECT id FROM prof)),
d12 AS (DELETE FROM harpiadb_nucleo_readaptacao_professor        WHERE professor_id IN (SELECT id FROM prof)),
d13 AS (DELETE FROM harpiadb_nucleo_excecao_carga_unidade        WHERE professor_id IN (SELECT id FROM prof)),
d14 AS (DELETE FROM harpiadb_alocacoes_solicitacao_rat           WHERE professor_id IN (SELECT id FROM prof)),
u15 AS (UPDATE harpiadb_alocacoes_alocacao_turma_docente     SET docente_id   = NULL WHERE docente_id   IN (SELECT id FROM prof)),
u16 AS (UPDATE harpiadb_nucleo_solicitacao_professor_externo SET professor_id = NULL WHERE professor_id IN (SELECT id FROM prof))
DELETE FROM harpiadb_professores_professor
WHERE id IN (SELECT id FROM prof)
RETURNING id, "ID_FUNCIONAL", rh_nome;
