# Central de Ajuda e suporte

## Integração e interface

A implementação usa o app `core`, `base.html`, os campos e classes Tailwind existentes,
CSRF, validação por formulário Django e os perfis operacionais Unidade/DESUP.
O perfil ADMIN mantém o redirecionamento à administração; a visualização operacional
do superadministrador segue o perfil/unidade definidos pelo middleware existente.
O botão `?` continua abrindo o tutorial anterior. O link “Perguntas frequentes e
suporte” no painel do tutorial abre a página FAQ, com perguntas por perfil.
O menu lateral inclui a seção “Perguntas frequentes” logo abaixo de “Ensino e currículo”,
com o item FAQ e ícone de interrogação. A rota é `/core/ajuda/faq/` (`core:faq`).
Ao final das perguntas, “Como podemos ajudar?” oferece o botão “Solicitar suporte”.
O suporte tem página própria em `/core/ajuda/`; não há mais abas internas de navegação.

O acesso começa no canto inferior direito: a aba lateral “Suporte”, com ícone de
headset. Ela abre diretamente o formulário, sem botão circular, X ou estado de
recolhimento. A faixa reservada foi reduzida para 40 px, para não cobrir conteúdo
e aproveitar melhor a largura em dispositivos móveis. O usuário pode arrastá-la
com o mouse para outra posição dentro da tela. Um clique simples abre o formulário;
o término do arraste não dispara a navegação. A posição é salva em `localStorage`
(`harpia.support.position.v1`) e se adapta ao redimensionamento da janela.
Se o armazenamento estiver bloqueado, o arraste continua funcionando na página.
Modais, tutorial e menu móvel ocultam o acesso flutuante. Não há polling nem
consultas adicionais de suporte durante a navegação nas demais páginas.

As respostas do FAQ foram conferidas nos tutoriais em `apps/core/ajuda.py`, na
listagem de professores, na equipe diretiva e nas abas de Extracurriculares.
O contato técnico não substitui o pedido de abertura da janela, RAT, cessão,
cadastro de professor ou aprovações. Nenhum desses fluxos foi alterado.

## Configuração e implantação

Execute as migrações e gere os estáticos pelos comandos normais de implantação:

```powershell
python manage.py migrate
npm run build:css
python manage.py collectstatic --noinput
```

Configure as variáveis no ambiente do servidor (não no frontend):

| Variável | Uso |
| --- | --- |
| `HARPIA_SUPPORT_EMAIL` | Opcional. Define outra caixa de destino; quando vazio, usa o endereço de `DEFAULT_FROM_EMAIL`. |
| `EMAIL_BACKEND` | Backend Django. Produção usa `django.core.mail.backends.smtp.EmailBackend` por padrão. |
| `EMAIL_HOST`, `EMAIL_PORT` | Servidor e porta fornecidos pela instituição/provedor. |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | Credenciais do provedor, quando exigidas. |
| `EMAIL_USE_TLS`, `EMAIL_USE_SSL` | Conforme o provedor; não ativar ambos. |
| `DEFAULT_FROM_EMAIL` | Remetente autorizado pelo provedor. |
| `EMAIL_TIMEOUT` | Limite de espera SMTP, em segundos; padrão existente: 5. |

O endereço institucional informado é `harpia@desup.faetec.rj.gov.br`, já definido
em `DEFAULT_FROM_EMAIL` no Vercel. O suporte reutiliza essa configuração, sem
duplicar o endereço no código nem exigir uma nova variável de ambiente. Uma
configuração explícita de `HARPIA_SUPPORT_EMAIL` continua tendo precedência.
Não foram alteradas credenciais nem configurações do Vercel. Os backends de
console, arquivo e dummy deixam o envio indisponível para não anunciar uma entrega
inexistente. `development.py` usa console por padrão e respeita `EMAIL_BACKEND`
e `DEFAULT_FROM_EMAIL` quando definidos explicitamente no ambiente local.
Variáveis cadastradas apenas no Vercel não são copiadas automaticamente para
a máquina local. Para testar SMTP localmente, configure o backend SMTP e os
dados do provedor no ambiente local; o endereço do remetente, sozinho, não
configura a conexão com o serviço. O aviso do formulário distingue modo de
simulação e endereços ausentes ou inválidos, sem expor credenciais.
O backend locmem é usado somente nos testes, sem comprovar entrega real.

