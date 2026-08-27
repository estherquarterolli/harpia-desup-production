# Workflow de Sprints — AllocGest-DESUP

Este documento organiza o desenvolvimento do **AllocGest-DESUP** em sprints práticas, usando os ciclos definidos a partir da documentação do projeto e da estratégia de implementação incremental adotada. O sistema existe para centralizar processos hoje feitos em planilhas, com foco em autenticação, controle por perfil, matriz curricular, alocação de professores, ausências, dashboards e segurança.[cite:1]

## Objetivo do workflow

O objetivo deste workflow é transformar os requisitos e casos de uso do documento em um plano de execução claro, incremental e seguro. A ideia é construir primeiro a base estrutural do sistema e só depois avançar para regras mais sensíveis, como trava de carga horária, escopo por unidade e dashboards gerenciais.[cite:1]

## Regras de execução

- Cada sprint deve gerar um entregável funcional, mesmo que pequeno.
- Nenhuma sprint deve pular validações de segurança e escopo por unidade quando isso impactar o domínio.[cite:1]
- Toda feature crítica deve ser revisada antes de ser considerada concluída, especialmente autenticação, autorização, alocação e dashboards.[cite:1]
- O fluxo recomendado é: **implementar → revisar → corrigir → validar manualmente → registrar avanço**.

## Papéis dos agentes

**MANDATÓRIO PARA TODOS OS AGENTES:** É obrigatória a leitura e aplicação do arquivo `prompt-arquiteto-regras-negocio.md` e das diretrizes de fiscalização contidas em `agentes_strict_rules.md` (localizados na pasta base/docs). A regra de negócio prevalece sobre qualquer atalho técnico, e implementações que a desrespeitarem devem ser reprovadas.

### Gemini
Use o Gemini para:
- implementar a primeira versão das features;
- gerar boilerplate, CRUDs, forms, views e templates;
- quebrar tarefas grandes em partes pequenas;
- acelerar codificação incremental.

### Claude Opus
Use o Claude Opus para:
- revisar PRs e blocos de código importantes;
- analisar segurança, regras de negócio e regressão;
- gerar relatórios de erro;
- validar se a sprint está realmente pronta.

## Sprint 1 — Fundação do projeto

### Ciclo 1: Fundação do projeto
**Objetivo de aprendizado:** estruturar corretamente um projeto Django modular e preparar a base para crescimento.

**Escopo desta sprint:**
- criar a estrutura principal do projeto;
- configurar settings por ambiente;
- preparar `.env.example`;
- criar app `core`;
- configurar usuário customizado com autenticação por e-mail.

**Tarefas principais:**
- montar a arquitetura inicial com `config/`, `apps/`, `templates/`, `static/`, `tests/` e `requirements`;
- separar `base.py`, `development.py` e `production.py`;
- configurar banco, arquivos estáticos, timezone e apps instalados;
- definir `AUTH_USER_MODEL` desde o início;
- criar modelo inicial de usuário com perfil e unidade.

**Entregável da sprint:**
projeto Django inicial funcional, com estrutura limpa, usuário customizado e base de configuração pronta para evolução.

**Checklist de pronto:**
- projeto sobe localmente;
- migrations iniciais funcionam;
- usuário customizado existe;
- settings por ambiente estão separados;
- `.env.example` está coerente.

**Agente principal:** Gemini.[cite:1]
**Agente de validação:** Claude Opus.

---

## Sprint 2 — Modelagem do domínio

### Ciclo 2: Modelagem do domínio acadêmico
**Objetivo de aprendizado:** transformar o domínio acadêmico em entidades bem modeladas e consistentes.

**Escopo desta sprint:**
- desenhar diagrama lógico das entidades (ER);
- modelar unidades, cursos, matrizes curriculares, componentes curriculares e turmas;
- modelar professores, contratos, disponibilidade e ausências;
- configurar relacionamentos (ForeignKey/ManyToMany) considerando Unidade e Período Letivo;
- associar limites fixos e status aos tipos de contrato;
- criar propriedades nos models para calcular CH Total, CH Alocada e % de Alocação.

**Tarefas principais:**
- desenhar ou revisar o diagrama lógico antes de consolidar migrations;
- criar app `courses` com entidades `Course`, `CurriculumMatrix`, `CurricularComponent`, `ClassGroup` (Turma);
- criar app `professors` com professor, tipo de contrato e status;
- criar propriedades no model `Professor` para cálculos dinâmicos de Carga Horária;
- configurar as referências cruzadas entre `courses`, `core` e `professors`;

**Entregável da sprint:**
modelo relacional inicial do sistema com migrations aplicadas e entidades centrais prontas para uso.

