-- RODE ESTE ARQUIVO ANTES de remover_professores_lista_2.sql. Não apaga nada.
-- Lista, entre os 199 IDs da remoção, quem parece ser PROFESSOR de verdade, ou seja, quem:
--   * tem cargo de docência/pedagógico (PROFESSOR, ORIENTADOR, SUPERVISOR, TÉCNICO SUPERIOR, SECRETÁRIO), ou
--   * já está alocado como docente em alguma turma, ou
--   * tem pendência extracurricular, ocupação em cargo diretivo ou disponibilidade cadastrada.
-- Resultado vazio = nenhum dos IDs parece professor; pode seguir com a remoção.

WITH prof AS (
  SELECT p.id, p."ID_FUNCIONAL", p.rh_nome, p.cargo_origem, tc.nome AS cargo
  FROM harpiadb_professores_professor p
  LEFT JOIN harpiadb_professores_tipo_contrato tc ON tc.id = p.tipo_contrato_id
  WHERE p."ID_FUNCIONAL" IN (
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
)
SELECT
  prof."ID_FUNCIONAL", prof.rh_nome, prof.cargo, prof.cargo_origem,
  (SELECT COUNT(*) FROM harpiadb_alocacoes_alocacao_turma_docente a WHERE a.docente_id = prof.id) AS turmas_alocadas,
  (SELECT COUNT(*) FROM harpiadb_extracurricular_pendencia x WHERE x.professor_id = prof.id) AS pendencias,
  (SELECT COUNT(*) FROM harpiadb_nucleo_ocupacao_diretiva o WHERE o.professor_id = prof.id) AS cargos_diretivos,
  (SELECT COUNT(*) FROM harpiadb_professores_disponibilidade d WHERE d.professor_id = prof.id) AS disponibilidades
FROM prof
WHERE COALESCE(prof.cargo, '') ~* '(professor|orientador|supervisor|t[eé]cnico superior|secret[aá]rio)'
   OR COALESCE(prof.cargo_origem, '') ~* '(professor|orientador|supervisor|t[eé]cnico superior|secret[aá]rio)'
   OR EXISTS (SELECT 1 FROM harpiadb_alocacoes_alocacao_turma_docente a WHERE a.docente_id = prof.id)
   OR EXISTS (SELECT 1 FROM harpiadb_extracurricular_pendencia x WHERE x.professor_id = prof.id)
   OR EXISTS (SELECT 1 FROM harpiadb_nucleo_ocupacao_diretiva o WHERE o.professor_id = prof.id)
   OR EXISTS (SELECT 1 FROM harpiadb_professores_disponibilidade d WHERE d.professor_id = prof.id)
ORDER BY prof.rh_nome;
