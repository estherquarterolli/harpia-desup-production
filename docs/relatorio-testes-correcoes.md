# Relatório de testes — correções aplicadas (status 🟢 Corrigido)

- **Data de execução:** 2026-07-16
- **Branch:** `fix/CORR-012`
- **Comando base:** `python manage.py test <app|classe> --verbosity=2`
- **Settings:** `config.settings.development` · **DB de teste:** `test_harpia_db` (criado/destruído pelo runner)
- **Escopo:** apenas os itens marcados 🟢 no `docs/checklist_correcao.md` (CORR-001, CORR-008, CORR-011, CORR-012). Itens 🔴/📄 **não** foram tocados.

## Resumo geral

| Item | App / Classe de teste | Testes | Resultado |
|------|-----------------------|:------:|:---------:|
| CORR-001 | `apps.extra_curricular` → `DecisaoDesupTests` (+`ExtraCurricularApprovedTests`) | 15 | ✅ 15/15 |
| CORR-008 | `apps.courses` → `MatrixPermissaoUnidadeTests` | 5 | ✅ 5/5 |
| CORR-011 | `apps.courses` → `MatrixCoexistenciaVigentesTests` | 2 | ✅ 2/2 |
| CORR-012 | `apps.courses` → `MatrixArquivarReativarTests` | 5 | ✅ 5/5 |

- `apps.courses` (3 classes): **12/12** verde em 36,2 s.
- `apps.extra_curricular` + `apps.professors`: **15/15** verde em 41,2 s (`apps.professors` sem testes próprios).
- `manage.py check`: **0 issues**.

---

## CORR-001 — `ch_justificada` soma horas aprovadas (não solicitadas)

**Correção validada:** `Professor.ch_justificada` passa a somar `ch_aprovada` (via `PendenciaExtra.ch_total_justificada`), escopada pelo semestre atual.

**Contexto comum (`setUp` de `DecisaoDesupTests`):** 1 Unidade `UD`, 1 `ContractType`, 1 `Professor` "Docente Decisão", 1 `PendenciaExtra` no semestre atual com status `ENVIADO`, usuários `DESUP` e `COORDENADOR_UNIDADE`.

### Teste regressão direta — `test_ch_justificada_usa_horas_aprovadas_nao_solicitadas`
| | |
|---|---|
| **Input** | Pendência marcada `APROVADO`. `OrientacaoTCC` com `num_orientandos=8` (solicitado → `carga_horaria = 4.0h`, teto TCC), `num_orientandos_aprovados=2` (aprovado DESUP → `ch_aprovada = 1.0h`), `parecer_desup=APROVADO`. |
| **Ação** | Lê `professor.ch_justificada` após `refresh_from_db()`. |
| **Output esperado** | `ch_justificada == 1.0` (horas **aprovadas**), não `4.0` (solicitadas). |
| **Resultado** | ✅ ok |

### Escopo por semestre — `test_justificativa_semestre_anterior_nao_conta_no_professor`
| | |
|---|---|
| **Input** | `PendenciaExtra` `APROVADO` em **semestre anterior** + `OrientacaoTCC` 4/4 aprovada. |
| **Output esperado** | `pend.ch_total_justificada > 0` (tem CH própria), porém `professor.ch_justificada == 0.0` (semestre anterior não conta). |
| **Resultado** | ✅ ok |

### Contraprova — `test_justificativa_semestre_atual_conta_no_professor`
| | |
|---|---|
| **Input** | Pendência do setUp (semestre atual) marcada `APROVADO` + `OrientacaoTCC` 4/4 aprovada. |
| **Output esperado** | `professor.ch_justificada > 0.0`. |
| **Resultado** | ✅ ok |

### Não soma indeferido — `test_ch_total_justificada_nao_soma_indeferido`
| | |
|---|---|
| **Input** | Dois `OrientacaoTCC` na mesma pendência: um `APROVADO`, um `INDEFERIDO`; roda `sincronizar_status_pendencia`. |
| **Output esperado** | Status vira `INDEFERIDO` ⇒ `pend.ch_total_justificada == 0.0`. |
| **Resultado** | ✅ ok |

> Demais testes da classe (`DecisaoDesupTests`) e `ExtraCurricularApprovedTests` cobrem cálculo de horas aprovadas TCC/Extensão, finalização/reabertura de parecer, prioridade de indeferido e permissão DESUP-only — todos verdes, garantindo que a mudança de tipo/soma da CORR-001 não regrediu o fluxo de parecer.

---

## CORR-008 — Unidade não edita matriz e não vê rascunhos (só DESUP)

**Correção validada:** edição exige DESUP/superuser; lista e detalhe excluem `is_rascunho=True` para perfis não-DESUP.

