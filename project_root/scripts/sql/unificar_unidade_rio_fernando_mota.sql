-- Unifica a unidade "Rio de Janeiro" (FAETERJ Rio) na unidade "Fernando Mota":
-- as duas são a mesma unidade. Tudo que apontava para a unidade Rio passa a
-- apontar para Fernando Mota (a que a DESUP definiu como oficial em
-- sync_unidades_cursos) e a unidade Rio é removida.
--
-- Cobre: professores (principal + vínculos), usuários, matrizes, cursos da unidade
-- (CourseUnit), alocações consolidadas, pendências extra, janelas de entrega e
-- notificações. Professores alocados em disciplinas não mudam: `docente` na matriz
-- aponta para o professor, não para a unidade.
--
-- Seguro para rodar mais de uma vez (a 2ª execução só avisa que não há o que unir).
-- Aborta sem alterar nada se não achar exatamente uma unidade de cada lado.
--
-- Como usar no Supabase (SQL Editor):
--   1) rode só o bloco "PRÉVIA" e confira as duas unidades encontradas;
--   2) rode o bloco "UNIFICAÇÃO" (é uma transação única: tudo ou nada).

-- ───────────── PRÉVIA (somente leitura) ─────────────
SELECT id, nome, sigla, status
FROM harpiadb_nucleo_unidade
WHERE (nome ILIKE '%fernando mota%')
   OR nome ILIKE 'FAETERJ Rio de Janeiro'
ORDER BY nome;

-- ───────────── UNIFICAÇÃO ─────────────
BEGIN;

DO $$
DECLARE
    v_keep BIGINT;   -- Fernando Mota (fica)
    v_drop BIGINT;   -- Rio (é absorvida e removida)
    n_keep INT;
    n_drop INT;
