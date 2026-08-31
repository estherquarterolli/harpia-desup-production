-- ============================================================================
-- Preenche o campo `creditos` dos Componentes Curriculares (Supabase).
-- Regra: creditos = CH total / 20 (divisao INTEIRA, igual ao MatrixComponent).
-- Rodar no SQL Editor do dashboard (porta 443).
-- ----------------------------------------------------------------------------
-- Os componentes foram semeados com creditos = 0; este UPDATE grava o valor
-- derivado da carga horaria. Em Postgres, "inteiro / inteiro" ja e divisao
-- inteira (trunca), entao carga_horaria_padrao / 20 == floor(CH/20):
--   40->2  60->3  80->4  100->5  120->6  25->1  20->1  50->2 ...
--
-- Idempotente: so atualiza linhas cujo creditos esteja diferente do esperado.
-- ============================================================================

BEGIN;

UPDATE courses_curricularcomponent
   SET creditos = carga_horaria_padrao / 20
 WHERE creditos IS DISTINCT FROM (carga_horaria_padrao / 20);

COMMIT;

-- Confirmacao -- distribuicao de creditos x carga horaria:
SELECT creditos,
       MIN(carga_horaria_padrao) AS ch_min,
       MAX(carga_horaria_padrao) AS ch_max,
       COUNT(*)                  AS qtd
  FROM courses_curricularcomponent
 GROUP BY creditos
 ORDER BY creditos;
