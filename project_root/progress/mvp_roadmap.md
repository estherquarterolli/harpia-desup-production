# Roadmap de Implementação MVP - Prisma

Este documento lista as funcionalidades e tarefas pendentes para a conclusão do MVP (Minimum Viable Product), baseadas na board "Organização de tarefas" do Trello.

---

## 📋 Resumo do Status
- **Concluído:** Ciclo 1 (Setup Base), Modelagem Inicial de Usuários e Login.
- **Concluído:** Ciclo 2 (Modelagem Acadêmica).
- **Concluído:** Ciclo 3 (Gestão Acadêmica - Interface).
- **Concluído:** Ciclo 4 (Segurança, Escopo e Auditoria).
- **Concluído(Em analise):** Ciclo 5 (Motor de Alocação (Coração do Sistema)).
- **Concluído(Em analise):** Ciclo 6 (Regras Avançadas e Justificativas).
- **Concluído(Em analise):** Ciclo 7 (Dashboards e Relatórios).
- **Em Execução:** Ciclo 8 (QA Final, Hardening e Deploy).
- **Pendente:** Ciclo 9 (Migração e Ajustes Finais).

---

## 🛠️ Pendências por Ciclo

### Ciclo 2 - Modelagem Acadêmica (Base)
*Foco em estruturar as entidades fundamentais do domínio acadêmico.*
- [x] Desenhar diagrama lógico das entidades (ER).
- [x] Criar models: `Course`, `CurriculumMatrix`, `CurricularComponent`, `ClassGroup` (Turma). **(Em Código)**
- [x] Configurar relacionamentos (ForeignKey/ManyToMany) considerando Unidade e Período Letivo. **(Em Código)**
- [x] Associar limites fixos e status aos tipos de contrato. **(Em Código)**
- [x] Criar métodos nos models (ou helpers) para calcular CH Total, CH Alocada e % de Alocação dinamicamente. **(Em Código)**

### Ciclo 3 - Gestão Acadêmica (Interface)
*Foco na interface administrativa e CRUDs funcionais com HTMX.*
- [x] Criar Forms/ModelForms para Cursos, Componentes Curriculares, Turmas, Professores e Contratos.
- [x] Escrever views para processar o CRUD dessas entidades.
- [x] Desenvolver templates HTMX para listagem, criação, edição e exclusão (sem refresh).
- [x] Montar tabela dinâmica consolidando turnos (manhã/tarde/noite).
- [x] Implementar filtros de busca globais com HTMX.

### Ciclo 4 - Segurança, Escopo e Auditoria
*Foco em garantir que cada usuário veja apenas o que lhe é permitido.*
- [x] Criar lógica/helper para redirecionamento específico baseado no Perfil (Role).
- [x] Configurar timeout de sessão por inatividade.
- [x] Implementar logs/auditoria para CRUDs sensíveis e login/logout.
- [x] Criar lógica no template para que o dropdown 'Selecionar Unidade' só apareça para Admin DESUP.
- [x] Criar view/endpoint para exportar o histórico de auditoria (CSV/PDF).
- [x] Criar queries agregadas para alimentar os KPIs do Dashboard dinamicamente. **(Em Código - Propriedades no Model Professor)**

### Ciclo 5 - Motor de Alocação (Coração do Sistema)
*Foco na lógica de alocação de carga horária e validações de regras.*
- [ ] Criar model de alocação relacionando Professor, Componente Curricular, Turma e Unidade.
- [ ] Criar `business_rules.py` contendo as funções puras de trava de contrato.
- [ ] Implementar validação para impedir excesso de horas e gerar feedbacks de erro em tempo real.
- [ ] Criar formulário de alocação reativo via HTMX.
- [ ] Adicionar alertas visuais na UI para conflitos de horários.

### Ciclo 6 - Regras Avançadas e Justificativas
*Foco em carga extracurricular e gestão de ausências.*
- [ ] Adicionar lógica de soma de carga extracurricular ao teto global do contrato.
- [ ] Criar workflow de justificativas (Pendente, Aprovado, Rejeitado).
- [ ] Implementar upload de arquivos para atestados e licenças (validação de tamanho/tipo).
- [ ] Desenvolver modal de submissão de justificativa.
- [ ] Criar tela de análise para aprovação/rejeição por administradores.

### Ciclo 7 - Dashboards e Relatórios
*Foco na visualização de dados e exportação.*
- [ ] Escrever queries agregadas para indicadores da Unidade (pendências, alertas).
- [ ] Escrever queries comparativas para o Dashboard Global (DESUP).
- [ ] Criar serviço de geração de relatórios em PDF e Excel.
- [ ] Desenvolver interfaces visuais dos Dashboards (Cards e KPIs).

### Ciclo 8 - QA, Hardening e Entrega
*Foco na qualidade, segurança final e deploy.*
- [ ] Escrever testes unitários para a camada de regras de negócio (limites de carga).
- [ ] Escrever testes de isolamento de unidade (Segurança multitenant).
- [ ] Implementar fluxo de troca de senha obrigatória no primeiro login.
- [ ] Revisar permissões e realizar hardening de segurança.
- [ ] Documentar fluxo de setup e gerar README final.
- [ ] Realizar deploy inicial da versão MVP para homologação.

---

## 📈 Tarefas de Organização Geral
- [ ] Criar diagrama de classes com base nos Models e perfis já feitos no código.
- [ ] Finalizar documentação técnica do sistema.

---
*Última atualização: 05 de Maio de 2026*
