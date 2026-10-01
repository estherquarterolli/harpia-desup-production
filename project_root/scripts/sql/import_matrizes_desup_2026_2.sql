-- VERSÃO 3 — SUPABASE, SEM TABELAS TEMPORÁRIAS E SEM ON CONFLICT COMPOSTO.
-- Importação idempotente das matrizes DESUP 2026.2 e dos logins de unidade.
-- Fonte: Matrizes curriculares DESUP em 2026-2.xlsx.
-- Schema Django atual: tabelas harpiadb_*.
-- Se courses.0007 ainda não estiver no Supabase, este arquivo aplica a alteração
-- equivalente (nome_temporario + componente_curricular_id aceitando NULL).
-- Senha inicial das NOVAS contas: Faetec@123 (troca obrigatória no primeiro acesso).
-- Contas existentes não têm a senha redefinida.
-- PGE-DCX, GPO-CGO, ADS-FMO e SI-PTR só têm cabeçalho e geram matrizes vazias.
-- Tudo é transacional; unidade ausente ou ambígua cancela a execução inteira.

BEGIN;
DO $$
BEGIN
 IF to_regclass('public.harpiadb_nucleo_unidade') IS NULL OR to_regclass('public.harpiadb_cursos_curso') IS NULL OR to_regclass('public.harpiadb_cursos_curso_unidade') IS NULL OR to_regclass('public.harpiadb_cursos_matriz_curricular') IS NULL OR to_regclass('public.harpiadb_cursos_matriz_unidades') IS NULL OR to_regclass('public.harpiadb_cursos_componente_curricular') IS NULL OR to_regclass('public.harpiadb_cursos_componente_matriz') IS NULL OR to_regclass('public.harpiadb_contas_usuario') IS NULL THEN RAISE EXCEPTION 'Schema Harpia atual não encontrado. Aplique as migrations.'; END IF;
END $$;

-- Equivalente SQL idempotente da migration courses.0007.
ALTER TABLE public.harpiadb_cursos_componente_matriz
    ADD COLUMN IF NOT EXISTS nome_temporario varchar(255) NOT NULL DEFAULT '';

ALTER TABLE public.harpiadb_cursos_componente_matriz
    ALTER COLUMN componente_curricular_id DROP NOT NULL;

ALTER TABLE public.harpiadb_cursos_componente_matriz
    ALTER COLUMN nome_temporario SET DEFAULT '';

-- Mantém o histórico do Django coerente quando a migration anterior já consta
-- como aplicada. Assim um futuro `manage.py migrate` não tentará repetir o DDL.
DO $$
BEGIN
 IF to_regclass('public.django_migrations') IS NOT NULL
    AND EXISTS (
        SELECT 1 FROM public.django_migrations
         WHERE app='courses' AND name='0006_rename_tables_harpiadb_prefix'
    )
    AND NOT EXISTS (
        SELECT 1 FROM public.django_migrations
         WHERE app='courses' AND name='0007_matrixcomponent_disciplina_temporaria'
    ) THEN
  INSERT INTO public.django_migrations(app,name,applied)
  VALUES('courses','0007_matrixcomponent_disciplina_temporaria',CURRENT_TIMESTAMP);
 END IF;
END $$;

-- O executor do Supabase pode separar comandos em sessões/transações internas.
-- Por isso o estágio usa tabelas persistentes, limpas no início e removidas no fim.
DROP TABLE IF EXISTS public.harpia_stage_desup_login_2026_2;
DROP TABLE IF EXISTS public.harpia_stage_desup_componente_2026_2;
DROP TABLE IF EXISTS public.harpia_stage_desup_matriz_2026_2;
DROP TABLE IF EXISTS public.harpia_stage_desup_curso_2026_2;
DROP TABLE IF EXISTS public.harpia_stage_desup_unidade_2026_2;

CREATE TABLE public.harpia_stage_desup_unidade_2026_2(chave text PRIMARY KEY,siglas text[] NOT NULL,nomes text[] NOT NULL,unidade_id bigint);
INSERT INTO public.harpia_stage_desup_unidade_2026_2(chave,siglas,nomes) VALUES
 ('DCX',ARRAY['DUQ', 'DCX', 'FAETERJ DCX']::text[],ARRAY['FAETERJ Duque de Caxias', 'FAETERJ DUQUE DE CAXIAS', 'Duque de Caxias']::text[]),
 ('CGO',ARRAY['CAM', 'CGO', 'FAETERJ CGO']::text[],ARRAY['FAETERJ Campos dos Goytacazes', 'Campos dos Goytacazes']::text[]),
 ('FMO',ARRAY['FMO', 'FAETERJ-FMO']::text[],ARRAY['FAETERJ Fernando Mota', 'Fernando Mota']::text[]),
 ('PTR',ARRAY['PET', 'PTR', 'FAETERJ-PET']::text[],ARRAY['FAETERJ Petrópolis', 'FAETERJ Petropolis', 'Petrópolis']::text[]),
 ('ISERJ',ARRAY['ISERJ']::text[],ARRAY['ISERJ', 'Instituto de Educação do Rio de Janeiro (ISERJ)']::text[]),
 ('ISEPAM',ARRAY['ISEPAM']::text[],ARRAY['ISEPAM', 'Instituto de Educação Aldo Muylaert (ISEPAM)']::text[]),
 ('PRC',ARRAY['PAR', 'PRC', 'FAETERJ-PARACAMBI', 'FAETERJ-PCB']::text[],ARRAY['FAETERJ Paracambi', 'Paracambi']::text[]),
 ('BJI',ARRAY['BJI', 'FAETEC-BJI']::text[],ARRAY['FAETERJ Bom Jesus de Itabapoana', 'FAETEC Bom Jesus de Itabapoana', 'Bom Jesus do Itabapoana']::text[]),
 ('ITP',ARRAY['ITA', 'ITP', 'FAETEC-ITP']::text[],ARRAY['FAETERJ Itaperuna', 'FAETEC Itaperuna', 'Itaperuna']::text[]),
 ('SAP',ARRAY['PAD', 'SAP', 'FAETEC-SAdP']::text[],ARRAY['FAETERJ Santo Antônio de Pádua', 'FAETEC Santo Antônio de Pádua', 'Santo Antônio de Pádua']::text[]),
 ('TRS',ARRAY['3RIO', 'TRS', 'FAETERJ-TR']::text[],ARRAY['FAETERJ Três Rios', 'FAETEC Três Rios', 'Três Rios', 'Trê Rios']::text[]);
DO $$
DECLARE r record; n integer; rid bigint;
BEGIN
 FOR r IN SELECT * FROM public.harpia_stage_desup_unidade_2026_2 LOOP
  SELECT count(*),min(u.id) INTO n,rid FROM public.harpiadb_nucleo_unidade u WHERE EXISTS(SELECT 1 FROM unnest(r.siglas)s WHERE lower(btrim(u.sigla))=lower(btrim(s))) OR EXISTS(SELECT 1 FROM unnest(r.nomes)x WHERE lower(btrim(u.nome))=lower(btrim(x)));
  IF n=0 THEN RAISE EXCEPTION 'Unidade % não encontrada. Siglas %, nomes %',r.chave,r.siglas,r.nomes; ELSIF n>1 THEN RAISE EXCEPTION 'Unidade % ambígua: % correspondências.',r.chave,n; END IF;
  UPDATE public.harpia_stage_desup_unidade_2026_2 SET unidade_id=rid WHERE chave=r.chave;
 END LOOP;
