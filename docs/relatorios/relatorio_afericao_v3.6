# Relatório de Aferição v3.6 — Correção de Vulnerabilidades e Integridade

**Papel:** Agente REVIEWER (Revisão Técnica e de Conformidade de Domínio)
**Data:** 2026-05-06
**Escopo:** Validação das correções do agente **Corrector** e conformidade com as diretrizes do **Tester**.

---

## 1. Resumo das Correções de Segurança (Agente Corrector)
Foram verificadas as seguintes implementações de segurança e estabilidade:

### 🛡️ Endurecimento de Login (Hardenning)
- ✅ **Lockout de Conta:** Implementada a Regra #10 na view de login. Após 5 tentativas falhas, o e-mail é bloqueado por 15 minutos via cache do Django.
- ✅ **Redirecionamento Seguro:** A função `get_redirect_url_for_user` foi blindada para redirecionar Superusuários ao `/admin/` e perfis específicos aos seus dashboards, evitando exposição indevida.

### 🛠️ Estabilidade do Admin (Correção de Bugs)
- ✅ **IntegrityError Fix:** Criados `CustomUserCreationForm` e `CustomUserChangeForm` para resolver o erro de restrição UNIQUE no e-mail durante a criação de usuários via Admin.
- ✅ **Sincronização de Campos:** O formulário agora sincroniza automaticamente o campo `username` (AbstractUser) com o `email`, mantendo a compatibilidade interna do Django sem exigir entrada dupla do gestor.

---

## 2. Verificação de Integridade de Domínio (Regras #2 e #3)

### 📊 Separação RH vs DESUP
- ✅ **Modelo Professor:** Implementada a separação física de campos originais do RH (`rh_nome`, `rh_matricula`) e campos de ajuste do DESUP (`desup_nome`).
- ✅ **Transparência de Dados:** Propriedades `@property` no modelo garantem que o sistema utilize o dado original do RH como fallback, mas priorize o ajuste manual do DESUP se este existir.

### 🗓️ Janelas de Entrega
- ✅ **Modelo JanelaEntrega:** Implementado controle temporal por semestre e unidade para governar o envio da matriz curricular.
- ✅ **Trava de Backend:** O método `is_ativa` permite que o sistema bloqueie edições fora do prazo estipulado pela coordenação acadêmica.

---

## 3. Isolamento de Dados (UnitBoundManager)
- ✅ **Multi-tenancy:** O `UnitBoundManager` e o `UnitBoundQuerySet` estão filtrando corretamente os registros baseados na unidade do usuário logado (`COORDENADOR_UNIDADE`).
- ✅ **Failsafe:** Coordenadores sem unidade vinculada recebem `QuerySet.none()`, prevenindo vazamento de dados por erro de configuração de perfil.

---

## 4. Status de Testes
- ✅ **Cobertura:** Foram revisados e atualizados os testes em `apps/accounts/tests.py`, `apps/core/tests.py` e `apps/allocations/tests.py`.
- ✅ **Regex SEI:** Verificado que a validação regex do SEI está ativa e coberta por testes de falha/sucesso.

**Status Final:** ✅ **Conforme (v3.6)**. O sistema está pronto para a entrada de dados do Ciclo 2.

> [!IMPORTANT]
> **Ação Recomendada:** Realizar o checklist de testes manuais anexo para validar a experiência de ponta a ponta.
