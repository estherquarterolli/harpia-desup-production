-- ============================================================================
-- Correção do "meta CH" (max_class_hours) dos tipos de contrato no Supabase
-- ============================================================================
-- Regra de negócio: o limite de horas em sala (meta que conta para a alocação)
-- é METADE do regime de trabalho:  40h -> 20h  |  20h -> 10h.
-- O dump antigo trazia valores errados (40h com 32, 20h com 16).
--
-- Como rodar: cole este arquivo no SQL Editor do dashboard do Supabase
-- (Database > SQL Editor) e execute. Funciona via HTTPS/443 — não precisa da
-- porta de banco 5432/6543 (que está bloqueada na rede da unidade).
--
-- É idempotente: rodar mais de uma vez não causa efeito colateral. Não depende
-- de IDs nem de nomes específicos — só corrige quem viola a regra.
-- ============================================================================

-- 1) ANTES: veja o estado atual (rode este SELECT primeiro para conferir)
SELECT id, nome, max_total_hours, max_class_hours,
       (max_total_hours / 2)                       AS meta_correta,
       (max_class_hours = max_total_hours / 2)     AS ja_correto
FROM   professors_contracttype
ORDER  BY id;

-- 2) CORREÇÃO: aplica meta = regime/2 em todo contrato que estiver fora da regra.
--    (divisão inteira no Postgres: 40/2 = 20, 20/2 = 10)
UPDATE professors_contracttype
SET    max_class_hours = max_total_hours / 2
WHERE  max_total_hours IS NOT NULL
  AND  max_total_hours > 0
  AND  max_class_hours IS DISTINCT FROM (max_total_hours / 2);

-- 3) DEPOIS: confirme que todos ficaram corretos (coluna ja_correto = true)
SELECT id, nome, max_total_hours, max_class_hours,
       (max_class_hours = max_total_hours / 2) AS ja_correto
FROM   professors_contracttype
ORDER  BY id;

-- ----------------------------------------------------------------------------
-- ALTERNATIVA (só se a coluna max_total_hours no Supabase estiver vazia/errada
-- e o UPDATE acima não pegar): correção explícita pelos valores conhecidos.
-- Descomente e ajuste se precisar.
-- ----------------------------------------------------------------------------
-- UPDATE professors_contracttype SET max_class_hours = 20 WHERE max_class_hours = 32; -- 40h
-- UPDATE professors_contracttype SET max_class_hours = 10 WHERE max_class_hours = 16; -- 20h
