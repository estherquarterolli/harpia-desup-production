-- CONFIGURAÇÃO DO TURNO DAS MATRIZES — BLOCO ÚNICO PARA O SUPABASE.
-- Valores oficiais: M = Manhã, T = Tarde, N = Noite.
-- NULL continua permitido temporariamente apenas para matrizes legadas/importadas
-- cujo turno ainda precisa ser confirmado.

DO $configurar_turno$
DECLARE
    turnos_invalidos text;
    matrizes_sem_turno integer;
    lista_sem_turno text;
BEGIN
    IF to_regclass('public.harpiadb_cursos_matriz_curricular') IS NULL THEN
        RAISE EXCEPTION 'Tabela public.harpiadb_cursos_matriz_curricular não encontrada.';
    END IF;

    ALTER TABLE public.harpiadb_cursos_matriz_curricular
        ADD COLUMN IF NOT EXISTS turno varchar(1);

    UPDATE public.harpiadb_cursos_matriz_curricular
       SET turno = upper(btrim(turno))
     WHERE turno IS NOT NULL;

    UPDATE public.harpiadb_cursos_matriz_curricular
       SET turno = NULL
     WHERE turno = '';

    SELECT string_agg(format('%s (%s registro(s))', turno, quantidade), ', ' ORDER BY turno)
      INTO turnos_invalidos
      FROM (
          SELECT turno, count(*) AS quantidade
            FROM public.harpiadb_cursos_matriz_curricular
           WHERE turno IS NOT NULL
             AND turno NOT IN ('M', 'T', 'N')
           GROUP BY turno
      ) AS invalidos;

    IF turnos_invalidos IS NOT NULL THEN
        RAISE EXCEPTION
            'Existem turnos inválidos: %. Corrija-os para M, T ou N antes de continuar.',
            turnos_invalidos;
    END IF;

    ALTER TABLE public.harpiadb_cursos_matriz_curricular
        ALTER COLUMN turno TYPE varchar(1) USING turno::varchar(1);

    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conrelid = 'public.harpiadb_cursos_matriz_curricular'::regclass
           AND conname = 'harpia_matriz_turno_valido'
    ) THEN
        ALTER TABLE public.harpiadb_cursos_matriz_curricular
            ADD CONSTRAINT harpia_matriz_turno_valido
            CHECK (turno IS NULL OR turno IN ('M', 'T', 'N'));
    END IF;

    SELECT count(*)
      INTO matrizes_sem_turno
      FROM public.harpiadb_cursos_matriz_curricular
     WHERE turno IS NULL;

    SELECT string_agg(format('#%s %s', id, COALESCE(NULLIF(nome, ''), '(sem código)')), '; ' ORDER BY id)
      INTO lista_sem_turno
      FROM public.harpiadb_cursos_matriz_curricular
     WHERE turno IS NULL;

    RAISE NOTICE
        'Turno configurado com sucesso. Matrizes legadas ainda sem turno: %.',
        matrizes_sem_turno;
    IF lista_sem_turno IS NOT NULL THEN
        RAISE NOTICE 'Preencha depois: %.', lista_sem_turno;
    END IF;
END
$configurar_turno$;