Ajuste de posicionamento e diagnóstico: a aba permanece recolhida na lateral,
por padrão no canto inferior direito. A validação do diagnóstico executou 32 testes de
suporte e conferiu separadamente que console e SMTP explícitos são respeitados
por `development.py`, sem enviar mensagens reais.

Há Celery no código, mas os manifestos de implantação não incluem um worker.
Por isso o suporte usa envio síncrono com o timeout existente, sem depender de
Redis, novas filas ou novas bibliotecas. Confirmar a entrega real exige um teste
controlado após configurar o provedor e verificar a caixa institucional.

## Fluxo, segurança e confiabilidade

1. GET autenticado `/core/ajuda/` mostra FAQ e formulário com chave aleatória assinada,
   vinculada ao usuário e válida por duas horas. A origem contém apenas o nome de uma
   funcionalidade conhecida. Links de ajuda não copiam filtros, identificadores ou tokens.
2. POST valida CSRF, perfil, tipo, assunto (150 caracteres, sem controles/quebras de
   linha), descrição (5.000 caracteres) e assinatura. Identificadores de usuário,
   perfil ou unidade fornecidos pelo navegador são ignorados.
3. Uma transação curta bloqueia a linha do usuário e reserva um recibo UUID único.
   Máximo de uma tentativa por minuto e cinco por hora por usuário, incluindo falhas,
   independente de abas, sessões, cache local ou workers. Os bloqueios de linha
   requerem PostgreSQL/MySQL; SQLite protege a chave única, mas não garante a mesma
   serialização do limite entre pedidos concorrentes com chaves diferentes.
4. O backend envia texto puro com tipo, assunto, descrição, nome/e-mail autenticados,
   unidade, perfil, data/hora, funcionalidade e referência. `Reply-To` é o e-mail
   cadastrado do solicitante. Não há cópia automática de registros de terceiros.
5. Somente retorno `1` do backend marca `ENVIADO` e redireciona para uma confirmação
   persistente, visível apenas ao próprio usuário. A mensagem confirma aceitação pelo
   serviço, sem prometer entrega na caixa de entrada ou prazo de atendimento.
6. Exceção ou retorno zero marca `FALHOU`, preserva os campos na resposta e apresenta
   erro com nova chave para tentativa explícita após o limite de um minuto. Logs têm
   apenas referência e classe da exceção, sem conteúdo, e-mail ou resposta SMTP.

`SolicitacaoSuporte` mantém somente UUID, usuário/unidade, datas e status. Não armazena
assunto, descrição ou anexos. A migração é `core.0016_solicitacao_suporte`.
Não há lista pública de solicitações, painel de tickets, retentativa automática,
prioridades ou atribuição de técnicos. Anexos foram deixados fora desta versão para
manter a minimização de dados e evitar armazenamento de documentos sensíveis.

Se houver queda após a reserva ou entre a aceitação SMTP e a atualização do banco,
o recibo fica `ENVIANDO` (resultado incerto). O mesmo formulário não é reenviado nem
anunciado como sucesso. É necessária conferência operacional pela referência antes
de uma nova tentativa. Um timeout também pode ocorrer depois da aceitação pelo
provedor; a interface orienta conferir com a equipe antes de reenviar. O corpo não
é persistido: não há recuperação automática de uma mensagem perdida ao fechar a página.
Uma política institucional de retenção dos recibos pode ser definida posteriormente.

## Validação

Os testes de `apps.core.tests_support` cobrem autorização, CSRF, contexto e unidade,
validação, confirmação isolada por usuário, duplicação, limites persistidos,
falha/retorno zero, privacidade dos logs, escape HTML, configuração ausente, FAQ
e ausência de consultas de suporte na navegação comum. `apps.core.tests_ajuda`
exercita a integração anterior com os tutoriais.

```powershell
python manage.py test apps.core.tests_support apps.core.tests_ajuda --settings=config.settings._tmp_test
python manage.py check
python manage.py makemigrations --check --dry-run
```

