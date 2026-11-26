-- Normaliza o período dos componentes curriculares.
--
-- Escopo intencional: somente harpiadb_cursos_componente_matriz.periodo.
-- Campos chamados "semestre" que guardam o período letivo (por exemplo,
-- 2026.1 e 2026.2) não devem ser alterados.
--
-- Compatível com PostgreSQL/Supabase e seguro para executar mais de uma vez.

BEGIN;

UPDATE public.harpiadb_cursos_componente_matriz
SET periodo = regexp_replace(
    periodo,
    '^[[:space:]]*([1-8])[[:space:]]*(º|°|o)?[[:space:]]*(semestre|per[ií]odo)[[:space:]]*$',
    '\1º Período',
    'i'
)
WHERE periodo ~* '^[[:space:]]*[1-8][[:space:]]*(º|°|o)?[[:space:]]*(semestre|per[ií]odo)[[:space:]]*$'
  AND periodo IS DISTINCT FROM regexp_replace(
      periodo,
      '^[[:space:]]*([1-8])[[:space:]]*(º|°|o)?[[:space:]]*(semestre|per[ií]odo)[[:space:]]*$',
      '\1º Período',
      'i'
  );

COMMIT;

-- Conferência: esta consulta deve retornar apenas "1º Período" a
-- "8º Período" (além de vazio, caso existam componentes incompletos).
SELECT periodo, COUNT(*) AS quantidade
FROM public.harpiadb_cursos_componente_matriz
GROUP BY periodo
ORDER BY periodo;
