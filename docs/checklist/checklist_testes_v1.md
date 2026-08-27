# Checklist de Testes de Aceitação — AllocGest-DESUP

Este checklist deve ser preenchido para validar as implementações de segurança, autenticação e isolamento de dados por unidade.

---

## 🏗️ 1. Gestão de Usuários (SuperAdmin)
*Valida a criação de perfis e a estabilidade do Admin Django.*

- [ ] **Acesso SuperAdmin**: Login como superuser leva à URL `/admin/`.
- [ ] **Criação de Coordenador DESUP**: Criar usuário com perfil `COORDENADOR_DESUP`. Verificar se o campo `email` é obrigatório e se o `username` é preenchido automaticamente com o e-mail.
- [ ] **Criação de Coordenador de Unidade**: Criar usuário com perfil `COORDENADOR_UNIDADE` e vincular a uma `Unidade` específica.
- [ ] **Unicidade de E-mail**: Tentar criar um segundo usuário com o mesmo e-mail. O sistema deve exibir erro de validação (Não deve dar `IntegrityError`).

---

## 🛡️ 2. Segurança e Redirecionamento
*Valida a proteção de acesso e o endurecimento de login.*

- [ ] **Redirecionamento DESUP**: Logar com o Coordenador DESUP. O sistema deve redirecionar para `/dashboard/desup/`.
- [ ] **Redirecionamento Unidade**: Logar com o Coordenador de Unidade. O sistema deve redirecionar para `/dashboard/unidade/`.
- [ ] **Bloqueio de Tentativas (Lockout)**: Errar a senha 5 vezes para um mesmo e-mail.
    - [ ] Verificar se a mensagem de conta bloqueada aparece.
    - [ ] Verificar se novas tentativas (mesmo com senha correta) são bloqueadas pelos próximos 15 minutos.

---

## 🧱 3. Isolamento de Dados (Multi-tenancy)
*Valida se um coordenador de unidade consegue ver apenas seus próprios dados.*

- [ ] **Visibilidade de Professores**:
    - [ ] Coordenador da **Unidade A** logado: Verificar se na lista de professores aparecem **apenas** professores vinculados à Unidade A.
    - [ ] Tentar acessar via URL direta o ID de um professor da **Unidade B**. O sistema deve retornar `403 Forbidden` ou `404 Not Found`.
- [ ] **Gestão Global (DESUP)**: Coordenador DESUP logado deve visualizar professores de **todas** as unidades.

---

## 🏛️ 4. Regras de Domínio (RH vs DESUP)
*Valida a integridade dos dados originais do RH.*

- [ ] **Sobrescrita DESUP**: No Admin, acessar um registro de Professor.
    - [ ] Verificar se os campos `rh_nome` e `rh_matricula` estão presentes.
    - [ ] Preencher o campo `desup_nome` com um valor diferente.
    - [ ] Verificar no dashboard se o nome exibido é o do ajuste DESUP, mantendo o dado original do RH preservado no banco.

---

## 📁 5. Validação de Alocação e SEI
*Valida a regra rigorosa de formato e prazos.*

- [ ] **Formato SEI**: Tentar salvar uma alocação com SEI no formato `123-456`. O sistema deve rejeitar (Regex esperado: `SEI-999999/999999/9999`).
- [ ] **Janela de Entrega**: Alterar a `JanelaEntrega` do semestre atual para status `FECHADO`.
    - [ ] Tentar enviar uma nova alocação. O sistema deve exibir erro de prazo encerrado.

---

**Resultado Final dos Testes:** ____________________
**Data:** ____/____/_______
**Responsável:** ____________________