END $$;
CREATE TABLE public.harpia_stage_desup_curso_2026_2(chave text PRIMARY KEY,nome_canonico text NOT NULL,sigla_canonica text NOT NULL,siglas text[] NOT NULL,nomes text[] NOT NULL,curso_id bigint);
INSERT INTO public.harpia_stage_desup_curso_2026_2(chave,nome_canonico,sigla_canonica,siglas,nomes) VALUES
 ('PGE','Tecnologia em Processos Gerenciais','PGER',ARRAY['PGE', 'PGER', 'TPG']::text[],ARRAY['Tecnologia em Processos Gerenciais', 'Processos Gerenciais']::text[]),
 ('GPO','Tecnologia em Gestão Portuária','GPORT',ARRAY['GPO', 'GPORT', 'TGP']::text[],ARRAY['Tecnologia em Gestão Portuária', 'Gestão Portuária']::text[]),
 ('ADS','Tecnologia em Análise e Desenvolvimento de Sistemas','ADS',ARRAY['ADS']::text[],ARRAY['Tecnologia em Análise e Desenvolvimento de Sistemas', 'Análise e Desenvolvimento de Sistemas']::text[]),
 ('SI','Tecnologia em Sistemas de Informação','SI',ARRAY['SI', 'TSI']::text[],ARRAY['Tecnologia em Sistemas de Informação', 'Tecnologia em Sistemas da Informação', 'Sistemas de Informação']::text[]),
 ('PED','Licenciatura em Pedagogia','LICPED',ARRAY['PED', 'LICPED']::text[],ARRAY['Licenciatura em Pedagogia', 'Pedagogia']::text[]),
 ('GAM','Tecnologia em Gestão Ambiental','TGA',ARRAY['GAM', 'TGA', 'GESTAMB']::text[],ARRAY['Tecnologia em Gestão Ambiental', 'Gestão Ambiental']::text[]),
 ('LOG','Tecnologia em Logística','LOG',ARRAY['LOG']::text[],ARRAY['Tecnologia em Logística', 'Logística']::text[]);
DO $$
DECLARE r record; n integer; rid bigint;
BEGIN
 FOR r IN SELECT * FROM public.harpia_stage_desup_curso_2026_2 LOOP
  SELECT count(*),min(c.id) INTO n,rid FROM public.harpiadb_cursos_curso c WHERE EXISTS(SELECT 1 FROM unnest(r.siglas)s WHERE lower(btrim(c.sigla))=lower(btrim(s)));
  IF n=0 THEN SELECT count(*),min(c.id) INTO n,rid FROM public.harpiadb_cursos_curso c WHERE EXISTS(SELECT 1 FROM unnest(r.nomes)x WHERE lower(btrim(c.nome))=lower(btrim(x))); END IF;
  IF n>1 THEN RAISE EXCEPTION 'Curso % ambíguo: % correspondências.',r.chave,n; ELSIF n=0 THEN INSERT INTO public.harpiadb_cursos_curso(nome,sigla) VALUES(r.nome_canonico,r.sigla_canonica) RETURNING id INTO rid; END IF;
  UPDATE public.harpia_stage_desup_curso_2026_2 SET curso_id=rid WHERE chave=r.chave;
 END LOOP;
END $$;
CREATE TABLE public.harpia_stage_desup_matriz_2026_2(chave text PRIMARY KEY,fonte_chave text NOT NULL,curso_chave text NOT NULL REFERENCES public.harpia_stage_desup_curso_2026_2(chave),unidade_chave text NOT NULL REFERENCES public.harpia_stage_desup_unidade_2026_2(chave),nome text NOT NULL,periodo_letivo text NOT NULL,quantidade_fonte integer NOT NULL,matriz_id bigint);
INSERT INTO public.harpia_stage_desup_matriz_2026_2(chave,fonte_chave,curso_chave,unidade_chave,nome,periodo_letivo,quantidade_fonte) VALUES
 ('pge_dcx','pge_dcx','PGE','DCX','PGE 2026.2 - DCX','2026.2',0),
 ('gpo_cgo','gpo_cgo','GPO','CGO','GPO 2026.2 - CGO','2026.2',0),
 ('ads_fmo','ads_fmo','ADS','FMO','ADS 2026.2 - FMO','2026.2',0),
 ('si_ptr','si_ptr','SI','PTR','SI 2026.2 - PTR','2026.2',0),
 ('ped_iserj','ped_iserj','PED','ISERJ','PED 2026.2 - ISERJ','2026.2',55),
 ('ped_isepam','ped_isepam','PED','ISEPAM','PED 2026.2 - ISEPAM','2026.2',54),
 ('ads_2024_prc','ads_2024_prc','ADS','PRC','ADS 2024 - PRC','2026.2',36),
 ('gam_2024_prc','gam_2024_prc','GAM','PRC','GAM 2024 - PRC','2026.2',37),
 ('gam_2022_prc','gam_2022_prc','GAM','PRC','GAM 2022 - PRC','2026.2',41),
 ('si_prc','si_prc','SI','PRC','SI 2026.2 - PRC','2026.2',33),
 ('ped_bji','ped_integrada','PED','BJI','PED 2026.2 - BJI','2026.2',49),
 ('ped_itp','ped_integrada','PED','ITP','PED 2026.2 - ITP','2026.2',49),
 ('ped_sap','ped_integrada','PED','SAP','PED 2026.2 - SAP','2026.2',49),
 ('ped_trs','ped_integrada','PED','TRS','PED 2026.2 - TRS','2026.2',49),
 ('log_trs','log_trs','LOG','TRS','LOG 2026.2 - TRS','2026.2',32);
UPDATE public.harpiadb_cursos_curso_unidade cu
   SET ativo=true
  FROM public.harpia_stage_desup_matriz_2026_2 m
  JOIN public.harpia_stage_desup_curso_2026_2 c ON c.chave=m.curso_chave
  JOIN public.harpia_stage_desup_unidade_2026_2 u ON u.chave=m.unidade_chave
 WHERE cu.curso_id=c.curso_id AND cu.unidade_id=u.unidade_id;

INSERT INTO public.harpiadb_cursos_curso_unidade(curso_id,unidade_id,ativo)
SELECT DISTINCT c.curso_id,u.unidade_id,true
  FROM public.harpia_stage_desup_matriz_2026_2 m
  JOIN public.harpia_stage_desup_curso_2026_2 c ON c.chave=m.curso_chave
  JOIN public.harpia_stage_desup_unidade_2026_2 u ON u.chave=m.unidade_chave
 WHERE NOT EXISTS (
       SELECT 1 FROM public.harpiadb_cursos_curso_unidade cu
        WHERE cu.curso_id=c.curso_id AND cu.unidade_id=u.unidade_id
 );
DO $$
DECLARE r record; n integer; rid bigint;
BEGIN
 FOR r IN SELECT m.*,c.curso_id,u.unidade_id FROM public.harpia_stage_desup_matriz_2026_2 m JOIN public.harpia_stage_desup_curso_2026_2 c ON c.chave=m.curso_chave JOIN public.harpia_stage_desup_unidade_2026_2 u ON u.chave=m.unidade_chave LOOP
  SELECT count(*),min(cm.id) INTO n,rid FROM public.harpiadb_cursos_matriz_curricular cm WHERE cm.curso_id=r.curso_id AND cm.nome=r.nome AND cm.periodo_letivo=r.periodo_letivo;
  IF n>1 THEN RAISE EXCEPTION 'Matriz % ambígua: % correspondências.',r.chave,n; ELSIF n=0 THEN INSERT INTO public.harpiadb_cursos_matriz_curricular(curso_id,nome,is_vigente,is_rascunho,criada_em,periodo_letivo,turno) VALUES(r.curso_id,r.nome,true,false,CURRENT_TIMESTAMP,r.periodo_letivo,NULL) RETURNING id INTO rid; ELSE UPDATE public.harpiadb_cursos_matriz_curricular SET is_vigente=true,is_rascunho=false WHERE id=rid; END IF;
  UPDATE public.harpia_stage_desup_matriz_2026_2 SET matriz_id=rid WHERE chave=r.chave;
  INSERT INTO public.harpiadb_cursos_matriz_unidades(curriculummatrix_id,unidade_id)
  SELECT rid,r.unidade_id
   WHERE NOT EXISTS (
    SELECT 1 FROM public.harpiadb_cursos_matriz_unidades mu
     WHERE mu.curriculummatrix_id=rid AND mu.unidade_id=r.unidade_id
   );
 END LOOP;
