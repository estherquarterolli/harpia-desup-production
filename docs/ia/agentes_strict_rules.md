# Diretrizes Estritas para Agentes (Coder, Tester e Arquiteto)

**Atenção Absoluta:** O projeto AllocGest-DESUP é regido por regras de negócio estritas. **NENHUM agente tem permissão para ignorar, simplificar ou burlar as regras de domínio** documentadas no arquivo mestre de arquitetura (`docs/prompt-arquiteto-regras-negocio.md`).

## 1. Obediência Obrigatória ao Arquivo Mestre
Sempre consulte o documento `docs/prompt-arquiteto-regras-negocio.md` antes de gerar código ou criar testes.

As 15 regras de negócio (Perfis de Acesso, Alterações Institucionais, Banco RH/DESUP, Cessão/RAT, CH Docente 20/40 e BTT, Horas Justificadas, Justificativa de CH, SEI, Matriz Curricular, Alocação Curricular, Alocação Extracurricular, Prazo de Entrega da Matriz, Ausências/Afastamentos, Dashboards/Relatórios, Auditoria/Segurança) **têm prevalência absoluta sobre UX e velocidade de desenvolvimento**.

## 2. Perfis do Sistema
O sistema opera com 3 perfis:
- **SuperAdmin** — acesso total para administração, testes e suporte.
- **Admin** — acesso ampliado conforme permissão institucional (Coordenador Acadêmico / DESUP).
- **Usuário-Unidade** — vê e altera apenas dados da sua unidade (Coordenador de Unidade).

## 3. Para o Agente Coder (Gemini ou similar)
- **Você está expressamente proibido de implementar permissões puramente no client-side (HTMX, CSS).** Toda autorização, filtro de unidade e trava de prazo deve ocorrer no backend Django (Views, Services, Managers - Server-Side).
- Se a interface permitir uma ação, mas o back-end receber uma solicitação inválida (ex: Unidade X alterando dado da Unidade Y, alocação acima do limite do contrato, justificativa fora do prazo da janela), o sistema DEVE retornar erro (`403 Forbidden` ou falha de validação controlada).
- Se um campo for obrigatório por regra de negócio (ex: SEI para envio definitivo), o campo deve estar sempre visível e o front-end deve indicar sua obrigatoriedade, mas a validação final (trava) DEVE ocorrer no backend.
- O campo SEI é **obrigatório para envio definitivo**, mas **não** exige validação de formato (regex). Basta verificar que está preenchido.
- Nunca sobrescreva dados de origem do RH. Ajustes e edições manuais (DESUP) pertencem apenas à camada lógica de sobrescrita/referência paralela definida pela arquitetura.
- Os estados de alocação (COMPLETO, INCOMPLETO, SEM PROFESSOR, NÃO OFERECIDA) são **distintos** e não intercambiáveis.

## 4. Para o Agente de QA / Arquiteto (Claude Opus ou similar)
- **Você tem autoridade e o DEVER de reprovar** qualquer código que ignore ou facilite violação das regras do documento mestre.
- Testes automatizados ou planilhas de testes manuais sugeridos DEVEM incluir validações de bypass de segurança (escalada de privilégio/acesso de outra unidade), testar ações fora da janela semestral, e tentar registrar excesso na carga horária estabelecida pelo contrato.
- Seu review deve cruzar imediatamente o Pull Request ou Código gerado com as regras explícitas em `docs/prompt-arquiteto-regras-negocio.md`.

## 5. Consequência da Violação
Qualquer código que entregue a funcionalidade solicitada, mas que quebre a regra de escopo de unidade, regras estritas de alocação (Tetos 20/40, BTT 10h/24t), ignore restrição de Autoridade Institucional ou ignore validação de estados de alocação será considerado como **Falha Crítica**.

> **A regra de negócio vence sobre a facilidade de desenvolvimento. Sempre.**

## 6. Distinção Crucial: Usuário vs. Professor
- **User (Autenticação):** Apenas SuperAdmin, Admin e Usuário-Unidade.
- **Professor (Domínio):** Entidade cadastrada e gerenciada pelos coordenadores.
- **PROIBIDO:** Criar qualquer vínculo de herança, OneToOneField com User, ou lógica de login para a entidade Professor. Eles são registros administrativos que aparecerão em tabelas e dashboards, nunca usuários do sistema.
