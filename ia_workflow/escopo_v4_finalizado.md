# Escopo da Versão 4 — Finalizado

Este documento consolida as funcionalidades implementadas na v4 do AllocGest-DESUP.

## 1. Governança Institucional e Perfis
- **Renomeação de Perfil:** O perfil `COORDENADOR_DESUP` foi simplificado para `DESUP` em todo o sistema (modelos, views, mixins e testes).
- **Controle de Super Usuário:** Implementada trava no Admin para que apenas superusuários possam conceder ou revogar o privilégio de superusuário a outros usuários.

## 2. Segurança de Autenticação (Lockout)
- **Correção do Fluxo de Login:** 
    - Corrigido erro de nomenclatura no formulário (`username` para `email`).
    - Integração com HTMX para submissão de login.
    - **Preservação de Dados:** Os campos de e-mail e senha não são mais resetados em caso de falha, permitindo que o usuário corrija apenas o erro.
    - **Bloqueio Ativo:** O contador de tentativas (5 falhas) agora acumula corretamente, bloqueando o acesso por 15 minutos via cache.

## 3. Gestão Acadêmica (CRUDs Operacionais)
Foram implementados os CRUDs completos com interfaces modernas e travas de domínio:

### Unidades de Ensino (`core`)
- Lista de cards com status (Ativo/Inativo).
- Cadastro e Edição exclusivos para perfil `DESUP`.

### Corpo Docente (`professors`)
- **Isolamento de Dados:** Coordenadores de Unidade visualizam e editam apenas professores vinculados ao seu campus (via `UnitBoundManager`).
- **Campos DESUP:** Interface preparada para sobrescrita de dados de RH.
- **Ações:** Listagem detalhada e formulário responsivo.

### Matrizes Curriculares (`courses`)
- **Operacionalização:** Interface para associar Cursos, Componentes Curriculares, Períodos e Turnos.
- **Trava de Janela:** A criação/edição de matrizes respeita o status da `JanelaEntrega`. Se a janela estiver fechada, a edição é bloqueada (exceto para SuperAdmin).
- **Turmas:** Base para criação de turmas (`ClassGroup`) a partir da matriz.

## 4. Infraestrutura de UI
- **Template Base:** Extraída a lógica de navegação para `base.html`.
- **Sidebar Dinâmica:** Links automáticos para as novas seções de gestão, respeitando as permissões do usuário logado.

---
**Status da Versão:** ✅ Concluída em 11/05/2026.
