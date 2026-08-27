## Prompts pendentes conforme o checklist atual

### 1. Extracurricular

**Prompt**

Atue como desenvolvedor full stack e ajuste apenas o que ainda falta no módulo de justificativas extracurriculares:

1. Ao atualizar a página depois de inserir um novo professor, mantenha a seção/painel de justificativa aberta automaticamente.
2. No fluxo de envio das justificativas, substitua a confirmação nativa do navegador por um modal mais claro e chamativo.
3. No botão de cancelar das telas de justificativa, use destaque visual em vermelho, mantendo consistência com o padrão de ações de risco.

Não altere o que já está implementado e não refatore outras partes do módulo.

---

### 2. Novo Professor

**Prompt**

Ajuste o cadastro e a edição de professores para corrigir a inconsistência entre código e banco de dados:

1. Garanta que a estrutura continue baseada em `eixo` e não em `materia`.
2. Se houver migrações, models, forms ou views desalinhados, alinhe tudo para que a aplicação e o banco usem o mesmo campo.
3. Preserve a compatibilidade com os dados já existentes e evite quebra no fluxo de listagem e edição.

Faça apenas o necessário para resolver essa divergência.

---

### 3. Gerais

**Prompt**

Faça apenas os ajustes gerais que ainda estão pendentes:

1. Aplique a fonte Myriad Pro nos títulos da aplicação, mantendo a identidade visual atual.
2. Crie um seed isolado com dados reais para a próxima apresentação, separado da base de teste.

Não mexa em itens que já foram concluídos, como renomeação do sistema ou logo.

---

### 4. Notificações

**Prompt**

Corrija apenas o que ainda falta na janela de notificações:

1. Garanta a codificação UTF-8 para que acentos e caracteres especiais sejam renderizados corretamente.

Mantenha os links de redirecionamento atuais e não faça mudanças fora desse ponto.