END $$;
CREATE TABLE public.harpia_stage_desup_componente_2026_2(fonte_chave text NOT NULL,ordem integer NOT NULL,periodo text NOT NULL,disciplina text NOT NULL,carga_horaria integer NOT NULL CHECK(carga_horaria>0),PRIMARY KEY(fonte_chave,ordem));
INSERT INTO public.harpia_stage_desup_componente_2026_2(fonte_chave,ordem,periodo,disciplina,carga_horaria) VALUES
 ('ped_iserj',1,'1º Período','Filosofia e Educação',60),
 ('ped_iserj',2,'1º Período','Fundamentos para o ensino de Língua Portuguesa',40),
 ('ped_iserj',3,'1º Período','Arte e Educação',40),
 ('ped_iserj',4,'1º Período','Introdução à Metodologia da Pesquisa',40),
 ('ped_iserj',5,'1º Período','Didática e Práticas Pedagógicas',60),
 ('ped_iserj',6,'1º Período','Movimento e Expressão Corporal',60),
 ('ped_iserj',7,'1º Período','História da Educação',60),
 ('ped_iserj',8,'2º Período','Antropologia e Educação',60),
 ('ped_iserj',9,'2º Período','Metodologias para o ensino de Língua Portuguesa',40),
 ('ped_iserj',10,'2º Período','Filosofia e Questões Contemporâneas',40),
 ('ped_iserj',11,'2º Período','Planejamento e Prática Pedagógica',40),
 ('ped_iserj',12,'2º Período','Educação e Movimentos Sociais',40),
 ('ped_iserj',13,'2º Período','Tecnologias digitais na educação',60),
 ('ped_iserj',14,'2º Período','Psicologia na Educação',60),
 ('ped_iserj',15,'2º Período','História da Educação II',60),
 ('ped_iserj',16,'3º Período','Intertextualidades: linguagem verbal e não verbal',40),
 ('ped_iserj',17,'3º Período','Currículo e Educação',40),
 ('ped_iserj',18,'3º Período','Tópicos especiais em educação não formal',40),
 ('ped_iserj',19,'3º Período','Fundamentos e Metodologias para o ensino de Matemática I',40),
 ('ped_iserj',20,'3º Período','Fundamentos e Metodologias para o ensino de Ciências Naturais I',40),
 ('ped_iserj',21,'3º Período','Fundamentos e Metodologias para o ensino de Geografia I',40),
 ('ped_iserj',22,'3º Período','Psicologia do Desenvolvimento e da Aprendizagem',60),
 ('ped_iserj',23,'3º Período','Sociologia da Educação',60),
 ('ped_iserj',24,'4º Período','Fundamentos e Metodologias para a Educação Infantil',40),
 ('ped_iserj',25,'4º Período','Introdução à literatura Infanto-Juvenil',40),
 ('ped_iserj',26,'4º Período','Fundamentos e Metodologias para o ensino de Geografia II',40),
 ('ped_iserj',27,'4º Período','Fundamentos e Metodologias para o ensino de Matemática II',40),
 ('ped_iserj',28,'4º Período','Fundamentos e Metodologias para o ensino de Ciências Naturais II',40),
 ('ped_iserj',29,'4º Período','Avaliação da Aprendizagem: questões teóricas e práticas',40),
 ('ped_iserj',30,'4º Período','Língua Brasileira de Sinais-LIBRAS',60),
 ('ped_iserj',31,'4º Período','Alfabetização I',60),
 ('ped_iserj',32,'5º Período','Fundamentos e Metodologias para o ensino de História I',40),
 ('ped_iserj',33,'5º Período','Práticas Pedagógicas na Educação Infantil',40),
 ('ped_iserj',34,'5º Período','Fundamentos e Metodologias para Educação de Jovens e Adultos',40),
 ('ped_iserj',35,'5º Período','Fundamentos e Metodologias para o Ensino Fundamental',40),
 ('ped_iserj',36,'5º Período','Fundamentos e Metodologias para Educação Especial e Inclusão',60),
 ('ped_iserj',37,'5º Período','Alfabetização II',60),
 ('ped_iserj',38,'5º Período','Estágio: Educação Infantil',100),
 ('ped_iserj',39,'6º Período','Práticas Pedagógicas na Educação Especial e Inclusão',60),
 ('ped_iserj',40,'6º Período','Práticas Pedagógicas no Ensino Fundamental',40),
 ('ped_iserj',41,'6º Período','Fundamentos e Metodologias para o ensino de História II',40),
 ('ped_iserj',42,'6º Período','Música e Educação',40),
 ('ped_iserj',43,'6º Período','Práticas Pedagógicas na Educação de Jovens e Adultos',60),
 ('ped_iserj',44,'6º Período','Pesquisa I',60),
 ('ped_iserj',45,'6º Período','Estágio: Ensino Fundamental- Regular e EJA',100),
 ('ped_iserj',46,'7º Período','Fundamentos e Metodologias para o Ensino Médio',40),
 ('ped_iserj',47,'7º Período','Tópicos especiais na Educação do Campo/Quilombola/Indígena',40),
 ('ped_iserj',48,'7º Período','Tópicos especiais na Educação a Distância',40),
 ('ped_iserj',49,'7º Período','Pesquisa II',60),
 ('ped_iserj',50,'7º Período','Fundamentos e Princípios da Gestão da Educação',40),
 ('ped_iserj',51,'7º Período','Estágio: Ensino Médio, na modalidade Normal e Educação Profissional na área de serviços e apoio escolar',100),
 ('ped_iserj',52,'8º Período','Gestão e Organização do Trabalho na Educação',60),
 ('ped_iserj',53,'8º Período','Política, Estado e Educação',60),
 ('ped_iserj',54,'8º Período','Educação das Relações Étnico-Raciais',60),
 ('ped_iserj',55,'8º Período','Estágio: Gestão',100),
 ('ped_isepam',1,'1º Período','FUNDAMENTOS DA PESQUISA PEDAGÓGICA I',60),
 ('ped_isepam',2,'1º Período','HISTÓRIA DA EDUCAÇÃO',60),
 ('ped_isepam',3,'1º Período','FILOSOFIA DA EDUCAÇÃO',60),
 ('ped_isepam',4,'1º Período','FUNDAMENTOS PSICOLÓGICOS DA EDUCAÇÃO',60),
 ('ped_isepam',5,'1º Período','PORTUGUÊS INSTRUMENTAL',60),
 ('ped_isepam',6,'1º Período','DIDÁTICA GERAL E PRÁTICA EDUCATIVA',60),
 ('ped_isepam',7,'2º Período','FUNDAMENTOS DA PESQUISA PEDAGÓGICA II',60),
 ('ped_isepam',8,'2º Período','PEDAGOGIA INSTITUCIONAL',60),
 ('ped_isepam',9,'2º Período','LEGISLAÇÃO DO ENSINO NO BRASIL',40),
 ('ped_isepam',10,'2º Período','FUNDAMENTOS SOCIOLÓGICOS DA EDUCAÇÃO',60),
 ('ped_isepam',11,'2º Período','DIDÁTICA E TEORIAS DA APRENDIZAGEM',60),
 ('ped_isepam',12,'2º Período','ELETIVA 1',40),
 ('ped_isepam',13,'3º Período','FUNDAMENTOS DA PESQUISA PEDAGÓGICA III',60),
 ('ped_isepam',14,'3º Período','FUNDAMENTOS ANTROPOLÓGICOS DA EDUCAÇÃO',60),
 ('ped_isepam',15,'3º Período','POLÍTICAS PÚBLICAS E GESTÃO DA EDUCAÇÃO BÁSICA',60),
 ('ped_isepam',16,'3º Período','TEORIAS DO CURRÍCULO',60),
 ('ped_isepam',17,'3º Período','RELAÇÕES ÉTNICO-RACIAIS',60),
 ('ped_isepam',18,'3º Período','FUNDAMENTOS E METODOLOGIAS DA EDUCAÇÃO INCLUSIVA',60),
 ('ped_isepam',19,'3º Período','LIBRAS',60),
 ('ped_isepam',20,'4º Período','PESQUISA E PRÁTICA APLICADA À EDUCAÇÃO INFANTIL',60),
 ('ped_isepam',21,'4º Período','CORPO E MOVIMENTO NA EDUCAÇÃO INFANTIL',40),
 ('ped_isepam',22,'4º Período','PROCESSOS DE APRENDIZAGEM DA LEITURA E DA ESCRITA',60),
 ('ped_isepam',23,'4º Período','PEDAGOGIA DA EDUCAÇÃO INFANTIL',60),
 ('ped_isepam',24,'4º Período','GESTÃO E ORIENTAÇÃO DO TRABALHO PEDAGÓGICO NA EDUCAÇÃO INFANTIL',60),
 ('ped_isepam',25,'4º Período','ELETIVA 2',40),
 ('ped_isepam',26,'4º Período','ESTÁGIO SUPERVISIONADO I – DOCÊNCIA NA EDUCAÇÃO INFANTIL I',100),
 ('ped_isepam',27,'5º Período','PESQUISA E PRÁTICA APLICADA AO ENSINO FUNDAMENTAL',60),
 ('ped_isepam',28,'5º Período','ARTE E EDUCAÇÃO',60),
 ('ped_isepam',29,'5º Período','LEITURA E PRODUÇÃO DE TEXTO',60),
 ('ped_isepam',30,'5º Período','FUNDAMENTOS E METODOLOGIA DO ENSINO DE LÍNGUA PORTUGUESA',60),
 ('ped_isepam',31,'5º Período','FUNDAMENTOS E MEDODOLOGIA DO ENSINO DE MATEMÁTICA',60),
 ('ped_isepam',32,'5º Período','GESTÃO E ORIENTAÇÃO DO TRABALHO PEDAGÓGICO NO ENSINO FUNDAMENTAL',60),
 ('ped_isepam',33,'5º Período','ESTÁGIO SUPERVISIONADO II – DOCÊNCIA NOS ANOS INICIAIS DO ENSINO FUNDAMENTAL',100),
 ('ped_isepam',34,'6º Período','PESQUISA E PRÁTICA APLICADA AO ENSINO MÉDIO',60),
 ('ped_isepam',35,'6º Período','FUNDAMENTOS E METODOLOGIA DO ENSINO DE GEOGRAFIA',60),
 ('ped_isepam',36,'6º Período','FUNDAMENTOS E METODOLOGIA DO ENSINO DE HISTÓRIA',60),
 ('ped_isepam',37,'6º Período','FUNDAMENTOS E METODOLOGIA DO ENSINO DE CIÊNCIAS',60),
 ('ped_isepam',38,'6º Período','EDUCAÇÃO PROFISSIONAL TECNICA DE NÍVEL MÉDIO',60),
 ('ped_isepam',39,'6º Período','GESTÃO E ORIENTAÇÃO DO TRABALHO PEDAGÓGICO NO ENSINO MÉDIO',60),
 ('ped_isepam',40,'6º Período','ELETIVA 3',40),
 ('ped_isepam',41,'6º Período','ESTÁGIO SUPERVISIONADO III – DOCÊNCIA NAS DISCIPLINAS PEDAGÓGICAS DO ENSINO MÉDIO',100),
 ('ped_isepam',42,'7º Período','PESQUISA E PRÁTICA APLICADA À GESTÃO ESCOLAR E NÃO ESCOLAR',60),
 ('ped_isepam',43,'7º Período','EDUCAÇÃO DO CAMPO, INDÍGENA E QUILOMBOLA',60),
 ('ped_isepam',44,'7º Período','FUNDAMENTOS E METODOLOGIA NA EDUCAÇÃO DE JOVENS E ADULTOS',60),
 ('ped_isepam',45,'7º Período','AVALIAÇÃO DA APRENDIZAGEM E AVALIAÇÃO INSTITUCIONAL',60),
 ('ped_isepam',46,'7º Período','GESTÃO E PLANEJAMENTO NAS INSTITUIÇÕES ESCOLARES E NÃO ESCOLARES',60),
 ('ped_isepam',47,'7º Período','ENSINO-APRENDIZAGEM A PARTIR DAS TECNOLOGIAS DIGITAIS DA INFORMAÇÃO E COMUNICAÇÃO (TDIC)',40),
 ('ped_isepam',48,'7º Período','ELETIVA 4',40),
 ('ped_isepam',49,'7º Período','ESTÁGIO SUPERVISIONADO IV – GESTÃO NAS ORGANIZAÇÕES ESCOLARES E NÃO ESCOLARES',100),
 ('ped_isepam',50,'8º Período','SEMINÁRIO DE PESQUISA',20),
 ('ped_isepam',51,'8º Período','SUPERVISÃO ESCOLAR',60),
 ('ped_isepam',52,'8º Período','ORIENTAÇÃO ESCOLAR',60),
 ('ped_isepam',53,'8º Período','FUNDAMENTOS E METODOLOGIAS DA EDUCAÇÃO À DISTÂNCIA',40),
 ('ped_isepam',54,'8º Período','ELETIVA 5',40),
 ('ads_2024_prc',1,'1º Período','Modelagem Conceitual de Dados',80),
 ('ads_2024_prc',2,'1º Período','Arquitetura de Computadores',80),
 ('ads_2024_prc',3,'1º Período','Fundamentos de Sistemas de Informação',40),
 ('ads_2024_prc',4,'1º Período','Programação Estruturada',80),
 ('ads_2024_prc',5,'1º Período','Matemática Discreta',80),
 ('ads_2024_prc',6,'1º Período','Ambiente de Edição Web',80),
 ('ads_2024_prc',7,'1º Período','Português Instrumental',40),
 ('ads_2024_prc',8,'2º Período','Modelo Relacional e Projeto Lógico de Banco de Dados',80),
 ('ads_2024_prc',9,'2º Período','Fundamentos de Engenharia de Software',80),
 ('ads_2024_prc',10,'2º Período','Modelo e Programação Orientados a Objetos',80),
 ('ads_2024_prc',11,'2º Período','Estruturas de Dados',80),
 ('ads_2024_prc',12,'2º Período','Sistemas Operacionais e Serviços de Virtualização',80),
 ('ads_2024_prc',13,'2º Período','Estatística',40),
 ('ads_2024_prc',14,'2º Período','Inglês Instrumental',40),
 ('ads_2024_prc',15,'3º Período','Desenvolvimento Frontend',80),
 ('ads_2024_prc',16,'3º Período','Interface Humano-Máquina e UI Design',40),
 ('ads_2024_prc',17,'3º Período','Metodologia da Pesquisa',40),
 ('ads_2024_prc',18,'3º Período','Técnicas de Análise e Projeto de Sistemas',80),
 ('ads_2024_prc',19,'3º Período','Redes de Computadores',80),
 ('ads_2024_prc',20,'3º Período','Métodos Ágeis',40),
 ('ads_2024_prc',21,'3º Período','Projeto de Extensão I',48),
 ('ads_2024_prc',22,'4º Período','Desenvolvimento Backend',80),
 ('ads_2024_prc',23,'4º Período','Arquitetura de Software',60),
 ('ads_2024_prc',24,'4º Período','Gestão de Processos de Negócios (BPM)',60),
 ('ads_2024_prc',25,'4º Período','Padrões de Projeto',60),
 ('ads_2024_prc',26,'4º Período','Testes de Software',60),
 ('ads_2024_prc',27,'4º Período','Qualidade de Software',40),
 ('ads_2024_prc',28,'4º Período','Projeto de Extensão II',96),
 ('ads_2024_prc',29,'5º Período','Desenvolvimento Mobile',80),
 ('ads_2024_prc',30,'5º Período','Abordagem Devops e Entregas Contínuas',80),
 ('ads_2024_prc',31,'5º Período','Empreendedorismo e Computação',40),
 ('ads_2024_prc',32,'5º Período','Gestão e Governança de TI',80),
 ('ads_2024_prc',33,'5º Período','Segurança da Informação',80),
 ('ads_2024_prc',34,'5º Período','Gestão de Projetos',80),
 ('ads_2024_prc',35,'5º Período','Direito e Legislação de Informática',40),
 ('ads_2024_prc',36,'5º Período','Projeto de Extensão III',96),
 ('gam_2024_prc',1,'1º Período','Química geral',40),
 ('gam_2024_prc',2,'1º Período','Noções de Direito',40),
 ('gam_2024_prc',3,'1º Período','Língua Portuguesa',40),
 ('gam_2024_prc',4,'1º Período','Segurança do Trabalho e Meio Ambiente',40),
 ('gam_2024_prc',5,'1º Período','Ética',40),
 ('gam_2024_prc',6,'1º Período','Educação Ambiental e Sustentabilidade',60),
 ('gam_2024_prc',7,'1º Período','Geometria aplicada ao Meio Ambiente',60),
 ('gam_2024_prc',8,'1º Período','Energia e Sustentabilidade',60),
 ('gam_2024_prc',9,'1º Período','Metodologia da Pesquisa Científica',40),
 ('gam_2024_prc',10,'2º Período','Estatística Aplicada',40),
 ('gam_2024_prc',11,'2º Período','Economia dos Recursos Naturais e Ambiente',60),
 ('gam_2024_prc',12,'2º Período','Química inorgânica',40),
 ('gam_2024_prc',13,'2º Período','Biologia e Biotecnologia Aplicada',60),
 ('gam_2024_prc',14,'2º Período','Botânica Geral',40),
 ('gam_2024_prc',15,'2º Período','Geociência ambiental',40),
 ('gam_2024_prc',16,'2º Período','Zoologia Geral',60),
 ('gam_2024_prc',17,'2º Período','Ecologia',60),
 ('gam_2024_prc',18,'2º Período','Política e Legislação Ambiental',60),
 ('gam_2024_prc',19,'2º Período','Projeto de Extensão 1',40),
 ('gam_2024_prc',20,'3º Período','Administração e Gerenciamento de Projetos',60),
 ('gam_2024_prc',21,'3º Período','Gerenciamento de Resíduos',60),
 ('gam_2024_prc',22,'3º Período','Gestão pela Qualidade de Equipes',40),
 ('gam_2024_prc',23,'3º Período','Georreferenciamento',60),
 ('gam_2024_prc',24,'3º Período','Química Analítica',60),
 ('gam_2024_prc',25,'3º Período','Microbiologia Ambiental',40),
 ('gam_2024_prc',26,'3º Período','Química Orgânica Ambiental',40),
 ('gam_2024_prc',27,'3º Período','Limnologia',40),
 ('gam_2024_prc',28,'3º Período','Controle poluição da água',60),
 ('gam_2024_prc',29,'3º Período','Projeto de Extensão 2',80),
 ('gam_2024_prc',30,'4º Período','Recuperação de Áreas degradadas',60),
 ('gam_2024_prc',31,'4º Período','Controle da Poluição Atmosférica',60),
 ('gam_2024_prc',32,'4º Período','Manejo e Gerenciamento de Bacias Hidrográficas',40),
 ('gam_2024_prc',33,'4º Período','Controle da Poluição do Solo',60),
 ('gam_2024_prc',34,'4º Período','Saúde Pública e a Questão Ambiental',60),
 ('gam_2024_prc',35,'4º Período','Licenciamento, Certificação e Auditoria Ambiental',100),
 ('gam_2024_prc',36,'4º Período','Gestão de Unidades de Conservação',40),
 ('gam_2024_prc',37,'4º Período','Projeto de Extensão 3',80),
 ('gam_2022_prc',1,'1º Período','Matemática Aplicada',60),
 ('gam_2022_prc',2,'1º Período','Física Geral',60),
 ('gam_2022_prc',3,'1º Período','Biologia Básica',60),
 ('gam_2022_prc',4,'1º Período','Química Geral',60),
 ('gam_2022_prc',5,'1º Período','Noções de Direito',40),
 ('gam_2022_prc',6,'1º Período','Ecologia Geral',40),
 ('gam_2022_prc',7,'1º Período','Língua Portuguesa',40),
 ('gam_2022_prc',8,'1º Período','Introdução à informática',40),
 ('gam_2022_prc',9,'2º Período','Estatística Aplicada',40),
 ('gam_2022_prc',10,'2º Período','Economia dos Recursos Naturais e Ambiente',60),
 ('gam_2022_prc',11,'2º Período','Desenho Técnico',40),
 ('gam_2022_prc',12,'2º Período','Química Ambiental Inorgânica',40),
 ('gam_2022_prc',13,'2º Período','Metodologia da Pesquisa Científica',60),
 ('gam_2022_prc',14,'2º Período','Botânica Geral',40),
 ('gam_2022_prc',15,'2º Período','Ética',40),
 ('gam_2022_prc',16,'2º Período','Física Ambiental e Conservação de Energia',40),
 ('gam_2022_prc',17,'2º Período','Zoologia Geral',40),
 ('gam_2022_prc',18,'3º Período','Segurança do Trabalho e Meio Ambiente',60),
 ('gam_2022_prc',19,'3º Período','Política e Legislação Ambiental',60),
 ('gam_2022_prc',20,'3º Período','Gerenciamento de Resíduos',60),
 ('gam_2022_prc',21,'3º Período','Ecologia Aplicada',60),
 ('gam_2022_prc',22,'3º Período','Química Analítica',60),
 ('gam_2022_prc',23,'3º Período','Gerenciamento de Projetos',60),
 ('gam_2022_prc',24,'3º Período','Optativa 1',40),
 ('gam_2022_prc',25,'4º Período','Controle da Poluição Atmosférica',40),
 ('gam_2022_prc',26,'4º Período','Biotecnologia Aplicada ao Meio Ambiente',40),
 ('gam_2022_prc',27,'4º Período','Recuperação de Áreas degradadas',60),
 ('gam_2022_prc',28,'4º Período','Microbiologia Ambiental',40),
 ('gam_2022_prc',29,'4º Período','Química Ambiental Orgânica',60),
 ('gam_2022_prc',30,'4º Período','Controle da Poluição do Solo',40),
 ('gam_2022_prc',31,'4º Período','Controle da Poluição das Águas',40),
 ('gam_2022_prc',32,'4º Período','Geociência Ambiental',40),
 ('gam_2022_prc',33,'4º Período','Optativa 2',40),
 ('gam_2022_prc',34,'5º Período','Gestão pela Qualidade de Equipes',40),
 ('gam_2022_prc',35,'5º Período','Saúde Pública e a Questão Ambiental',40),
 ('gam_2022_prc',36,'5º Período','Biorremediação de Solos e Aquíferos Contaminados',40),
 ('gam_2022_prc',37,'5º Período','Trabalho Conclusão de Curso',80),
 ('gam_2022_prc',38,'5º Período','Biomonitoramento de Ecossistemas Aquáticos',40),
 ('gam_2022_prc',39,'5º Período','Manejo de Bacias Hidrográficas',40),
 ('gam_2022_prc',40,'5º Período','Auditoria e Certificação Ambiental',80),
 ('gam_2022_prc',41,'5º Período','Optativa 3',40),
 ('si_prc',1,'1º Período','Algoritmos e Linguagem de Programação I',120),
 ('si_prc',2,'1º Período','Redes I',80),
 ('si_prc',3,'1º Período','Arquitetura de Computadores I',80),
 ('si_prc',4,'1º Período','Matemática Aplicada',100),
 ('si_prc',5,'1º Período','Língua Portuguesa',80),
 ('si_prc',6,'1º Período','Metodologia de Pesquisa I',40),
 ('si_prc',7,'2º Período','Algoritmos e Linguagem de Programação II',120),
 ('si_prc',8,'2º Período','Redes II',80),
 ('si_prc',9,'2º Período','Arquitetura de Computadores II',60),
 ('si_prc',10,'2º Período','Sistema Operacional',80),
 ('si_prc',11,'2º Período','Álgebra Linear',80),
 ('si_prc',12,'2º Período','Inglês Instrumental',40),
 ('si_prc',13,'2º Período','Metodologia de Pesquisa II',40),
 ('si_prc',14,'3º Período','Estrutura de Dados',40),
 ('si_prc',15,'3º Período','Internet',80),
 ('si_prc',16,'3º Período','Programação Orientada a Objeto I',120),
 ('si_prc',17,'3º Período','Gerência de Projetos de Sistemas',40),
 ('si_prc',18,'3º Período','Sistema e Projeto de Banco de Dados',120),
 ('si_prc',19,'3º Período','Estatística Aplicada',60),
 ('si_prc',20,'3º Período','Desenvolvimento Humano e Qualidade de Vida',40),
 ('si_prc',21,'4º Período','Administração Aplicada',40),
 ('si_prc',22,'4º Período','Engenharia de Software',120),
 ('si_prc',23,'4º Período','Programação Orientada a Objeto II',120),
 ('si_prc',24,'4º Período','Interface Homem Máquina',40),
 ('si_prc',25,'4º Período','Produção de Software',60),
 ('si_prc',26,'4º Período','Implementação de Banco de Dados',120),
 ('si_prc',27,'5º Período','Análise e Projeto de Sistemas',120),
 ('si_prc',28,'5º Período','Informática e Sociedade',40),
 ('si_prc',29,'5º Período','Linguagem de Programação para WEB',120),
 ('si_prc',30,'5º Período','Direito em Informática',40),
 ('si_prc',31,'5º Período','Empreendedorismo',40),
 ('si_prc',32,'5º Período','Técnicas de Relacionamento Interpessoal',40),
 ('si_prc',33,'5º Período','Tópicos Avançados',60),
 ('ped_integrada',1,'1º Período','HISTÓRIA DA EDUCAÇÃO BRASILEIRA',60),
 ('ped_integrada',2,'1º Período','LEITURA E PRODUÇÃO DE TEXTOS ACADÊMICOS',60),
 ('ped_integrada',3,'1º Período','EDUCAÇÃO PARA AS RELAÇÕES ÉTNICO-RACIAIS E DIVERSIDADES',60),
 ('ped_integrada',4,'1º Período','FUNDAMENTOS E METODOLOGIAS DA EDUCAÇÃO INCLUSIVA',60),
 ('ped_integrada',5,'1º Período','CULTURAS TECNOLÓGICAS EDUCATIVAS',60),
 ('ped_integrada',6,'1º Período','DIDÁTICA EDUCACIONAL',60),
 ('ped_integrada',7,'2º Período','FILOSOFIA DA EDUCAÇÃO',60),
 ('ped_integrada',8,'2º Período','PSICOLOGIA DA EDUCAÇÃO E DO DESENVOLVIMENTO HUMANO',60),
 ('ped_integrada',9,'2º Período','PLANEJAMENTO EDUCACIONAL',60),
 ('ped_integrada',10,'2º Período','CURRÍCULO E ORGANIZAÇÃO PEDAGÓGICA',60),
 ('ped_integrada',11,'2º Período','ESTUDO DA LÍNGUA BRASILEIRA DE SINAIS',60),
 ('ped_integrada',12,'2º Período','SOCIOLOGIA E ANTROPOLOGIA NA EDUCAÇÃO',60),
 ('ped_integrada',13,'3º Período','FUNDAMENTOS DA EDUCAÇÃO INFANTIL',60),
 ('ped_integrada',14,'3º Período','ARTE E EDUCAÇÃO',60),
 ('ped_integrada',15,'3º Período','ALFABETIZAÇÃO E LETRAMENTO',60),
 ('ped_integrada',16,'3º Período','AVALIAÇÃO DA APRENDIZAGEM E DOS PROCESSOS DE ENSINO',60),
 ('ped_integrada',17,'3º Período','PRÁTICAS PEDAGÓGICAS NA EDUCAÇÃO INCLUSIVA',60),
 ('ped_integrada',18,'3º Período','EXTENSÃO INTEGRADA I',80),
 ('ped_integrada',19,'4º Período','LEGISLAÇÃO E POLÍTICAS PÚBLICAS DA EDUCAÇÃO BÁSICA',60),
 ('ped_integrada',20,'4º Período','CORPO E MOVIMENTO',60),
 ('ped_integrada',21,'4º Período','METODOLOGIA DO ENSINO DA LÍNGUA PORTUGUESA',60),
 ('ped_integrada',22,'4º Período','PRÁTICAS PEDAGÓGICAS NA EDUCAÇÃO INFANTIL',60),
 ('ped_integrada',23,'4º Período','METODOLOGIA DO ENSINO DE HISTÓRIA E GEOGRAFIA',60),
 ('ped_integrada',24,'4º Período','EXTENSÃO INTEGRADA II',80),
 ('ped_integrada',25,'4º Período','ESTÁGIO SUPERVISIONADO- DOCÊNCIA NA EDUCAÇÃO INFANTIL',100),
 ('ped_integrada',26,'5º Período','METODOLOGIA DO ENSINO DA MATEMÁTICA',60),
 ('ped_integrada',27,'5º Período','METODOLOGIA DO ENSINO DE CIÊNCIAS E EDUCAÇÃO AMBIENTAL',60),
 ('ped_integrada',28,'5º Período','ELETIVA 1',60),
 ('ped_integrada',29,'5º Período','PRÁTICAS PEDAGÓGICAS NO ENSINO FUNDAMENTAL',60),
 ('ped_integrada',30,'5º Período','EXTENSÃO INTEGRADA III',80),
 ('ped_integrada',31,'5º Período','ESTEF- ESTÁGIO SUPERVISIONADO- DOCÊNCIA NO ENSINO FUNDAMENTAL',100),
 ('ped_integrada',32,'6º Período','FUNDAMENTOS DA ORIENTAÇÃO EDUCACIONAL',60),
 ('ped_integrada',33,'6º Período','GESTÃO E ORGANIZAÇÃO DA EDUCAÇÃO BÁSICA',60),
 ('ped_integrada',34,'6º Período','METODOLOGIA DA PESQUISA',60),
 ('ped_integrada',35,'6º Período','ELETIVA',60),
 ('ped_integrada',36,'6º Período','PRÁTICAS PEDAGÓGICAS NO ENSINO MÉDIO',60),
 ('ped_integrada',37,'6º Período','EXTENSÃO INTEGRADA IV',80),
 ('ped_integrada',38,'6º Período','ESTEM- ESTÁGIO SUPERVISIONADO- DOCÊNCIA NO ENSINO MÉDIO',60),
 ('ped_integrada',39,'7º Período','FUNDAMENTOS DA SUPERVISÃO EDUCACIONAL',60),
 ('ped_integrada',40,'7º Período','EDUCAÇÃO PROFISSIONAL E TRABALHO',60),
 ('ped_integrada',41,'7º Período','EDUCAÇÃO QUILOMBOLA, INDÍGENA E NO CAMPO',60),
 ('ped_integrada',42,'7º Período','TCC I',60),
 ('ped_integrada',43,'7º Período','ELETIVA 2',60),
 ('ped_integrada',44,'7º Período','PRÁTICAS PEDAGÓGICAS EM CONTEXTOS NÃO ESCOLARES',60),
 ('ped_integrada',45,'7º Período','ESTOE- ESTÁGIO SUPERVISIONADO- GESTÃO DE ORGANIZAÇÕES ESCOLARES E NÃO-ESCOLARES',80),
 ('ped_integrada',46,'8º Período','FUNDAMENTOS DA INSPEÇÃO ESCOLAR',60),
 ('ped_integrada',47,'8º Período','TCC II',60),
 ('ped_integrada',48,'8º Período','ELETIVA 3',60),
 ('ped_integrada',49,'8º Período','EJA83- PRÁTICAS PEDAGÓGICAS NA EJA',60),
 ('log_trs',1,'1º Período','Fundamentos de Gestão e Logística',60),
 ('log_trs',2,'1º Período','Introdução a Economia',60),
 ('log_trs',3,'1º Período','Matemática Básica',60),
 ('log_trs',4,'1º Período','Gestão de Pessoas',60),
 ('log_trs',5,'1º Período','Planejamento de Marketing',60),
 ('log_trs',6,'1º Período','Metodologia da Pesquisa Científica',60),
 ('log_trs',7,'1º Período','Saúde e Segurança no trabalho',60),
 ('log_trs',8,'1º Período','Ética e Responsabilidade Empresarial',60),
 ('log_trs',9,'2º Período','Sistemas de armazenagem e movimentação de cargas',60),
 ('log_trs',10,'2º Período','Estatística',60),
 ('log_trs',11,'2º Período','Gestão da qualidade',60),
 ('log_trs',12,'2º Período','Planejamento e Controle de Produção Integrado a Logística',60),
 ('log_trs',13,'2º Período','Gestão Sustentável',60),
 ('log_trs',14,'2º Período','Gestão de Projetos',60),
 ('log_trs',15,'2º Período','Empreendedorismo e Inovação',60),
 ('log_trs',16,'2º Período','Optativa 1',60),
 ('log_trs',17,'3º Período','Administração de Materiais',60),
 ('log_trs',18,'3º Período','Gestão da Cadeia de Suprimentos',60),
 ('log_trs',19,'3º Período','Transportes na logística',60),
 ('log_trs',20,'3º Período','Gestão de Custos logísticos',60),
 ('log_trs',21,'3º Período','Matemática Financeira',60),
 ('log_trs',22,'3º Período','Logística Internacional',60),
 ('log_trs',23,'3º Período','Projeto Integrador I',60),
 ('log_trs',24,'3º Período','Projeto de Extensão 1',90),
 ('log_trs',25,'4º Período','Transporte de Passageiros',60),
 ('log_trs',26,'4º Período','Comércio Exterior',60),
 ('log_trs',27,'4º Período','Sistemas de Informação Logístico',60),
 ('log_trs',28,'4º Período','Logística Reversa',60),
 ('log_trs',29,'4º Período','Comportamento Organizacional',60),
 ('log_trs',30,'4º Período','Optativa 2',60),
 ('log_trs',31,'4º Período','Projeto Integrador II',60),
 ('log_trs',32,'4º Período','Projeto de Extensão 2',100);