O arraste tem testes de eventos e persistência com o runner nativo do Node,
sem dependências adicionais (executar na raiz do repositório):

```powershell
node --test project_root/apps/core/tests_support_drag.cjs
```

Para verificar a migração real, execute os testes focados com
`--settings=config.settings.development` em banco de testes local isolado.

Resultados da revisão de interface e envio em 11/11/2026:

- 43 testes focados de suporte e tutoriais aprovados. Incluem FAQ no menu,
  separação das páginas, compatibilidade dos links anteriores, ausência do botão
  circular e envio para a caixa de `DEFAULT_FROM_EMAIL` quando não há outro destino.
- Os dois testes do menu em `SidebarAbertaEmBlocosTests` foram atualizados para
  a organização atual das seções e as permissões de Unidade/DESUP.
- Suíte completa: 862 testes, com 40 falhas, 5 erros e 20 ignorados. Comparação
  por identificador com a execução anterior confirmou ausência de novas falhas
  ou erros e resolução dos dois testes de menu. As 45 ocorrências restantes já
  existiam em áreas como alocação, carga horária, expectativas de telas e iconografia.
- A migração já havia sido validada em 26 testes com migrações reais em 10/11.
  Esta revisão não altera modelos nem exige novas migrações.
- Para executar a suíte completa em tempo razoável, o processo de teste usou
  `MD5PasswordHasher` apenas no processo dos testes. Nenhuma configuração de senha
  da aplicação foi alterada. Os 43 testes focados usaram o hashing padrão.
- `manage.py check`, `makemigrations --check --dry-run`, compilação Tailwind,
  `node --check static/js/support.js` e `git diff --check` passaram.
- A revisão visual foi tentada novamente, mas o host de acesso ao navegador
  permanece indisponível. Layout desktop/móvel e sobreposição com componentes
  ainda requerem conferência visual.
- Não houve envio real à caixa institucional durante os testes. O remetente
  informado pelo usuário já está no Vercel; o código reutiliza essa variável.
  A entrega real precisa ser verificada após a implantação.

Logs locais da revisão: `output/support-menu-regression.log` e
`output/support-menu-comparison.log` na raiz do projeto.

## Arquivos da implementação

| Arquivo | Alteração |
| --- | --- |
| `apps/core/support.py` | Serviço de envio, contexto assinado, idempotência e limites. |
| `apps/core/support_forms.py` | Campos e validação do formulário. |
| `apps/core/support_views.py` | Central autenticada e FAQ por perfil. |
| `apps/core/ajuda.py` | Orientações dos tutoriais para as páginas FAQ e Suporte. |
| `apps/core/models.py` | Recibo mínimo de envio. |
| `apps/core/migrations/0016_solicitacao_suporte.py` | Tabela e índices dos recibos. |
| `apps/core/urls.py` | Rotas separadas de FAQ e Suporte. |
| `apps/core/tests_support.py` | Testes de suporte. |
| `apps/core/tests_support_drag.cjs` | Testes unitários do arraste, limites da tela e persistência. |
| `apps/core/tests.py` | Validação do menu atual por perfil. |
| `config/settings/base.py` | Destinatário opcional; usa o remetente institucional por padrão. |
| `config/settings/development.py` | Simulação por padrão e respeito às opções de e-mail explícitas no ambiente local. |
| `templates/core/central_ajuda.html` | FAQ, contexto, formulário e confirmação. |
| `templates/partials/_suporte_flutuante.html` | Link lateral fixo para Suporte. |
| `templates/partials/_ajuda_modal.html` | Link para a Central no tutorial existente. |
| `templates/base.html` | Inclusão compartilhada do suporte. |
| `static/js/support.js` | Overlays e bloqueio de cliques repetidos. |
| `static/css/dashboard.css` | Faixa reservada e estilos do acesso lateral. |
| `static/css/tailwind.min.css` | CSS recompilado. |
| `README.md` e `doc/central-ajuda.md` (raiz do repositório) | Configuração, operação e limitações. |

Os demais caminhos da tabela são relativos a `project_root/`.
