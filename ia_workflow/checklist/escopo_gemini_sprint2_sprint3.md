# Tarefa atual — AllocGest-DESUP

Quero que você implemente esta etapa do projeto AllocGest-DESUP.
Siga a arquitetura definida, mantenha a solução incremental e não pule validações importantes.

Entregue:
- objetivo da etapa;
- estratégia técnica;
- arquivos envolvidos;
- código completo por arquivo;
- explicação pedagógica curta;
- checklist de validação;
- próximo passo sugerido.

---

## Escopo da tarefa

### Contexto do estado atual

A Sprint 1 está concluída e validada:
- Modelo `User` customizado com `email` como `USERNAME_FIELD`.
- Campo `perfil` usando `TextChoices` com dois valores: `COORDENADOR_DESUP`, `COORDENADOR_UNIDADE`.
- `PerfilRequiredMixin` já implementado em `apps/accounts/mixins.py`, usando `request.user.perfil` (não Groups).
- Migrations limpas. 4 testes automatizados passando.

O modelo `Unidade` existe em `apps/core/models.py` com os campos `nome`, `sigla` e `status`.  
O modelo `Professor` existe em `apps/professors/models.py` com o campo `unidade_principal` (FK para `core.Unidade`).  
O modelo `User` tem o campo `unidade` (FK para `core.Unidade`).

---

### Bloco 1 — `UnitBoundManager` (isolamento por unidade)

Implementar um `QuerySet` e `Manager` reutilizáveis que filtrem registros automaticamente pela unidade do usuário logado.

**Regras de negócio obrigatórias:**
- `COORDENADOR_DESUP` e `is_superuser` enxergam **todos** os registros (escopo global).
- `COORDENADOR_UNIDADE` enxerga **apenas** os registros da própria unidade.

- O Manager deve funcionar para qualquer model que tenha campo `unidade` **ou** `unidade_principal`.

**Arquivo a alterar:** `apps/core/models.py`  
Adicionar abaixo do model `Unidade` (não substituir):

```python
class UnitBoundQuerySet(models.QuerySet):
    def for_user(self, user):
        ...

class UnitBoundManager(models.Manager):
    def get_queryset(self):
        ...
    def for_user(self, user):
        ...
```

**Arquivo a alterar:** `apps/professors/models.py`  
Vincular o `UnitBoundManager` ao model `Professor`.  
O manager deve ser adicionado como `objects = UnitBoundManager()`.  
Não alterar os outros models (`ContractType`, `Availability`, `AbsenceRecord`) por enquanto.

---

### Bloco 2 — Redirecionamento por perfil na `login_view`

Hoje a `login_view` redireciona todo login bem-sucedido para `/dashboard/` sem distinguir perfil.  
Isso deve ser corrigido para respeitar a regra de negócio de separação por perfil.

**Regra de negócio:**
- `COORDENADOR_DESUP` → redirecionar para `/dashboard/desup/`
- `is_superuser` → redirecionar para `/admin/` (Django Admin)

**Arquivo a alterar:** `apps/accounts/views.py`  
A view usa HTMX. O redirecionamento deve continuar usando `HX-Redirect` no header da response.  
Extrair a lógica de escolha de URL para uma função auxiliar separada (ex: `get_redirect_url_for_user(user)`).

**Atenção:** As URLs `/dashboard/desup/` e `/dashboard/unidade/` ainda **não existem**. Crie as views e rotas como stubs funcionais (retornando um `HttpResponse` simples ou template mínimo), para que o redirecionamento não quebre com 404.

---

### Restrições

- Não usar React, Vue ou qualquer SPA.
- Não criar API REST.
- Não usar Groups do Django para controle de acesso.
- Manter o `PerfilRequiredMixin` existente — não reescrever.
- Não alterar o modelo `User` nem as migrations já aplicadas.
- O `UnitBoundManager` deve ser importado de `apps.core.models`, não duplicado em cada app.

---

### Critérios de validação (o que precisa funcionar ao final)

1. `Professor.objects.for_user(user_coordenador_unidade_a)` retorna apenas professores da unidade A.
2. `Professor.objects.for_user(user_coordenador_desup)` retorna todos os professores.
3. Login com `COORDENADOR_DESUP` → HX-Redirect aponta para `/dashboard/desup/`.
4. Login com `COORDENADOR_UNIDADE` → HX-Redirect aponta para `/dashboard/unidade/`.
6. Nenhum erro 500 ou 404 ao fazer login com qualquer perfil válido.