WITH s AS(SELECT m.matriz_id,x.periodo,x.disciplina,x.carga_horaria FROM public.harpia_stage_desup_componente_2026_2 x JOIN public.harpia_stage_desup_matriz_2026_2 m ON m.fonte_chave=x.fonte_chave)
UPDATE public.harpiadb_cursos_componente_matriz mc SET carga_horaria=s.carga_horaria,creditos=(s.carga_horaria/20)::smallint,carga_horaria_semanal=round(s.carga_horaria::numeric/20,2) FROM s WHERE mc.matriz_id=s.matriz_id AND lower(btrim(mc.periodo))=lower(btrim(s.periodo)) AND lower(btrim(COALESCE((SELECT cc.nome FROM public.harpiadb_cursos_componente_curricular cc WHERE cc.id=mc.componente_curricular_id),mc.nome_temporario)))=lower(btrim(s.disciplina));
WITH s AS(SELECT m.matriz_id,x.* FROM public.harpia_stage_desup_componente_2026_2 x JOIN public.harpia_stage_desup_matriz_2026_2 m ON m.fonte_chave=x.fonte_chave),r AS(SELECT s.*,COALESCE((SELECT CASE WHEN count(*)=1 THEN min(cc.id) END FROM public.harpiadb_cursos_componente_curricular cc WHERE lower(btrim(cc.nome))=lower(btrim(s.disciplina)) AND cc.carga_horaria_padrao=s.carga_horaria),(SELECT CASE WHEN count(*)=1 THEN min(cc.id) END FROM public.harpiadb_cursos_componente_curricular cc WHERE lower(btrim(cc.nome))=lower(btrim(s.disciplina)))) componente_id FROM s)
INSERT INTO public.harpiadb_cursos_componente_matriz(matriz_id,componente_curricular_id,nome_temporario,codigo,periodo,carga_horaria,creditos,docente_id,compartilhado,curso_compartilhado_id,carga_horaria_semanal,distribuicao_semanal,status,observacoes)
SELECT r.matriz_id,r.componente_id,CASE WHEN r.componente_id IS NULL THEN r.disciplina ELSE '' END,COALESCE((SELECT cc.codigo FROM public.harpiadb_cursos_componente_curricular cc WHERE cc.id=r.componente_id),''),r.periodo,r.carga_horaria,(r.carga_horaria/20)::smallint,NULL,false,NULL,round(r.carga_horaria::numeric/20,2),'','SEM_PROFESSOR','' FROM r WHERE NOT EXISTS(SELECT 1 FROM public.harpiadb_cursos_componente_matriz mc WHERE mc.matriz_id=r.matriz_id AND lower(btrim(mc.periodo))=lower(btrim(r.periodo)) AND lower(btrim(COALESCE((SELECT cc.nome FROM public.harpiadb_cursos_componente_curricular cc WHERE cc.id=mc.componente_curricular_id),mc.nome_temporario)))=lower(btrim(r.disciplina)));
CREATE TABLE public.harpia_stage_desup_login_2026_2(unidade_chave text NOT NULL REFERENCES public.harpia_stage_desup_unidade_2026_2(chave),email text PRIMARY KEY,password_hash text NOT NULL,first_name text NOT NULL,last_name text NOT NULL);
INSERT INTO public.harpia_stage_desup_login_2026_2(unidade_chave,email,password_hash,first_name,last_name) VALUES
 ('DCX','direcao@faeterj-dcx.faetec.rj.gov.br','pbkdf2_sha256$1200000$iamocBgkIEJijEhYuPfx3m$plHm3yY8yYhQXaguUqlAMvUmFTVLtjhQwjmca8xoJAQ=','Coordenação','DCX'),
 ('CGO','direcao@faeterj-cgo.faetec.rj.gov.br','pbkdf2_sha256$1200000$iamocBgkIEJijEhYuPfx3m$plHm3yY8yYhQXaguUqlAMvUmFTVLtjhQwjmca8xoJAQ=','Coordenação','CGO'),
 ('FMO','direcao@faeterj-rio.edu.br','pbkdf2_sha256$1200000$iamocBgkIEJijEhYuPfx3m$plHm3yY8yYhQXaguUqlAMvUmFTVLtjhQwjmca8xoJAQ=','Coordenação','FMO'),
 ('PTR','direcao@faeterj-petropolis.edu.br','pbkdf2_sha256$1200000$iamocBgkIEJijEhYuPfx3m$plHm3yY8yYhQXaguUqlAMvUmFTVLtjhQwjmca8xoJAQ=','Coordenação','PTR'),
 ('ISERJ','direcao.dg@iserj.edu.br','pbkdf2_sha256$1200000$iamocBgkIEJijEhYuPfx3m$plHm3yY8yYhQXaguUqlAMvUmFTVLtjhQwjmca8xoJAQ=','Coordenação','ISERJ'),
 ('ISEPAM','direcao@isepam.edu.br','pbkdf2_sha256$1200000$iamocBgkIEJijEhYuPfx3m$plHm3yY8yYhQXaguUqlAMvUmFTVLtjhQwjmca8xoJAQ=','Coordenação','ISEPAM'),
 ('PRC','direcao@faeterj-prc.faetec.rj.gov.br','pbkdf2_sha256$1200000$iamocBgkIEJijEhYuPfx3m$plHm3yY8yYhQXaguUqlAMvUmFTVLtjhQwjmca8xoJAQ=','Coordenação','PRC'),
 ('BJI','direcao@faeterj-bji.faetec.rj.gov.br','pbkdf2_sha256$1200000$iamocBgkIEJijEhYuPfx3m$plHm3yY8yYhQXaguUqlAMvUmFTVLtjhQwjmca8xoJAQ=','Coordenação','BJI'),
 ('ITP','direcao@faeterj-itp.faetec.rj.gov.br','pbkdf2_sha256$1200000$iamocBgkIEJijEhYuPfx3m$plHm3yY8yYhQXaguUqlAMvUmFTVLtjhQwjmca8xoJAQ=','Coordenação','ITP'),
 ('SAP','direcao@faeterj-sap.faetec.rj.gov.br','pbkdf2_sha256$1200000$iamocBgkIEJijEhYuPfx3m$plHm3yY8yYhQXaguUqlAMvUmFTVLtjhQwjmca8xoJAQ=','Coordenação','SAP'),
 ('TRS','direcao@faeterj-trs.faetec.rj.gov.br','pbkdf2_sha256$1200000$iamocBgkIEJijEhYuPfx3m$plHm3yY8yYhQXaguUqlAMvUmFTVLtjhQwjmca8xoJAQ=','Coordenação','TRS');
