# Roadmap de Implementação MVP (Linha do Tempo)

Este documento organiza as entregas do MVP em ciclos de **no máximo 3 dias de implementação**, seguidos por **2 dias de revisão (humana + IA)** e validação com o cliente. O foco principal é a **aderência estrita às regras de negócio**.

## 🟢 Ciclo 1: Fundação do Projeto (5 dias totais)
- **Implementação (1-3 dias):** Setup base, modelagem inicial de usuários, login por e-mail, perfis de acesso.
- **Validação (4-5 dias):** Revisão de segurança, teste de perfis e aprovação inicial do fluxo de entrada.
- **Regras de Negócio Associadas:**
  - *Regra de escopo por perfil e unidade* (Base).
  - *Regra de segurança e auditoria mínima* (Definição de perfis COORDENADOR_DESUP e COORDENADOR_UNIDADE).

## 🟢 Ciclo 2: Modelagem do Domínio Acadêmico (5 dias totais)
- **Implementação (1-3 dias):** App `courses` (Cursos, Matrizes, Componentes Curriculares, Turmas), App `professors` (Professores, Contratos). Relacionamentos e propriedades de cálculo dinâmico de CH.
- **Validação (4-5 dias):** Verificação das chaves estrangeiras, propriedades do modelo e consistência do banco de dados com a regra de isolamento.
- **Regras de Negócio Associadas:**
  - *Regra dos dois bancos de dados* (Previsão arquitetural para RH vs DESUP na base dos modelos).
  - *Regra de carga horária do professor 40h* (Modelagem dos tetos e propriedades no contrato).

## 🟢 Ciclo 3: Segurança, Escopo e Auditoria (5 dias totais)
- **Implementação (1-3 dias):** Redirecionamento por perfil, bloqueio de URLs por unidade (UnitBoundManager), dashboards stub, exportação de auditoria, timeout de sessão.
- **Validação (4-5 dias):** Testes rigorosos de bypass de segurança, acessos indevidos e isolamento multitenant.
- **Regras de Negócio Associadas:**
  - *Regra de escopo por perfil e unidade* (Validação server-side, UnitBoundManager).
  - *Regra de autoridade institucional* (Apenas DESUP vê tudo, Unidade vê apenas o próprio escopo).

## 🟢 Ciclo 4: Gestão Acadêmica - Cadastros Básicos (5 dias totais)
- **Implementação (1-3 dias):** CRUDs operacionais (Cursos, Turmas, Componentes Curriculares) via HTMX. Visão consolidada da matriz.
- **Validação (4-5 dias):** Verificação de experiência de uso (HTMX) e bloqueios de cadastro fora de prazo.
- **Regras de Negócio Associadas:**
  - *Regra de janela semestral para envio da matriz curricular* (Bloqueio de cadastro de turmas/matriz fora da janela aberta pela DESUP).

## 🟢 Ciclo 5: Motor de Alocação (Coração do Sistema) (5 dias totais)
- **Implementação (1-3 dias):** Alocação de professores em turmas, alertas visuais de conflito e validação em tempo real.
- **Validação (4-5 dias):** Testes exaustivos com carga acima do limite de contrato, validação do erro retornado.
- **Regras de Negócio Associadas:**
  - *Regra de carga horária do professor 40h* (Trava de 20h em sala).
  - *Regra de cessão* (Tratar professor cedido como carência e ler dados ignorando a lista força).

## 🟢 Ciclo 6: Regras Avançadas, Extracurricular e Ausências (5 dias totais)
- **Implementação (1-3 dias):** Justificativas (Extracurricular), TCC, workflow de aprovação, registro de ausências e upload de atestado.
- **Validação (4-5 dias):** Validação de regras de teto global com as horas justificadas incluídas. Teste de prazos.
- **Regras de Negócio Associadas:**
  - *Regra de horas ociosas justificadas* (Rastreabilidade e teto global de 40h).
  - *Regra do prazo para carga horária justificada* (Inclusão permitida até o fechamento da matriz; após isso, somente em reabertura definida pela coordenação acadêmica).
  - *Regra de RAT* (Aceitar apenas carga integral).

## 🟢 Ciclo 7: Dashboards Inteligentes e Relatórios (5 dias totais)
- **Implementação (1-3 dias):** KPI reais integrados com as queries agregadas. Dashboards DESUP vs Unidade reais.
- **Validação (4-5 dias):** Testes de carga visual, validação de segurança para não exibir dados de outras unidades na unidade A.
- **Regras de Negócio Associadas:**
  - *Regra de autoridade institucional* (Apenas DESUP vê tudo).
  - *Regra de escopo por perfil e unidade* (Garantia nos relatórios gerados).

## 🟡 Ciclo 8: QA Final, Hardening e Deploy (5 dias totais)
- **Implementação (1-3 dias):** Fechamento de pendências, troca de senha inicial, testes unitários de regras de negócio faltantes, deploy para homologação.
- **Validação (4-5 dias):** Homologação final do cliente antes de migrar a operação oficial das planilhas para o Prisma.
- **Regras de Negócio Associadas:**
  - *Todas as anteriores* (Foco na integridade do banco RH x DESUP na migração final de dados).

## 🔴 Ciclo 9: Migração e Ajustes Finais (5 dias totais)
- **Implementação (1-3 dias):** Script de migração de dados das planilhas para o Prisma, auditoria de integridade, ajuste de regras de negócio baseados no feedback de uso real.
- **Validação (4-5 dias):** Testes de carga com dados migrados, validação de regras de negócio em produção (troca de operação planilhas vs. Prisma).
- **Regras de Negócio Associadas:**
  - *Regra de integração RH x DESUP* (Garantia de sincronia e integridade na migração de dados).
  - *Todas as regras anteriores* (Ajustes finos baseados no uso real e feedback).