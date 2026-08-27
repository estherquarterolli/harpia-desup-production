# Checklist de Requisitos e Implementação — Prisma (AllocGest-DESUP)

Este documento apresenta o levantamento das funcionalidades solicitadas, identificando o que já foi implementado e o que ainda está pendente no sistema.

---

## 📋 Quadro Geral de Requisitos

### 1. Extracurricular
- [x] **Adicionar coluna com número do SEI**: Campo `sei_numero` adicionado ao modelo `PendenciaExtra` e integrado na listagem e na mesa de trabalho em lote.
- [x] **Remover regime(40h)**: A coluna de regime de trabalho e suas referências foram removidas das listagens e formulários de atividades extracurriculares.
- [x] **Deixar justificativas de forma independente**: Se um professor tiver diferentes justificativas (TCC, Extensão, Redução), cada uma delas é listada de forma separada na tabela de pendências via view helper `get_pendencias_data`.
- [x] **Substituir coluna saldo por "não alocado"**: O cabeçalho e os campos correspondentes foram atualizados para "Não alocado" na listagem de pendências.
- [x] **Substituir aprovado por "finalizado"**: O status `APROVADO` foi renomeado e é exibido como "Finalizado" nos enums e templates.
- [x] **Substituir frase do botão e colocar "Adicionar professor no TCC" (ou extensionista ou redução)**: Frases ajustadas dinamicamente no frontend de lote de acordo com o professor selecionado.
- [x] **Substituir o btn sair por "Voltar e salvar rascunho" em uma cor mais chamativa**: Atualizado em `pendencia_lote.html` com coloração âmbar chamativa.
- [x] **Colocar filtros e pesquisas de nome**: Filtro de pesquisa de docente por nome e filtros de status e tipo de justificativa implementados via JS na listagem de pendências.
- [x] **Timer ao enviar (Muitas solicitações)**: Debouncer global de submissão implementado em `base.html`, bloqueando cliques duplos e múltiplos envios em formulários.
- [x] **Pop-up avisando que a janela de entrega está aberta (E colocar a data de fechamento)**: Implementado. O sistema exibe um aviso na interface com o status de janela aberta e a data de fechamento no `base.html`.
- [ ] **Deixar a parte da justificativa aberta (quando inserir novo professor ao atualizar a página)**: Não implementado. Os accordions e formulários são redefinidos/fechados por padrão ao recarregar a página.
- [x] **Botão de cancelar na cor vermelha**: Implementado. Os botões de cancelamento nas telas de formulários de justificativa, unidades e cursos utilizam a classe `bg-red-600` para destaque.
- [x] **Trocar "preencher o sei" para "Clique aqui para preencher o sei" na cor laranja**: Implementado. Os botões de SEI nas telas de lote e detalhe foram atualizados para o texto solicitado e usam destaque laranja.
- [ ] **Melhorar pop-up quando pedir pra confirmar se deseja enviar as justificativas**: Não implementado. O sistema ainda utiliza a janela de confirmação nativa do navegador (`confirm(...)`).
- [x] **Quando estiver com status de "rascunho" deve ser clicavel para abrir a janela de justificativa e editar**: Implementado. O badge de rascunho na listagem abre a pendência para edição.
- [x] **Quando não for enviado por falta de SEI ou qualquer outro problema, deve aparecer um pop-up com aviso mais chamativo na tela do usuario (colocando um botão para editar e inserir o numero do SEI)**: Implementado. O sistema exibe um pop-up modal com a ação de editar o SEI diretamente.

---

### 2. Novo Professor
- [x] **Remove campo matrícula**: O campo `rh_matricula` foi excluído do formulário de criação/edição `ProfessorForm`.
- [ ] **Permanecer os eixos (e não por matérias)**: **Parcialmente Implementado / Inconsistência no Banco**. O código-fonte em Python define e utiliza o campo `eixo`, contudo, a migração `0008` removeu `eixo` para criar `materia` no banco de dados, e a reversão programada em `models.py` ainda não foi migrada/aplicada na base de dados (a migração `0011` para remover `materia` e reintroduzir `eixo` está pendente de geração e execução).