DO $$
DECLARE r record; n integer; uid bigint;
BEGIN
 FOR r IN SELECT l.*,u.unidade_id FROM public.harpia_stage_desup_login_2026_2 l JOIN public.harpia_stage_desup_unidade_2026_2 u ON u.chave=l.unidade_chave LOOP
  SELECT count(*),min(id) INTO n,uid FROM public.harpiadb_contas_usuario WHERE lower(email)=lower(r.email);
  IF n>1 THEN RAISE EXCEPTION 'Mais de uma conta para %.',r.email; ELSIF n=1 THEN UPDATE public.harpiadb_contas_usuario SET perfil='COORDENADOR_UNIDADE',unidade_id=r.unidade_id,is_active=true WHERE id=uid;
  ELSE IF EXISTS(SELECT 1 FROM public.harpiadb_contas_usuario WHERE lower(username)=lower(r.email)) THEN RAISE EXCEPTION 'Username % já pertence a outra conta.',r.email; END IF; INSERT INTO public.harpiadb_contas_usuario(password,last_login,is_superuser,username,first_name,last_name,is_staff,is_active,date_joined,email,perfil,unidade_id,dados_submetidos,forcar_troca_senha) VALUES(r.password_hash,NULL,false,r.email,r.first_name,r.last_name,false,true,CURRENT_TIMESTAMP,r.email,'COORDENADOR_UNIDADE',r.unidade_id,false,true); END IF;
 END LOOP;
