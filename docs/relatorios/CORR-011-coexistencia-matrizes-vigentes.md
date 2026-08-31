# Relatório — CORR-011: remover auto-arquivamento (matrizes coexistem por turno)

**Data:** 2026-07-16 · **Commit:** feito pelo usuário (nada commitado).

## 1. O que era
Ao **publicar** uma matriz, o sistema arquivava **todas** as outras vigentes do **mesmo curso**
(`is_vigente=False`). Assim, duplicar uma matriz numa mesma unidade jogava a de origem para
Histórico automaticamente. Desejado: matrizes do mesmo curso (ex.: turnos diferentes) **coexistem**
como vigentes; arquivamento só manual (CORR-012) ou em massa na virada de semestre.

## 2. O que mudou
- `apps/courses/views.py` — `CurriculumMatrixFormsetMixin.form_valid` (ramo de publicação):
  **removido** o bloco de auto-arquivamento
  (`CurriculumMatrix.objects.filter(curso=..., is_vigente=True).exclude(pk=...).update(is_vigente=False)`).
  Publicar/duplicar agora nasce `is_vigente=True` sem arquivar nenhuma outra. Comentário no código
  apontando CORR-011/012 + virada.
- `apps/courses/tests.py` — classe `MatrixCoexistenciaVigentesTests` (2 testes): publicar 2ª matriz
  do mesmo curso não arquiva a de origem; as duas ficam vigentes (`count() == 2`). POST real no
  CreateView com formset.

## 3. Funcionamento / verificação
- Publicar/duplicar não afeta o status das demais matrizes do curso.
- `Professor.ch_alocada` passa a poder somar horas de 2 matrizes vigentes do mesmo curso
  (comportamento esperado com a coexistência; irmãs não são `compartilhado`).
- **Testes:** `apps.courses` 13/13 verdes; `apps.professors` sem testes; `manage.py check` limpo.

## 4. Guard não implementado (registrado)
Impedir "2 vigentes do mesmo curso+turno+unidade" depende de `turno` virar campo de verdade
(hoje inerte). Fica para a feature **CORR-013** (turnos por curso).

## 5. Rollback
```bash
git checkout -- project_root/apps/courses/views.py project_root/apps/courses/tests.py
```
Sem migration. Nada commitado.
