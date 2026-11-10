# Central de Ajuda e suporte

## Integração e interface

A implementação usa o app `core`, `base.html`, os campos e classes Tailwind existentes,
CSRF, validação por formulário Django e os perfis operacionais Unidade/DESUP.
O perfil ADMIN mantém o redirecionamento à administração; a visualização operacional
do superadministrador segue o perfil/unidade definidos pelo middleware existente.
O botão `?` continua abrindo o tutorial anterior. O link “Perguntas frequentes e
suporte” no painel do tutorial abre a Central, que reúne FAQ por perfil e formulário,
sem acrescentar ícones ao cabeçalho em telas estreitas.

O acesso flutuante reserva uma faixa de 56 px à direita do conteúdo, inclusive
no celular, para não cobrir tabelas, filtros e botões. Pode ser recolhido para uma
aba lateral de 32 px. O estado fica em `localStorage` (`harpia.support.minimized`);
se o armazenamento estiver bloqueado, o controle continua funcionando na página.
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
| `HARPIA_SUPPORT_EMAIL` | Endereço institucional de destino, obrigatório para habilitar envio. Sem valor padrão. |
| `EMAIL_BACKEND` | Backend Django. Produção usa `django.core.mail.backends.smtp.EmailBackend` por padrão. |
| `EMAIL_HOST`, `EMAIL_PORT` | Servidor e porta fornecidos pela instituição/provedor. |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | Credenciais do provedor, quando exigidas. |
| `EMAIL_USE_TLS`, `EMAIL_USE_SSL` | Conforme o provedor; não ativar ambos. |
| `DEFAULT_FROM_EMAIL` | Remetente autorizado pelo provedor. |
| `EMAIL_TIMEOUT` | Limite de espera SMTP, em segundos; padrão existente: 5. |

Não foram definidos destinatários ou credenciais institucionais. Os backends de
console, arquivo e dummy deixam o envio indisponível para não anunciar uma entrega
inexistente. `development.py` força o backend console; para testar SMTP use uma
configuração local própria que importe development e sobrescreva essa opção.
O backend locmem é usado somente nos testes, sem comprovar entrega real.

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

Para verificar a migração real, execute os testes focados com
`--settings=config.settings.development` em banco de testes local isolado.

Resultados da implementação em 10/11/2026:

- 26 testes de suporte aprovados, com migrações reais e SQLite em memória.
- Suíte completa: 856 testes; 42 falhas, 5 erros e 20 ignorados. Comparação com
  o `HEAD` anterior (830 testes) confirmou os mesmos 47 testes com falha/erro,
  sem novas ocorrências. As pendências existentes envolvem alocação, carga
  horária, permissões/expectativas de telas e iconografia, fora deste escopo.
- Para executar a suíte completa em tempo razoável, o processo de teste usou
  `MD5PasswordHasher` em memória, tanto no código atual quanto na referência.
  Nenhuma configuração de senha da aplicação foi alterada. Os 26 testes focados
  com migrações reais usaram a configuração padrão de hashing.
- `manage.py check`, `makemigrations --check --dry-run`, compilação Tailwind,
  `node --check static/js/support.js` e `git diff --check` passaram.
- O controle de computador interrompeu a validação visual porque não conseguiu
  determinar com segurança a URL do navegador. Layout desktop/móvel, recolhimento
  entre páginas e sobreposição com componentes ainda requerem conferência visual.
- Não houve envio real ao provedor SMTP ou à caixa institucional. É necessário
  configurar o destinatário/remetente/provedor e verificar essa entrega no ambiente.

Logs locais: `output/support-real-migrations.log`, `output/support-regression-final.log`,
`output/support-baseline-tests.log` e `output/support-comparison.log` na raiz do projeto.

## Arquivos da implementação

| Arquivo | Alteração |
| --- | --- |
| `apps/core/support.py` | Serviço de envio, contexto assinado, idempotência e limites. |
| `apps/core/support_forms.py` | Campos e validação do formulário. |
| `apps/core/support_views.py` | Central autenticada e FAQ por perfil. |
| `apps/core/models.py` | Recibo mínimo de envio. |
| `apps/core/migrations/0016_solicitacao_suporte.py` | Tabela e índices dos recibos. |
| `apps/core/urls.py` | Rota da Central de Ajuda. |
| `apps/core/tests_support.py` | Testes de suporte. |
| `config/settings/base.py` | Destinatário por variável de ambiente. |
| `templates/core/central_ajuda.html` | FAQ, contexto, formulário e confirmação. |
| `templates/partials/_suporte_flutuante.html` | Botão recolhível e aba lateral. |
| `templates/partials/_ajuda_modal.html` | Link para a Central no tutorial existente. |
| `templates/base.html` | Inclusão compartilhada do suporte. |
| `static/js/support.js` | Minimização persistida, overlays e bloqueio de cliques repetidos. |
| `static/css/dashboard.css` | Faixa reservada e estilos do acesso lateral. |
| `static/css/tailwind.min.css` | CSS recompilado. |
| `README.md` e `doc/central-ajuda.md` (raiz do repositório) | Configuração, operação e limitações. |

Os demais caminhos da tabela são relativos a `project_root/`.
