-- Supabase / PostgreSQL — campo "Área de atuação" do professor.
-- Equivale à migration professors.0012_professor_area_atuacao.
--
-- Pode ser executado mais de uma vez: não recria a coluna nem duplica o
-- registro da migration. Se o deploy do Vercel já rodou "migrate", este script
-- apenas confirma o estado e não altera nada.

BEGIN;

SET LOCAL lock_timeout = '10s';

ALTER TABLE public.harpiadb_professores_professor
    ADD COLUMN IF NOT EXISTS area_atuacao varchar(150) NOT NULL DEFAULT '';

-- O Django não usa default no banco; o valor padrão vem da aplicação.
ALTER TABLE public.harpiadb_professores_professor
    ALTER COLUMN area_atuacao DROP DEFAULT;

INSERT INTO public.django_migrations (app, name, applied)
SELECT 'professors', '0012_professor_area_atuacao', now()
WHERE NOT EXISTS (
    SELECT 1 FROM public.django_migrations
    WHERE app = 'professors' AND name = '0012_professor_area_atuacao'
);

COMMIT;