**Checklist de pronto:**
- models representam corretamente unidade, curso, turma, componente curricular e professor;
- contratos estão desacoplados de regras hardcoded;
- ausências e status já têm espaço no domínio;
- migrations consistentes e sem gambiarra.

**Agente principal:** Gemini.
**Agente de validação:** Claude Opus, com foco em coerência de domínio.[cite:1]

---

## Sprint 3 — Acesso e segurança base

### Ciclo 3: Autenticação, autorização e escopo por unidade
**Objetivo de aprendizado:** garantir que o sistema respeite perfis de acesso e isolamento entre unidades.

**Escopo desta sprint:**
- login por e-mail e senha;
- redirecionamento por perfil;
- autorização por papel e unidade;
- auditoria básica e exportação do histórico;
- timeout de sessão por inatividade;
- lógica condicional na UI para seletores globais.

**Tarefas principais:**
- implementar fluxo de login com redirecionamento específico baseado no Perfil;
- bloquear acesso indevido por manipulação de URL e filtrar querysets por escopo da unidade;
- registrar ações críticas e criar view/endpoint para exportar histórico de auditoria (CSV/PDF);
- configurar expiração de sessão (timeout) por inatividade;
- criar lógica no template para que o dropdown 'Selecionar Unidade' só apareça para Admin DESUP.

**Entregável da sprint:**
controle de acesso seguro e funcional, com base mínima de auditoria e isolamento por unidade.

**Checklist de pronto:**
- usuário da unidade não acessa dados de outra unidade;
- redirecionamento funciona corretamente;
- logs básicos existem;
- sessão expira;
- permissões não dependem só de esconder botão na interface.

**Agente principal:** Gemini para implementação inicial.
**Agente de validação:** Claude Opus, obrigatoriamente, por envolver segurança e autorização.[cite:1]

---

## Sprint 4 — Cadastros operacionais

### Ciclo 4: Matriz curricular e cadastros operacionais
**Objetivo de aprendizado:** construir a base operacional para uso real do sistema.

**Escopo desta sprint:**
- CRUD de cursos, componentes curriculares e turmas;
- CRUD de professores e contratos;
- tela unificada da grade curricular.

**Tarefas principais:**
- implementar cadastros com Django Forms/ModelForms;
- usar HTMX para melhorar tabelas, formulários ou modais quando fizer sentido;
- preparar filtros por unidade, curso e status;
- criar visão consolidada da matriz curricular por curso e turno.

**Entregável da sprint:**
módulo administrativo de base funcional, capaz de alimentar corretamente a futura alocação.

**Checklist de pronto:**
- usuários autorizados conseguem cadastrar e editar dados-base;
- dados aparecem corretamente nas listagens;
- filtros mínimos funcionam;
- matriz curricular é navegável e coerente.

**Agente principal:** Gemini.
**Agente de validação:** Claude Opus para revisão de consistência e permissões.

---

## Sprint 5 — Núcleo do sistema

### Ciclo 5: Motor de alocação de carga horária
**Objetivo de aprendizado:** implementar o coração do sistema com regras de negócio testáveis.

**Escopo desta sprint:**
- criar a estrutura de alocação em sala;
- aplicar regras de trava por contrato;
- exibir alertas de conflito;
- manter lógica centralizada em regras de negócio.

**Tarefas principais:**
- criar app `allocations` com models necessários;
- implementar `business_rules.py` ou camada equivalente;
- validar limite de 20 horas para Ensino Superior;
- preparar extensibilidade para outros contratos, como BTT, citado no documento;
- criar interface de alocação com HTMX para experiência mais fluida.

**Entregável da sprint:**
alocação em sala funcionando, com travas de negócio e retorno visual claro para conflitos.

**Checklist de pronto:**
- sistema impede excesso de carga em sala conforme regra;
- mensagens de erro/sucesso são claras;
- regra não está enterrada em view;
- testes unitários cobrem cenário feliz e bordas.

**Agente principal:** Gemini para primeira implementação.
**Agente de validação:** Claude Opus, com foco forte em regra de negócio e regressão.[cite:1]

---

## Sprint 6 — Fluxos complementares críticos

### Ciclo 6: Carga extracurricular, justificativas e ausências
**Objetivo de aprendizado:** modelar e implementar estados operacionais mais completos do professor.

**Escopo desta sprint:**
- registrar carga extracurricular;
- somar carga extracurricular ao teto global de 40 horas;
- implementar justificativas/status;
- registrar ausências com upload e alteração de status.

