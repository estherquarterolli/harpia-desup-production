# Plano de Implementação v3 — Integridade de Domínio

Este plano endereça as dívidas críticas de regras de negócio identificadas no `relatorio_afericao_v3.md`, movendo o sistema de um CRUD genérico para uma ferramenta de gestão acadêmica com travas institucionais.

## 1. Regra de Janela Semestral (Regra #2)

### Objetivo funcional
Bloquear edições na matriz curricular fora dos prazos definidos pela coordenação acadêmica.

### Estratégia Técnica
- Criar o app `configuracoes` (ou usar o `core`) para o modelo `JanelaEntrega`.
- Implementar um helper `is_janela_aberta(unidade)`.
- Adicionar validação no `clean()` dos models de alocação e nas Views.

**Model `JanelaEntrega`:**
- `semestre` (ex: 2026.1)
- `data_inicio`, `data_fim`
- `status` (ABERTO, FECHADO, REABERTO)
- `unidade` (opcional, para reaberturas específicas)

---

## 2. Regra dos Dois Bancos / Separação RH vs DESUP (Regra #3)

### Objetivo funcional
Preservar os dados originais da "Lista Força" (RH) e registrar apenas as correções na camada DESUP.

### Estratégia Técnica
- Refatorar o modelo `Professor` para separar campos `rh_` de campos `desup_`.
- Campos `rh_` são populados via importação (Simulado por enquanto) e nunca editados pela Unidade.
- Campos `desup_` armazenam a sobrescrita. Se `desup_nome` estiver vazio, usa-se `rh_nome`.

**Refatoração `Professor`:**
- `rh_matricula`, `rh_nome`, `rh_email`, `rh_ch_total` (Read-only)
- `desup_nome`, `desup_email`, `desup_ch_total` (Editáveis pela DESUP)
- `is_cedido` (Boolean - Regra #4)

---

## 3. Regra do SEI e Fluxo de Justificativa (Regra #8)

### Objetivo funcional
Exigir número SEI válido (seguindo o padrão institucional) para envio de justificativas e controlar o prazo pela janela de fechamento da matriz.

### Estratégia Técnica
- Adicionar campo `sei_numero` ao modelo de Alocação/Justificativa.
- Criar validador Regex para o formato `SEI-\d{6}/\d{6}/\d{4}`.
- Implementar lógica de prazo vinculada a `JanelaEntrega`: a carga horária justificada pode ser adicionada até `data_fim` da matriz; após isso, apenas se houver janela `REABERTO` definida pela coordenação acadêmica.

---

## 4. Regra de Cessão e RAT (Regras #4 e #5)

### Objetivo funcional
Tratar professores cedidos como carência e exigir RAT integral.

### Estratégia Técnica
- No modelo `Professor`, a flag `is_cedido` deve disparar a lógica de "Carência" nos relatórios.
- No modelo de alocação, criar o tipo `RAT` com validação de que a carga horária informada deve ser igual ao total da atividade (sem parciais).

---

## Cronograma de Execução

1.  **Fase 1: Infraestrutura de Controle**
    - Criar `JanelaEntrega` e lógica de bloqueio.
2.  **Fase 2: Refatoração de Persistência**
    - Migrar `Professor` para o padrão RH/DESUP.
3.  **Fase 3: Fluxo de Envio (SEI)**
    - Implementar obrigatoriedade de preenchimento do SEI e prazo pela janela da matriz.
4.  **Fase 4: Testes de Domínio**
    - Criar os testes negativos solicitados no relatório v3.

**Implementar preservando integralmente as regras de negócio; qualquer solução que as flexibilize deve ser rejeitada, mesmo que reduza esforço técnico.**
