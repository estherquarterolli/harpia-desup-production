# Relatório de Aferição v3.2 — Foco: Regras de Negócio

**Papel:** Agente REVIEWER (Revisão Técnica e de Conformidade de Domínio)
**Data:** 2026-05-05
**Escopo:** Avaliação do sistema AllocGest-DESUP frente às regras mandatórias do documento `prompt-arquiteto-regras-negocio.md`.

---

## 1. Objetivo da Etapa
Avaliar se a implementação atual respeita as regras de negócio institucionais ou se o projeto está seguindo um caminho puramente técnico, ignorando as travas de domínio obrigatórias.

---

## 2. Aferição de Regras de Negócio (Mandatórias)

| Regra de Negócio | Status | Análise do Reviewer |
| :--- | :--- | :--- |
| **1. Autoridade Institucional** | 🔴 **Risco** | O sistema permite que Coordenadores de Unidade vejam seus dados, mas ainda não há travas que impeçam a edição de campos sensíveis (como CH) que deveriam ser exclusivos da DESUP. |
| **2. Janela Semestral** | ❌ **Ausente** | Não existe lógica de "Período Aberto/Fechado". A matriz curricular pode ser alterada a qualquer momento, violando a regra de prazos institucionais. |
| **3. Dois Bancos (RH vs DESUP)** | ❌ **Ausente** | **Dívida Técnica Crítica.** Os modelos salvam diretamente na tabela principal. Não há separação entre dados de origem (RH) e ajustes/sobrescritas (DESUP). |
| **4. Regra de Cessão** | ❌ **Ausente** | Professores cedidos não são tratados como "carência" e não há flag de cessão no modelo `Professor`. |
| **5. Regra de RAT (Integralidade)** | ❌ **Ausente** | Modelo RAT não implementado. |
| **6. Regra 20/40 (Exceções)** | ⚠️ **Parcial** | O `ContractType` suporta os limites, mas não há rastreabilidade de exceções (ex: pesquisa em sala) conforme exigido. |
| **7. Horas Ociosas Justificadas** | ❌ **Ausente** | Conceito de justificativa de horas (TCC, extracurricular) não modelado. |
| **8. Regra do SEI e prazo da matriz**| ❌ **Ausente** | O SEI deve ser obrigatório para envio pela unidade, seguindo rigorosamente o formato regex; o prazo de carga horária justificada deve seguir o fechamento/reabertura da matriz. |
| **9. Escopo por Unidade (Server-side)**| ✅ **Conforme** | O `UnitBoundManager` e `PerfilRequiredMixin` garantem que a validação ocorra no servidor. |
| **10. Auditoria e Hardening** | ❌ **Ausente** | Sem log de ações críticas e sem bloqueio de login após 5 tentativas. |

---


## 3. Guia de Correção para o Agente CODER

O desenvolvimento deve mudar o foco da "interface" para o "domínio".

### Ações Imediatas:
1.  **Refatoração de Persistência (Regra 3):** Criar campos ou modelos de "Override" para dados da DESUP. Exemplo: no modelo `Professor`, distinguir o que veio da "Lista Força" (RH) do que foi ajustado manualmente pela coordenação.
2.  **Implementação de Janela (Regra 2):** Criar um app `configuracoes` ou similar para gerenciar os períodos de entrega de matriz, com um middleware ou decorator que bloqueie POST/PUT fora da janela.
3.  **Fluxo de SEI e prazo da matriz (Regra 8):** Adicionar campo `sei_numero`. Implementar lógica de validação: se `status='ENVIADO'`, o SEI é obrigatório e deve seguir o regex `SEI-\d{6}/\d{6}/\d{4}`. Bloquear carga horária justificada fora da janela de fechamento/reabertura da matriz.
4.  **Travas de Edição (Regra 1):** No `ProfessorForm` ou na View, garantir que campos como `tipo_contrato` ou `unidade_principal` sejam `readonly` para o perfil `COORDENADOR_UNIDADE`.

---

## 4. Guia de Correção para o Agente TESTER

Os testes atuais são puramente técnicos (consegue logar? consegue criar?). Devem passar a ser de domínio.

### Testes Negativos Obrigatórios:
1.  **Tentativa de Burlar Janela:** Tentar submeter uma matriz com data de sistema simulada fora do prazo. O sistema DEVE retornar erro 403/400.
2.  **Edição Proibida (Unidade):** Tentar alterar a carga horária de um professor logado como `COORDENADOR_UNIDADE` via requisição POST direta. Deve falhar.
3.  **Integridade do RH:** Editar um nome de professor no Dashboard DESUP e verificar no banco de dados se o valor original do RH foi preservado e apenas o valor da camada DESUP foi alterado.
4.  **SEI obrigatório e prazo da matriz:** Validar que uma submissão sem SEI não pode ser enviada; validar que formato fora do padrão regex é rejeitado; validar que carga horária justificada não pode ser adicionada após o fechamento da matriz, exceto em reabertura definida pela coordenação acadêmica.

---

## 5. Checklist de Validação para Próxima Sprint

- [ ] Existe modelo de `PrazoMatriz`?
- [ ] O modelo `Professor` distingue dados RH de dados DESUP?
- [ ] O campo SEI é obrigatório no envio e possui validação de formato (regex)?
- [ ] Usuários de Unidade estão bloqueados de editar campos sensíveis no backend?

---

## 6. Veredito do Reviewer

O sistema está tecnicamente bem montado, mas **funcionalmente frágil** por ignorar as travas de negócio. O próximo ciclo não deve ser "novas telas", mas sim a **implementação das travas e da arquitetura de dois bancos (RH/DESUP)**.

**Status Final:** ⚠️ **Aprovado com Ressalvas (Dívida de Domínio Alta)**.

> [!IMPORTANT]
> Implementar preservando integralmente as regras de negócio; qualquer solução que as flexibilize deve ser rejeitada, mesmo que reduza esforço técnico.
