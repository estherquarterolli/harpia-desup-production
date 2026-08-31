-- ============================================================================
-- Limpa TODAS as justificativas extracurriculares (dados de teste).
-- Rodar no SQL Editor do Supabase (porta 443).
-- ----------------------------------------------------------------------------
-- Tabelas afetadas:
--   extra_curricular_pendenciaextra          (cabecalho: professor + semestre) <- pai
--   extra_curricular_orientacaotcc           (itens de TCC)                     <- cascata
--   extra_curricular_atividadeextensionista  (itens de extensao)               <- cascata
--   extra_curricular_reducaocargahoraria     (itens de reducao de CH)          <- cascata
--
-- Os 3 tipos de item referenciam a pendencia (ON DELETE CASCADE no ORM); como as
-- FKs do Django nao tem cascade no nivel do banco, usamos TRUNCATE ... CASCADE,
-- que limpa as 4 tabelas de forma consistente. Nada mais referencia essas
-- tabelas. Professores, Unidades e demais dados NAO sao afetados.
-- ============================================================================

BEGIN;

TRUNCATE TABLE
    extra_curricular_pendenciaextra,
    extra_curricular_orientacaotcc,
    extra_curricular_atividadeextensionista,
    extra_curricular_reducaocargahoraria
  RESTART IDENTITY CASCADE;

COMMIT;

-- Confirmacao -- tudo deve dar 0:
SELECT
  (SELECT COUNT(*) FROM extra_curricular_pendenciaextra)         AS pendencias,
  (SELECT COUNT(*) FROM extra_curricular_orientacaotcc)          AS tcc,
  (SELECT COUNT(*) FROM extra_curricular_atividadeextensionista) AS extensao,
  (SELECT COUNT(*) FROM extra_curricular_reducaocargahoraria)    AS reducao;

-- (OPCIONAL) Se quiser tambem remover as notificacoes geradas por essas
-- justificativas de teste, descomente a linha abaixo (ajuste o nome da tabela
-- se necessario -- por padrao 'core_notificacao'):
-- DELETE FROM core_notificacao WHERE titulo ILIKE '%pend%extracurricular%';