**Tarefas principais:**
- criar fluxo para pesquisa, extensão e preparação de aula;
- implementar justificativa com possibilidade de análise/aprovação;
- permitir upload validado de atestado/licença;
- alterar status do professor para ausente/afastado;
- gerar alerta visual para o painel.

**Entregável da sprint:**
fluxo operacional mais fiel ao domínio acadêmico, cobrindo alocação complementar e indisponibilidade docente.

**Checklist de pronto:**
- teto global de 40 horas está sendo respeitado;
- ausência altera status corretamente;
- upload é validado no back-end;
- justificativas têm rastreabilidade mínima.

**Agente principal:** Gemini.
**Agente de validação:** Claude Opus, principalmente para revisar consistência de estado e segurança de upload.[cite:1]

---

## Sprint 7 — Inteligência gerencial

### Ciclo 7: Dashboards e relatórios
**Objetivo de aprendizado:** transformar dados operacionais em informação útil para unidade e gestão central.

**Escopo desta sprint:**
- dashboard da unidade;
- dashboard global;
- relatórios exportáveis.

**Tarefas principais:**
- implementar KPIs da unidade;
- implementar visão comparativa/global entre unidades;
- criar gráficos e filtros coerentes com o perfil do usuário;
- criar app `reports` com exportação PDF/Excel ou estrutura inicial equivalente.

**Entregável da sprint:**
camada analítica funcional para acompanhamento da conformidade da matriz e da situação das unidades.

**Checklist de pronto:**
- cada perfil vê apenas o que deveria ver;
- consultas não explodem em complexidade desnecessária;
- dashboard local e global estão separados com clareza;
- indicadores fazem sentido com os dados realmente existentes.

**Agente principal:** Gemini para base da implementação.
**Agente de validação:** Claude Opus para validar escopo, integridade e risco de vazamento de dados.[cite:1]

---

## Sprint 8 — Confiabilidade e entrega

### Ciclo 8: Qualidade, segurança e deploy
**Objetivo de aprendizado:** sair de um sistema que “funciona” para um sistema confiável e apresentável.

**Escopo desta sprint:**
- testes unitários e de integração;
- endurecimento de segurança;
- documentação técnica;
- preparação de deploy.

**Tarefas principais:**
- escrever testes para permissões, carga horária e fluxos sensíveis;
- revisar autenticação, hash de senha, troca de senha e logs;
- organizar README, setup e variáveis de ambiente;
- preparar estratégia inicial de deploy e backup;
- definir pendências de fase 2, como MFA e integrações externas, se não entrarem no MVP.

**Entregável da sprint:**
MVP estável, testado, documentado e minimamente pronto para apresentação, homologação ou continuação controlada.

**Checklist de pronto:**
- testes críticos passam;
- permissões foram revisadas;
- logs e segurança básica estão adequados;
- documentação de setup está utilizável;
- backlog pós-MVP foi registrado.

**Agente principal:** Claude Opus para revisão e fechamento, com Gemini apoiando correções pontuais.[cite:1]

---

## Ordem recomendada de execução

A ordem recomendada é:
1. Fundação do projeto
2. Modelagem do domínio
3. Autenticação e autorização
4. Cadastros operacionais
5. Alocação em sala
6. Carga extracurricular, justificativas e ausências
7. Dashboards e relatórios
8. Qualidade, segurança e deploy

Essa ordem respeita dependências técnicas, aprendizado progressivo e geração de feedback rápido sobre o núcleo do sistema, que é a alocação de professores e o controle por unidade.[cite:1]

## Definição de pronto por sprint

Uma sprint só deve ser considerada concluída quando:
- o entregável principal estiver funcional;
- os fluxos críticos tiverem sido validados manualmente;
- houver revisão do código da sprint;
- os principais riscos de permissão, regra de negócio e regressão tiverem sido analisados;
- as decisões relevantes tiverem sido registradas em documentação curta.

## Fluxo operacional recomendado por tarefa

Para cada tarefa importante, siga este fluxo:
1. Definir escopo pequeno e claro.
2. Pedir implementação inicial ao Gemini.
3. Executar localmente e validar o fluxo manual.
4. Enviar diff, arquivos ou erro ao Claude Opus.
5. Corrigir os pontos levantados.
6. Revalidar.
7. Marcar tarefa como concluída.

## Observações finais

Este workflow foi pensado para equilibrar velocidade de implementação e segurança técnica. Como o projeto possui regras sensíveis de autenticação, escopo institucional, carga horária e dashboards por perfil, vale mais avançar em blocos pequenos e sólidos do que tentar fechar muitos módulos ao mesmo tempo.[cite:1]