**Contexto comum (`setUp`):** Unidade `UP`, Curso `CP`, `matriz_vigente` (vigente, publicada) e `matriz_rascunho` (rascunho) — ambas ligadas à unidade; usuários `DESUP` e `COORDENADOR_UNIDADE` (da unidade).

| Teste | Input (login + ação) | Output esperado | Resultado |
|-------|----------------------|-----------------|:---------:|
| `test_unidade_nao_edita_matriz` | coord → `GET matrix_update(rascunho)` | `302` redirect p/ `matrix_list` | ✅ |
| `test_desup_edita_rascunho` | desup → `GET matrix_update(rascunho)` | `200` | ✅ |
| `test_unidade_nao_ve_rascunho_na_lista` | coord → `GET matrix_list` e `matrix_list?status=rascunho` | vigente **presente**, rascunho **ausente** em ambos (filtro forçado não vaza) | ✅ |
| `test_unidade_nao_ve_rascunho_no_detalhe` | coord → `GET matrix_detail(rascunho)` | `404` | ✅ |
| `test_desup_ve_rascunho` | desup → `matrix_list?status=rascunho` + `matrix_detail(rascunho)` | rascunho na lista; detalhe `200` | ✅ |

---

## CORR-011 — Duplicar/publicar não arquiva as demais do mesmo curso

**Correção validada:** removido o auto-arquivamento por curso no `form_valid`; matrizes do mesmo curso coexistem como vigentes.

**Contexto comum (`setUp`):** Unidade `UC`, Curso `CC`, `CurricularComponent` `CC001`, `matriz_origem` "MC-CC-Manha" já vigente/publicada; usuário `DESUP` logado.
**Ação padrão:** `POST courses:matrix_create` publicando nova matriz do mesmo curso (form + formset de 1 componente válido, sem flag de rascunho ⇒ `is_vigente=True`).

| Teste | Input | Output esperado | Resultado |
|-------|-------|-----------------|:---------:|
| `test_publicar_nova_nao_arquiva_a_de_origem` | POST publica "MC-CC-Noite" | `302`; `matriz_origem.is_vigente` permanece `True`; nova matriz `is_vigente=True`, `is_rascunho=False` | ✅ |
| `test_duas_vigentes_do_mesmo_curso_coexistem` | POST publica "MC-CC-Noite" | `CurriculumMatrix.filter(curso=CC, is_vigente=True).count() == 2` | ✅ |

---

## CORR-012 — Ação manual de arquivar/reativar matriz (DESUP-only)

**Correção validada:** views `ArquivarMatrizView`/`ReativarMatrizView` (POST, DESUP-only), com auditoria e sem tocar nas demais do curso.

**Contexto comum (`setUp`):** Unidade `UA`, Curso `CA`, três matrizes — `vigente` (MC-CA-V), `historico` (MC-CA-H, arquivada), `rascunho` (MC-CA-R); usuários `DESUP` e `COORDENADOR_UNIDADE`.

| Teste | Input (login + ação) | Output esperado | Resultado |
|-------|----------------------|-----------------|:---------:|
| `test_desup_arquiva_vigente` | desup → `POST matrix_archive(vigente)` | `302`; `is_vigente=False`, `is_rascunho=False`; registro `AuditoriaGlobal(acao='MATRIZ_ARQUIVADA')` | ✅ |
| `test_arquivar_rascunho_bloqueado` | desup → `POST matrix_archive(rascunho)` | rascunho intacto (`is_rascunho` continua `True`) | ✅ |
| `test_unidade_nao_arquiva` | coord → `POST matrix_archive(vigente)` | `302` p/ `matrix_list`; `vigente.is_vigente` continua `True` | ✅ |
| `test_desup_reativa_historico` | desup → `POST matrix_reactivate(historico)` | `302`; `is_vigente=True`, `is_rascunho=False`; `AuditoriaGlobal(acao='MATRIZ_REATIVADA')` | ✅ |
| `test_reativar_nao_arquiva_as_demais_do_curso` | desup → `POST matrix_reactivate(historico)` | `vigente` continua vigente; `count(curso=CA, is_vigente=True) == 2` (coerência com CORR-011) | ✅ |

---

## Observações

- Itens **não testados** (fora de escopo, status ≠ 🟢): CORR-002, 003, 004, 005, 006, 007, 009, 010 (🔴) e CORR-013 (📄 planejado). Nenhum arquivo desses itens foi tocado.
- Execução foi somente leitura/execução de testes — **nenhuma alteração de código** foi feita para este relatório.
- Testes em `apps.professors` inexistentes (0) — a cobertura da CORR-001 vive em `apps.extra_curricular`.
