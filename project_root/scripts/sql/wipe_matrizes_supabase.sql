-- ============================================================================
-- Apaga SOMENTE as Matrizes Curriculares (Supabase). Preserva os Componentes.
-- Rodar no SQL Editor do dashboard (porta 443).
-- ----------------------------------------------------------------------------
-- TRUNCATE ... CASCADE em courses_curriculummatrix limpa a matriz e tudo que
-- depende dela, SEM tocar em courses_curricularcomponent (que e "pai" de
-- courses_matrixcomponent, nao "filho" -- o CASCADE so desce, nunca sobe):
--   courses_curriculummatrix            (matrizes)                        <- alvo
--   courses_matrixcomponent             (componentes da matriz + docente) <- cascata
--   courses_classgroup                  (turmas)                          <- cascata
--   courses_curriculummatrix_unidades   (M2M matriz<->unidade)            <- cascata
--
-- >> Os 507 Componentes Curriculares (courses_curricularcomponent) ficam intactos. <<
-- Professores, Cursos, Unidades e vinculos CourseUnit tambem NAO sao afetados.
--
-- O TRUNCATE ... CASCADE emite NOTICEs listando as tabelas limpas em cascata --
-- confira na saida que courses_curricularcomponent NAO aparece na lista.
-- ============================================================================

BEGIN;

TRUNCATE TABLE courses_curriculummatrix RESTART IDENTITY CASCADE;

COMMIT;

-- Confirmacao -- matrizes/turmas = 0, componentes preservados (esperado: 507):
SELECT
  (SELECT COUNT(*) FROM courses_curriculummatrix)    AS matrizes,
  (SELECT COUNT(*) FROM courses_matrixcomponent)     AS componentes_da_matriz,
  (SELECT COUNT(*) FROM courses_classgroup)          AS turmas,
  (SELECT COUNT(*) FROM courses_curricularcomponent) AS componentes_curriculares;