END $$;
DO $$
DECLARE missing integer;
BEGIN
 SELECT count(*) INTO missing FROM public.harpia_stage_desup_componente_2026_2 x JOIN public.harpia_stage_desup_matriz_2026_2 m ON m.fonte_chave=x.fonte_chave WHERE NOT EXISTS(SELECT 1 FROM public.harpiadb_cursos_componente_matriz mc WHERE mc.matriz_id=m.matriz_id AND lower(btrim(mc.periodo))=lower(btrim(x.periodo)) AND lower(btrim(COALESCE((SELECT cc.nome FROM public.harpiadb_cursos_componente_curricular cc WHERE cc.id=mc.componente_curricular_id),mc.nome_temporario)))=lower(btrim(x.disciplina)));
 IF missing<>0 THEN RAISE EXCEPTION 'Falha: % componentes ausentes após carga.',missing; END IF;
 IF EXISTS(SELECT 1 FROM public.harpia_stage_desup_matriz_2026_2 WHERE matriz_id IS NULL) THEN RAISE EXCEPTION 'Falha: matriz sem ID.'; END IF;
 IF EXISTS(SELECT 1 FROM public.harpia_stage_desup_login_2026_2 l JOIN public.harpia_stage_desup_unidade_2026_2 u ON u.chave=l.unidade_chave WHERE NOT EXISTS(SELECT 1 FROM public.harpiadb_contas_usuario au WHERE lower(au.email)=lower(l.email) AND au.perfil='COORDENADOR_UNIDADE' AND au.unidade_id=u.unidade_id AND au.is_active=true)) THEN RAISE EXCEPTION 'Falha: login não associado.'; END IF;
END $$;
SELECT (SELECT count(*) FROM public.harpia_stage_desup_matriz_2026_2) matrizes_processadas,(SELECT count(*) FROM public.harpia_stage_desup_matriz_2026_2 WHERE quantidade_fonte=0) matrizes_vazias,(SELECT sum(quantidade_fonte) FROM public.harpia_stage_desup_matriz_2026_2) componentes_processados,(SELECT count(*) FROM public.harpia_stage_desup_login_2026_2) logins_processados;

DROP TABLE IF EXISTS public.harpia_stage_desup_login_2026_2;
DROP TABLE IF EXISTS public.harpia_stage_desup_componente_2026_2;
DROP TABLE IF EXISTS public.harpia_stage_desup_matriz_2026_2;
DROP TABLE IF EXISTS public.harpia_stage_desup_curso_2026_2;
DROP TABLE IF EXISTS public.harpia_stage_desup_unidade_2026_2;

COMMIT;

-- Resultado final visível no painel Results do Supabase.
SELECT 15 AS matrizes_processadas,
       4 AS matrizes_vazias,
       484 AS componentes_processados,
       11 AS logins_processados;
