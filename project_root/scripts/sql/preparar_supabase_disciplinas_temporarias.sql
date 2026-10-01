-- Alinha o Supabase com a funcionalidade de disciplinas temporárias.
-- Idempotente: pode ser executado mais de uma vez.
-- Não cria tabelas tmp_desup_*; elas pertenciam apenas ao importador antigo.

BEGIN;

DO $$
BEGIN
    IF to_regclass('public.harpiadb_cursos_componente_matriz') IS NULL THEN
        RAISE EXCEPTION 'Tabela public.harpiadb_cursos_componente_matriz não encontrada.';
    END IF;
END
$$;

-- Campo usado quando a disciplina ainda não existe no catálogo global.
ALTER TABLE public.harpiadb_cursos_componente_matriz
    ADD COLUMN IF NOT EXISTS nome_temporario varchar(255);

UPDATE public.harpiadb_cursos_componente_matriz
   SET nome_temporario = ''
 WHERE nome_temporario IS NULL;

ALTER TABLE public.harpiadb_cursos_componente_matriz
    ALTER COLUMN nome_temporario SET DEFAULT '',
    ALTER COLUMN nome_temporario SET NOT NULL;

-- Uma linha de matriz pode apontar para o catálogo OU usar nome temporário.
ALTER TABLE public.harpiadb_cursos_componente_matriz
    ALTER COLUMN componente_curricular_id DROP NOT NULL;

-- Impede linhas sem disciplina e também o preenchimento simultâneo das duas fontes.
ALTER TABLE public.harpiadb_cursos_componente_matriz
    DROP CONSTRAINT IF EXISTS harpia_componente_matriz_fonte_disciplina_ck;

ALTER TABLE public.harpiadb_cursos_componente_matriz
    ADD CONSTRAINT harpia_componente_matriz_fonte_disciplina_ck
    CHECK (
        (componente_curricular_id IS NOT NULL AND btrim(nome_temporario) = '')
        OR
        (componente_curricular_id IS NULL AND btrim(nome_temporario) <> '')
    ) NOT VALID;

-- Valida antes de confirmar. Se existirem linhas inconsistentes, tudo sofre rollback.
ALTER TABLE public.harpiadb_cursos_componente_matriz
    VALIDATE CONSTRAINT harpia_componente_matriz_fonte_disciplina_ck;

-- Mantém o histórico do Django coerente com o schema já aplicado.
INSERT INTO public.django_migrations (app, name, applied)
SELECT 'courses', '0007_matrixcomponent_disciplina_temporaria', CURRENT_TIMESTAMP
WHERE NOT EXISTS (
    SELECT 1
      FROM public.django_migrations
     WHERE app = 'courses'
       AND name = '0007_matrixcomponent_disciplina_temporaria'
);

COMMIT;

-- Resultado esperado:
-- nome_temporario       | NO  | ''::character varying
-- componente_curricular_id | YES | null
SELECT
    column_name,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'harpiadb_cursos_componente_matriz'
  AND column_name IN ('nome_temporario', 'componente_curricular_id')
ORDER BY column_name;

SELECT app, name, applied
FROM public.django_migrations
WHERE app = 'courses'
  AND name = '0007_matrixcomponent_disciplina_temporaria';
