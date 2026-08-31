# CORR-004 — HTTP 500 no parecer DESUP: `ch_aprovada` retornava `float` e `Decimal`

- **Área:** Extracurricular / Parecer DESUP
- **Prioridade:** 🅐 Alta
- **Data:** 2026-07-16
- **Escopo de arquivos:** `apps/extra_curricular/` (models.py, forms.py, tests.py). Sem alterações em
  `apps/core/`, `config/`, `templates/`. Sem commit (feito só pelo usuário).

## Bug / relato

Na fase de testes, o Coord (DESUP) **aprovou** uma orientação de TCC de um professor e, em seguida,
tentou **indeferir** uma atividade extensionista do **mesmo professor**. Resultado: tela branca
"Ocorreu um problema / Não foi possível processar sua solicitação" (HTTP 500).

## Causa-raiz

A property `ch_aprovada` **retornava tipos diferentes** conforme o caminho:

- `float` quando os "aprovados" da DESUP estavam preenchidos (`round(n * 0.5, 1)`);
- `Decimal` quando caía no fallback dos `DecimalField` (`horas_aprovadas` / `carga_horaria` /
  `horas_reduzidas`).

Ao **somar** itens de tipos distintos (um item aprovado → `float`; outro calculado → `Decimal`), a
operação `float + Decimal` levanta
`TypeError: unsupported operand type(s) for +: 'decimal.Decimal' and 'float'` → 500.

O ponto concreto e **determinístico** de crash era `BasePendenciaFormSet.clean`
(`apps/extra_curricular/forms.py`), onde `ch_outros` acumulava `sum(item.ch_aprovada ...)` dos três
tipos **sem cast** — bastando um item `float` e outro `Decimal` para estourar.

## O que mudou

Estratégia escolhida: **normalizar `ch_aprovada` para sempre retornar `float`** (menor ripple — os
consumidores no fluxo de parecer, `_ch_aprovada_outros` e `_BaseParecerView.post`, já casteavam para
`float`) e blindar as somas remanescentes.

### `apps/extra_curricular/models.py`

- `OrientacaoTCC.ch_aprovada` (~192): fallbacks passam a retornar `float(self.horas_aprovadas)` e
  `float(self.carga_horaria or 0)` (o caminho `round(...)` já era float).
- `AtividadeExtensionista.ch_aprovada` (~289): idem — `float(self.horas_aprovadas)` e
  `float(self.carga_horaria or 0)`.
- `ReducaoCargaHoraria.ch_aprovada` (~369): `float(self.horas_aprovadas)` e
  `float(self.horas_reduzidas or 0)`.
- `PendenciaExtra.ch_total_justificada` (~99): soma passa a usar `float(...)` por item
  (`sum(float(t.ch_aprovada) ...)`) e retorna `tcc + ext + red` — sem mistura de tipos. O `or 0`
  também evita `float(None)` em instâncias sem CH.

### `apps/extra_curricular/forms.py`

- `BasePendenciaFormSet.clean` (~49-55): `ch_outros` inicia como `0.0` e cada parcela usa
  `sum(float(item.ch_aprovada) ...)` — blindagem no ponto exato do crash (mesmo padrão de
  `_ch_aprovada_outros`).

### `apps/extra_curricular/views.py`

- **Sem alteração.** `_ch_aprovada_outros` (~683) e `_BaseParecerView.post` (~717) já convertiam para
  `float`; agora coerentes com o resto.

> Regra de negócio **inalterada** — apenas o tipo numérico. Os valores/limites continuam idênticos.

## Testes

Adicionada a classe `ChAprovadaTipoConsistenteTests` em `apps/extra_curricular/tests.py`:

1. `test_ch_aprovada_sempre_float_nos_tres_modelos` — `ch_aprovada` é `float` em todos os caminhos
   (com "aprovados" e no fallback DecimalField) para TCC, Extensão e Redução.
2. `test_ch_total_justificada_com_tipos_mistos_nao_estoura` — soma de itens originalmente mistos
   (float + Decimal) não levanta `TypeError` e bate `2.0 + 3.0 + 1.5`.
3. `test_formset_clean_soma_mista_nao_estoura_typeerror` — reproduz o ponto concreto do crash
   (`BasePendenciaFormSet.clean`): TCC aprovado (float) + Extensão sem aprovados (Decimal) →
   `formset.is_valid()` roda sem exceção.
4. `test_fluxo_parecer_aprovar_tcc_depois_indeferir_extensao` — regressão end-to-end do relato:
   aprovar TCC e depois indeferir Extensão do mesmo professor via endpoints `parecer_*` retorna 302
   (não 500) e consolida a pendência como `INDEFERIDO`.

## Verificação

```
DJANGO_SETTINGS_MODULE=config.settings.development ../.venv/Scripts/python.exe manage.py test apps.extra_curricular
→ Ran 19 tests ... OK

DJANGO_SETTINGS_MODULE=config.settings.development ../.venv/Scripts/python.exe manage.py check
→ System check identified no issues (0 silenced).
```

## Rollback

Reverter os três arquivos tocados:

```
git checkout -- project_root/apps/extra_curricular/models.py \
                project_root/apps/extra_curricular/forms.py \
                project_root/apps/extra_curricular/tests.py
```

(São os únicos arquivos de código alterados. Reverter também esta seção/relatório se desejado.)

## Notas

- A confirmação do traceback exato do endpoint de parecer depende da observabilidade da **CORR-005**
  (sem logs no momento). Independentemente disso, a inconsistência de tipo foi normalizada — que era
  a suspeita nº 1 e o crash determinístico em `BasePendenciaFormSet.clean`.
- Cobertura adicional de combinações/sequências de parecer é o escopo da **CORR-006**.
