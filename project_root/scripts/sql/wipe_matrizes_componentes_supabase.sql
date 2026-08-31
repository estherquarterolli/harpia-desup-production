-- ============================================================================
-- Apaga TODAS as matrizes curriculares e TODOS os componentes curriculares.
-- Alvo: Supabase (producao). Rodar no SQL Editor do dashboard (porta 443).
-- ----------------------------------------------------------------------------
-- Motivo: as matrizes serao recriadas do zero pelo coord. DESUP e os
-- componentes curriculares serao reimportados depois (fora deste script).
--
-- POR QUE TRUNCATE ... CASCADE (e nao DELETE):
--   As FKs geradas pelo Django NAO tem "ON DELETE CASCADE" no nivel do banco
--   (o cascade e emulado no ORM, em Python). Um DELETE cru precisaria apagar
--   cada tabela-filha na ordem exata, incluindo as tabelas M2M -- fragil se o
--   schema do Supabase estiver defasado. TRUNCATE ... CASCADE limpa as duas
--   tabelas-pai e TODAS as dependentes automaticamente, seja qual for a versao
--   do schema. Tabelas afetadas:
--     courses_curriculummatrix                    (matrizes)              <- pai
--     courses_curricularcomponent                 (componentes)           <- pai
--     courses_matrixcomponent                     (componentes da matriz +
--                                                  vinculo de docente)     <- cascata
--     courses_classgroup                          (turmas)                <- cascata
--     courses_curriculummatrix_unidades           (M2M matriz<->unidade)  <- cascata
--     courses_curricularcomponent_pre_requisitos  (M2M pre-requisitos)    <- cascata
--     courses_matrixcomponent_pre_requisitos      (M2M pre-requisitos)    <- cascata
--
-- >> ATENCAO <<  Isto tambem apaga TODAS as Turmas e TODAS as alocacoes de
--   docentes aos componentes (o vinculo "docente" vive dentro de
--   courses_matrixcomponent). Professores, Cursos, Unidades e vinculos
--   CourseUnit NAO sao afetados.
--
-- O TRUNCATE ... CASCADE emite NOTICEs listando as tabelas que foram limpas em
-- cascata -- confira essa lista na saida do SQL Editor para ter certeza de que
-- so as tabelas acima foram atingidas.
-- ============================================================================

-- (1) OPCIONAL -- veja o que existe hoje ANTES de apagar:
SELECT
  (SELECT COUNT(*) FROM courses_curriculummatrix)    AS matrizes,
  (SELECT COUNT(*) FROM courses_matrixcomponent)     AS componentes_da_matriz,
  (SELECT COUNT(*) FROM courses_classgroup)          AS turmas,
  (SELECT COUNT(*) FROM courses_curricularcomponent) AS componentes_curriculares;

-- (2) Apaga tudo, de forma atomica (se algo falhar, nada e alterado):
BEGIN;

TRUNCATE TABLE
    courses_curriculummatrix,
    courses_curricularcomponent
  RESTART IDENTITY CASCADE;

COMMIT;

-- (3) Confirmacao -- deve retornar 0 em todas as colunas:
SELECT
  (SELECT COUNT(*) FROM courses_curriculummatrix)    AS matrizes,
  (SELECT COUNT(*) FROM courses_matrixcomponent)     AS componentes_da_matriz,
  (SELECT COUNT(*) FROM courses_classgroup)          AS turmas,
  (SELECT COUNT(*) FROM courses_curricularcomponent) AS componentes_curriculares;
