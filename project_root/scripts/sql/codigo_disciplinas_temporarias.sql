-- Dá código TEMP-<id> às disciplinas temporárias (sem catálogo) que estão sem código.
-- Seguro para rodar mais de uma vez: só toca em linhas com código vazio.
UPDATE public.harpiadb_cursos_componente_matriz
   SET codigo = 'TEMP-' || lpad(id::text, 5, '0')
 WHERE componente_curricular_id IS NULL
   AND COALESCE(codigo, '') = '';
