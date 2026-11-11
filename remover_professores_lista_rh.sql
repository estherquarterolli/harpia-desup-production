-- Remove do sistema os 217 servidores da lista (Auxiliares de Serviços Gerais)
-- e tudo que estiver ligado a eles. PostgreSQL.
-- É um único comando (tudo ou nada), para funcionar no editor SQL do Supabase.

WITH prof AS (
  SELECT id FROM harpiadb_professores_professor
  WHERE "ID_FUNCIONAL" IN (
'20766351', '20746695', '41475585', '5775949', '20827520', '41474112', '42167434', '42165717', '41474120', 
'42658411', '20775920', '6184855', '5789419', '42078717', '42123526', '41766121', '42537002', '20853882', 
'20784686', '20863543', '40209083', '41475615', '41475623', '20746270', '41997204', '42538017', '41474171', 
'42123470', '41475631', '20873360', '32266340', '41474210', '41474236', '41475577', '41766202', '41766210', 
'42165768', '42639700', '20747527', '41474228', '20797435', '41474066', '20875576', '5789303', '41988167', 
'41475640', '20867735', '41766245', '20904070', '20823983', '41474244', '20931743', '42537711', '42658454', 
'41475674', '20886829', '41766253', '41987535', '20862962', '20862660', '41997239', '42506123', '41766296', 
'41474309', '41474317', '41766962', '42537401', '41473663', '42056632', '41766334', '20899653', '5788188', 
'42521980', '42614953', '41766369', '42638747', '41766393', '20929935', '41997255', '42145376', '42659051', 
'42056470', '20849443', '41473698', '5788196', '5788200', '41474422', '41474449', '20900147', '5788307', 
'5789400', '42593921', '42639352', '20883781', '41474473', '41474481', '42165865', '41474490', '20781555', 
'20864876', '20893442', '41474538', '41474546', '41474554', '20807937', '20878249', '41987608', '41474589', 
'41474597', '5789397', '20945949', '42658950', '41474600', '42638801', '20789459', '20907648', '5789168', 
'42638836', '42658560', '5679370', '40217914', '41474635', '41474643', '42537797', '20789157', '41474660', 
'20877188', '42639638', '42668298', '41987888', '41858450', '20863659', '41474686', '41474708', '42078660', 
'41474732', '41766547', '20946074', '42196493', '41474767', '41766555', '41475755', '42016177', '41766571', 
'5787637', '41474783', '41474791', '10732160', '41474805', '20966717', '20803850', '42629969', '41474813', 
'20915780', '20892985', '41987713', '20756054', '20778759', '20883366', '20894066', '42537568', '41474090', 
'5788234', '41391217', '41766644', '41474864', '5789028', '42123615', '20935706', '20893256', '41474880', 
'42538009', '20888961', '20891644', '20772548', '20774869', '41987756', '41473817', '42145341', '42507227', 
'20896085', '42144612', '42629136', '20811233', '41475208', '20931441', '42629276', '41474961', '20877439', 
'41475917', '41988230', '41814835', '41997301', '20853351', '41474996', '41475003', '41475011', '20956380', 
'20883668', '41475810', '41987934', '41852729', '41475496', '20928343', '41475054', '40211860', '20803443', 
'41766830', '20772955', '20958137', '42537860', '42629403', '41473442', '20868120', '20908229', '41766857', 
'20904975'
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
