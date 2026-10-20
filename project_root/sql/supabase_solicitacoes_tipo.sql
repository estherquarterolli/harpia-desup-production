-- Supabase / PostgreSQL — "Solicitações" (antes "Solicitações externas").
-- Equivale às migrations:
--   core.0007_simplificar_nomes_cargo_diretivo   (só textos/rótulos: NENHUMA alteração de esquema)
--   core.0008_solicitacao_tipo_cessao_cadastro
--
-- O QUE MUDA NO BANCO (tabela harpiadb_nucleo_solicitacao_professor_externo):
--   + coluna "tipo"           varchar(10) NOT NULL — 'CESSAO' (padrão, todas as linhas atuais)
--                             ou 'CADASTRO' (pedido de cadastro de professor novo)
--   + coluna "professor_nome" varchar(255) NOT NULL — nome informado no pedido de cadastro
--   ~ "professor_id"          passa a aceitar NULL (no cadastro o professor ainda não existe)
--   ~ "unidade_origem_id"     passa a aceitar NULL (no cadastro não há unidade de origem)
--   + índice em "tipo" (filtro da tela)
-- Os dados existentes NÃO são alterados: ficam como 'CESSAO', com professor e origem preservados.
--
-- A redução de carga determinada pela DESUP NÃO exige SQL: o sistema passa a descontar
-- a coluna harpiadb_nucleo_ocupacao_diretiva.carga_reducao_horas (já existente) do limite em sala.
--
-- Use ESTE script OU "python manage.py migrate" — não os dois. É idempotente: pode rodar de novo.
-- Recomenda-se backup antes.

BEGIN;

SET LOCAL lock_timeout = '10s';

-- 1) Tipo da solicitação ---------------------------------------------------------
ALTER TABLE public.harpiadb_nucleo_solicitacao_professor_externo
    ADD COLUMN IF NOT EXISTS tipo varchar(10) NOT NULL DEFAULT 'CESSAO';
ALTER TABLE public.harpiadb_nucleo_solicitacao_professor_externo
    ALTER COLUMN tipo DROP DEFAULT;

CREATE INDEX IF NOT EXISTS harpiadb_nucleo_solicitacao_professor_externo_tipo_idx
    ON public.harpiadb_nucleo_solicitacao_professor_externo (tipo);
CREATE INDEX IF NOT EXISTS harpiadb_nucleo_solicitacao_professor_externo_tipo_like
    ON public.harpiadb_nucleo_solicitacao_professor_externo (tipo varchar_pattern_ops);

-- 2) Nome informado (pedidos de cadastro) ----------------------------------------
ALTER TABLE public.harpiadb_nucleo_solicitacao_professor_externo
    ADD COLUMN IF NOT EXISTS professor_nome varchar(255) NOT NULL DEFAULT '';
ALTER TABLE public.harpiadb_nucleo_solicitacao_professor_externo
    ALTER COLUMN professor_nome DROP DEFAULT;

-- 3) Professor e unidade de origem passam a ser opcionais ------------------------
ALTER TABLE public.harpiadb_nucleo_solicitacao_professor_externo
    ALTER COLUMN professor_id DROP NOT NULL;
ALTER TABLE public.harpiadb_nucleo_solicitacao_professor_externo
    ALTER COLUMN unidade_origem_id DROP NOT NULL;

-- 4) Registro das migrations do Django -------------------------------------------
INSERT INTO public.django_migrations (app, name, applied)
SELECT v.app, v.name, now()
FROM (VALUES
    ('core', '0007_simplificar_nomes_cargo_diretivo'),
    ('core', '0008_solicitacao_tipo_cessao_cadastro')
) AS v (app, name)
WHERE NOT EXISTS (
    SELECT 1 FROM public.django_migrations d WHERE d.app = v.app AND d.name = v.name
);

COMMIT;