---

### 3. Alocação
- [x] **Deve continuar aparecendo todos os professores**: Todos os professores da unidade estão sendo devidamente listados no quadro de alocação.
- [x] **Criar opção chamado "sem professor" e "não oferecido"**: As opções `SEM_PROFESSOR` ("Sem professor") e `NAO_OFERECIDA` ("Não oferecido") foram adicionadas ao menu dropdown de seleção de docente.
- [x] **Se janela de entrega estiver fechada, ocultar o botão de "Salvar alocações"**: Implementado. O botão de salvar fica oculto quando `window_fechada` é verdadeiro.

---

### 4. Gerais
- [x] **Trocar nome para Prisma**: Implementado. O sistema e os templates já usam a marca Prisma.
- [ ] **Colocar todas os titulos com a fonte Myriad pro**: Não implementado. A fonte Myriad Pro não foi configurada ou importada no sistema.
- [x] **Criar uma logo**: Implementado. O sistema já utiliza os arquivos de logo do Prisma nas telas principais.
- [ ] **Separar os dados reais para a próxima apresentação**: Não implementado. Não há isolamento ou scripts de seed preparados especificamente com dados reais de produção para a próxima demonstração.

---

### 5. Segurança 
- [x] **Colocar pra trocar de senha no primeiro login**: Implementado. O middleware bloqueia o acesso até a troca de senha ser concluída.
- [x] **Criar função de "esqueceu senha" no login (Criar lógica e design da janela)**: Implementado. A tela de login já redireciona para o fluxo de recuperação de senha.
- [x] **Colocar como obrigatório senha com 1 maiuscula, pelo menos 1 numero, um caractere especial (Na hora que for trocar)**: Implementado. A validação de senha exige maiúscula, número e caractere especial.

---

### 6. Janela de Entrega
- [x] **Na nova janela de editar janela (tirar o status de aberto e deixar data de inicio sempre no dia do sistema(atual)); ao inves de varios —-- deixar como "Todas as unidades" e remover o texto em baixo**: Implementado. O formulário trava a data de início, remove `Aberto` das opções e usa `Todas as unidades` como padrão.
- [x] **Na nova janela de entrega a data-fim permanece; ao inves de varios —-- deixar como "Todas as unidades" e remover o texto em baixo**: Implementado. A data de fim continua editável e a unidade segue a opção consolidada de `Todas as unidades`.
- [x] **Colocar filtro na janela de entrega (de acordo com status e unidade)**: Implementado. A listagem de janelas já filtra por status e unidade.

---

### 7. Janela de Notificações
- [ ] **UTF-8 faltando**: Não implementado. Ainda não foi validado um ajuste específico para este ponto.
- [x] **Deixar links mais especificos (Redirecionar certo)**: Implementado. As notificações agora recebem URLs de ação mais precisas para redirecionamento.

---

## 📊 Resumo de Progresso

| Categoria | Requisitos Totais | Implementados | Pendentes / Incompletos | % de Conclusão |
| :--- | :---: | :---: | :---: | :---: |
| **1. Extracurricular** | 16 | 13 | 3 | 81.3% |
| **2. Novo Professor** | 2 | 1 | 1 | 50.0% |
| **3. Alocação** | 3 | 3 | 0 | 100.0% |
| **4. Gerais** | 4 | 2 | 2 | 50.0% |
| **5. Segurança** | 3 | 3 | 0 | 100.0% |
| **6. Janela de Entrega** | 3 | 3 | 0 | 100.0% |
| **7. Janela de Notificações** | 2 | 1 | 1 | 50.0% |
| **Total** | **33** | **26** | **7** | **78.8%** |
