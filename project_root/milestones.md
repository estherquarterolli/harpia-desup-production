# Ciclo de Desenvolvimento 1

## Pendências e Objetivos

### 1. Modelagem de Dados
- [ ] **Definir o modelo de domínio:**
  Ainda não há `Unidade`, `Perfil`, vínculo `usuario -> unidade`, nem modelos de dados de alocação. Os arquivos `models.py` de `accounts`, `core` e `allocations` estão vazios.
  - 📚 **Material de Estudo:** 
    - [Django Models (Documentação Oficial)](https://docs.djangoproject.com/en/stable/topics/db/models/)
    - [Custom User Model / AbstractUser](https://docs.djangoproject.com/en/stable/topics/auth/customizing/#substituting-a-custom-user-model)

### 2. Autenticação, Perfis e Permissões
- [ ] **Criar a regra clara dos três perfis:**
  - `superuser`: acesso total ao Django Admin e manutenção global.
  - `admin/DESUP`: usuário administrativo com permissões configuráveis por página e por ação.
  - `gestor de unidade`: usuário comum vinculado a uma unidade, vendo/editando apenas dados da própria unidade.
  - 📚 **Material de Estudo:** 
    - [Groups and Permissions](https://docs.djangoproject.com/en/stable/topics/auth/default/#groups)
- [ ] **Criar seed/migration ou comando inicial para grupos:**
  Popular grupos iniciais (Superuser, Admin DESUP, Gestor Unidade) e suas permissões associadas pelo banco.
  - 📚 **Material de Estudo:** 
    - [Data Migrations](https://docs.djangoproject.com/en/stable/topics/migrations/#data-migrations)
    - [Writing custom django-admin commands](https://docs.djangoproject.com/en/stable/howto/custom-management-commands/)
- [ ] **Definir permissões específicas (páginas e edições):**
  Definir roles como `view_dashboard_desup`, `view_alloc_curricular`, `change_professores`, etc. Controlar a edição exigindo permissões customizadas ou validações adicionais. Usar apenas grupos sem checar permissões não bloqueia a ação adequadamente.
  - 📚 **Material de Estudo:** 
    - [Custom Permissions](https://docs.djangoproject.com/en/stable/topics/auth/customizing/#custom-permissions)

### 3. Views e Controle de Acesso
- [ ] **Adicionar controle de acesso nas views:**
  Evitar renderização direta nas views atuais (`dashboard_view` e `alloc_curricular_view`). Implementar validações (login, permission, grupo, escopo).
  - 📚 **Material de Estudo:** 
    - [The login_required decorator](https://docs.djangoproject.com/en/stable/topics/auth/default/#the-login-required-decorator)
    - [The permission_required decorator](https://docs.djangoproject.com/en/stable/topics/auth/default/#the-permission-required-decorator)
    - [LoginRequiredMixin para Class-Based Views](https://docs.djangoproject.com/en/stable/topics/auth/default/#the-loginrequired-mixin)
- [ ] **Implementar escopo por unidade (Multi-tenancy básico):**
  Todas as consultas e edições do gestor precisam filtrar por `request.user.unidade` (ou equivalente). Sem isso, um gestor veria dados globais se a view listar tudo.
  - 📚 **Material de Estudo:** 
    - [Making queries](https://docs.djangoproject.com/en/stable/topics/db/queries/)
    - [Filtering querysets em Class-Based Views (método `get_queryset`)](https://docs.djangoproject.com/en/stable/topics/class-based-views/generic-display/#dynamic-filtering)
- [ ] **Separar dashboards e páginas por perfil:**
  Atualmente todo login redireciona para `/dashboard/` (`apps/accounts/views.py` ln 28). Modificar lógica de redirect pós-login com base na role/grupo.
  - 📚 **Material de Estudo:** 
    - [Login Redirect URL & Configuração de Autenticação](https://docs.djangoproject.com/en/stable/ref/settings/#login-redirect-url)

### 4. Interfaces e Interações (UI)
- [ ] **Criar formulários/views de edição reais:**
  Hoje as páginas são templates estáticos. Substituir por forms e Class-Based Views (`Form`, `ModelForm`, `CreateView`, `UpdateView`), garantindo validação e salvamento controlado (DB real).
  - 📚 **Material de Estudo:** 
    - [Working with forms](https://docs.djangoproject.com/en/stable/topics/forms/)
    - [Generic editing views](https://docs.djangoproject.com/en/stable/topics/class-based-views/generic-editing/)
- [ ] **Ajustar menus/templates para respeitar permissões:**
  Links como "Professores" e "Matriz Vigente" estão fixos ("DIREÇÃO / Admin") no HTML. Devem aparecer e renderizar menus apenas conforme perfil/permissão do usuário logado.
  - 📚 **Material de Estudo:** 
    - [Authentication data in templates (`{{ perms }}`)](https://docs.djangoproject.com/en/stable/topics/auth/default/#auth-context-processor)

### 5. Qualidade e Testes (QA)
- [ ] **Adicionar testes para garantir bloqueios:**
  Cobrir cenários variados com Pytest / Unittest: usuário anônimo, gestor de outra unidade, gestor sem permissão de edição, admin com permissão parcial, e admin total/superuser.
  - 📚 **Material de Estudo:** 
    - [Testing tools - Django](https://docs.djangoproject.com/en/stable/topics/testing/tools/)
    - [Testing Class-Based Views e Requests (Test Client)](https://docs.djangoproject.com/en/stable/topics/testing/tools/#the-test-client)