BEGIN
    SELECT count(*), min(id) INTO n_keep, v_keep
    FROM harpiadb_nucleo_unidade
    WHERE nome ILIKE '%fernando mota%';

    SELECT count(*), min(id) INTO n_drop, v_drop
    FROM harpiadb_nucleo_unidade
    WHERE btrim(nome) ILIKE 'FAETERJ Rio de Janeiro';  -- nome exato (não confunde com o ISERJ)

    IF n_drop = 0 THEN
        RAISE NOTICE 'Unidade Rio não encontrada: nada a unificar.';
        RETURN;
    END IF;
    IF n_keep <> 1 OR n_drop <> 1 THEN
        RAISE EXCEPTION 'Esperava 1 unidade Fernando Mota e 1 Rio; achei % e %. Confira a PRÉVIA.', n_keep, n_drop;
    END IF;
    IF v_keep = v_drop THEN
        RAISE EXCEPTION 'Rio e Fernando Mota são o mesmo registro.';
    END IF;

    -- 1) Cursos da unidade (CourseUnit): se Fernando Mota já tem o curso, as
    --    referências do CourseUnit do Rio migram para o dele; senão, o próprio
    --    CourseUnit é reapontado.
    --    1a) alocações consolidadas: descarta as que colidiriam (curso, semestre, turno)
    DELETE FROM harpiadb_alocacoes_alocacao_curricular a
    USING harpiadb_cursos_curso_unidade cu_drop, harpiadb_cursos_curso_unidade cu_keep
    WHERE a.curso_id = cu_drop.id
      AND cu_drop.unidade_id = v_drop
      AND cu_keep.unidade_id = v_keep
      AND cu_keep.curso_id = cu_drop.curso_id
      AND EXISTS (
          SELECT 1 FROM harpiadb_alocacoes_alocacao_curricular b
          WHERE b.curso_id = cu_keep.id AND b.semestre = a.semestre AND b.turno = a.turno
      );

    UPDATE harpiadb_alocacoes_alocacao_curricular a
    SET curso_id = cu_keep.id
    FROM harpiadb_cursos_curso_unidade cu_drop, harpiadb_cursos_curso_unidade cu_keep
    WHERE a.curso_id = cu_drop.id
      AND cu_drop.unidade_id = v_drop
      AND cu_keep.unidade_id = v_keep
      AND cu_keep.curso_id = cu_drop.curso_id;

    --    1b) componentes compartilhados com o curso da unidade Rio
    UPDATE harpiadb_cursos_componente_matriz m
    SET curso_compartilhado_id = cu_keep.id
    FROM harpiadb_cursos_curso_unidade cu_drop, harpiadb_cursos_curso_unidade cu_keep
    WHERE m.curso_compartilhado_id = cu_drop.id
      AND cu_drop.unidade_id = v_drop
      AND cu_keep.unidade_id = v_keep
      AND cu_keep.curso_id = cu_drop.curso_id;

    --    1c) CourseUnit duplicado do Rio é removido; os demais são reapontados
    DELETE FROM harpiadb_cursos_curso_unidade cu_drop
    USING harpiadb_cursos_curso_unidade cu_keep
    WHERE cu_drop.unidade_id = v_drop
      AND cu_keep.unidade_id = v_keep
      AND cu_keep.curso_id = cu_drop.curso_id;

    UPDATE harpiadb_cursos_curso_unidade SET unidade_id = v_keep WHERE unidade_id = v_drop;

    -- 2) Alocações consolidadas restantes da unidade
    UPDATE harpiadb_alocacoes_alocacao_curricular SET unidade_id = v_keep WHERE unidade_id = v_drop;

    -- 3) Matrizes (M2M): reaponta sem duplicar o par (matriz, unidade)
    DELETE FROM harpiadb_cursos_matriz_unidades d
    WHERE d.unidade_id = v_drop
      AND EXISTS (SELECT 1 FROM harpiadb_cursos_matriz_unidades k
                  WHERE k.unidade_id = v_keep AND k.curriculummatrix_id = d.curriculummatrix_id);
    UPDATE harpiadb_cursos_matriz_unidades SET unidade_id = v_keep WHERE unidade_id = v_drop;

    -- 4) Professores: vínculo M2M (sem duplicar) e unidade principal
    DELETE FROM harpiadb_professores_professor_unidades d
    WHERE d.unidade_id = v_drop
      AND EXISTS (SELECT 1 FROM harpiadb_professores_professor_unidades k
                  WHERE k.unidade_id = v_keep AND k.professor_id = d.professor_id);
    UPDATE harpiadb_professores_professor_unidades SET unidade_id = v_keep WHERE unidade_id = v_drop;
    UPDATE harpiadb_professores_professor SET unidade_principal_id = v_keep WHERE unidade_principal_id = v_drop;

    -- 5) Usuários, pendências extra, janelas de entrega e notificações
    UPDATE harpiadb_contas_usuario SET unidade_id = v_keep WHERE unidade_id = v_drop;
    UPDATE harpiadb_extracurricular_pendencia SET unidade_id = v_keep WHERE unidade_id = v_drop;
    UPDATE harpiadb_nucleo_janela_entrega SET unidade_id = v_keep WHERE unidade_id = v_drop;
    UPDATE harpiadb_nucleo_notificacao SET unidade_destino_id = v_keep WHERE unidade_destino_id = v_drop;

    -- 6) Remove a unidade Rio (já sem nenhuma referência)
    DELETE FROM harpiadb_nucleo_unidade WHERE id = v_drop;

    RAISE NOTICE 'Unidade % (Rio) unificada em % (Fernando Mota).', v_drop, v_keep;
END $$;

COMMIT;

-- ───────────── CONFERÊNCIA ─────────────
-- Deve listar só Fernando Mota, com os professores/matrizes/cursos somados.
SELECT u.id, u.nome, u.sigla,
       (SELECT count(*) FROM harpiadb_professores_professor_unidades pu WHERE pu.unidade_id = u.id) AS professores,
       (SELECT count(*) FROM harpiadb_cursos_matriz_unidades mu WHERE mu.unidade_id = u.id)         AS matrizes,
       (SELECT count(*) FROM harpiadb_cursos_curso_unidade cu WHERE cu.unidade_id = u.id)           AS cursos
FROM harpiadb_nucleo_unidade u
WHERE u.nome ILIKE '%fernando mota%' OR btrim(u.nome) ILIKE 'FAETERJ Rio de Janeiro';
