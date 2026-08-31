# Diagramas PlantUML — Sistema HARPIA-DESUP

> Códigos prontos para **copiar e colar** em qualquer renderizador PlantUML
> (plantuml.com/plantuml, extensão do VS Code, IntelliJ, etc.).
> Cada bloco `@startuml … @enduml` é independente — cole um de cada vez.
>
> **Padrão visual adotado (todos os diagramas):**
> - Ator: **bonequinho padrão** (`skinparam actorStyle stickman`).
> - Paleta: **azul** (`#2563EB` / `#DBEAFE` / `#1E3A8A`) e **amarelo** (`#FDE68A` / `#FEF3C7` / `#B45309`).
> - Sem sombras, fundo branco, setas azuis.
>
> Diagramas cobertos (seções vazias do documento de elicitação):
> 1. Casos de Uso (Fig. 2 — §6.2)
> 2. Classes / Estrutura Acadêmica (§6.1)
> 3. Sequência — UC01 Login (Fig. 3)
> 4. Sequência — Alocar Carga Horária de Professor (Fig. 4)
> 5. Sequência — Alocar Carga Horária Extracurricular (Fig. 5)
> 6. Sequência — Registrar Ausência de Professor
> 7–13. Atividades — UC01, UC02, UC04, UC05, UC06, UC07, UC08 (§6 Diagrama de Atividades)

---

## 1. Diagrama de Casos de Uso — Figura 2 (§6.2)

> **Nota de modelagem:** usa-se **generalização de atores** para reduzir ruído — o
> `SuperAdmin` (acesso irrestrito) herda o `DESUP` (visão global), que herda o
> `Coordenador de Unidade` (operacional restrito). Assim, todo caso de uso ligado a um
> ator inferior está automaticamente disponível aos superiores.

```plantuml
@startuml casos_de_uso_harpia
left to right direction
skinparam actorStyle stickman
skinparam shadowing false
skinparam backgroundColor #FFFFFF
skinparam ArrowColor #1E40AF
skinparam packageStyle rectangle
skinparam actor {
  BackgroundColor #FDE68A
  BorderColor #B45309
  FontColor #1E293B
}
skinparam usecase {
  BackgroundColor #DBEAFE
  BorderColor #2563EB
  FontColor #1E3A8A
}
skinparam rectangle {
  BackgroundColor #F8FAFC
  BorderColor #2563EB
  FontColor #1E3A8A
  FontStyle bold
}

title Sistema HARPIA-DESUP — Diagrama de Casos de Uso

actor "Coordenador\nde Unidade" as COORD
actor "DESUP\n(Coord. Acadêmica)" as DESUP
actor "SuperAdmin\n(Núcleo de TI)" as ADMIN
actor "Sistema RH" as RH

' Generalização de atores (herança de permissões)
DESUP --|> COORD
ADMIN --|> DESUP

rectangle "Autenticação e Sessão" {
  usecase "UC01 Autenticar-se no Sistema" as UC01
  usecase "UC02 Encerrar Sessão" as UC02
  usecase "UC03 Alterar Senha" as UC03
}

rectangle "Governança de Usuários e Permissões" {
  usecase "UC04 Cadastrar Usuário" as UC04
  usecase "UC05 Editar Usuário" as UC05
}

rectangle "Unidades e Janelas Semestrais" {
  usecase "UC06 Cadastrar Unidade" as UC06
  usecase "UC07 Editar Unidade" as UC07
  usecase "UC08 Abrir Janela de Entrega" as UC08
  usecase "UC09 Fechar Janela" as UC09
  usecase "UC10 Reabrir Janela" as UC10
}

rectangle "Corpo Docente" {
  usecase "UC11 Cadastrar Professor" as UC11
  usecase "UC12 Editar Professor" as UC12
  usecase "UC13 Registrar Disponibilidade" as UC13
  usecase "UC14 Registrar Ausência/Afastamento" as UC14
  usecase "UC15 Marcar Professor como Cedido" as UC15
}

rectangle "Estrutura Acadêmica" {
  usecase "UC16 Cadastrar Curso por Unidade" as UC16
  usecase "UC17 Cadastrar Componente Curricular" as UC17
  usecase "UC18 Criar Matriz Curricular" as UC18
  usecase "UC19 Editar Matriz e Componentes" as UC19
  usecase "UC20 Associar Docente a Componente" as UC20
  usecase "UC21 Definir Status do Componente" as UC21
  usecase "UC22 Cadastrar Turma a partir da Matriz" as UC22
}

rectangle "Alocação Curricular e Workflow" {
  usecase "UC23 Visualizar Tela de Alocação" as UC23
  usecase "UC24 Alocar Professor em Disciplina/Turma" as UC24
  usecase "UC25 Salvar Alocação em Rascunho" as UC25
  usecase "UC26 Enviar Alocação para DESUP" as UC26
  usecase "UC27 Aprovar Alocação" as UC27
  usecase "UC28 Autorizar Alterações Pós-Envio" as UC28
}

rectangle "Carga Horária, Extracurricular e Justificativas" {
  usecase "UC29 Registrar Alocação Extracurricular" as UC29
  usecase "UC30 Submeter Justificativa de CH" as UC30
  usecase "UC31 Aprovar Justificativa" as UC31
  usecase "UC32 Rejeitar Justificativa" as UC32
  usecase "UC33 Registrar Horas Ociosas Justificadas" as UC33
}

rectangle "Dashboards, Relatórios e Auditoria" {
  usecase "UC34 Dashboard Institucional" as UC34
  usecase "UC35 Dashboard da Unidade" as UC35
  usecase "UC36 Gerar Relatório de Auditoria" as UC36
  usecase "UC37 Exportar Relatórios" as UC37
}

' --- Casos do Coordenador (herdados por DESUP e SuperAdmin) ---
COORD -- UC01
COORD -- UC02
COORD -- UC03
COORD -- UC11
COORD -- UC12
COORD -- UC13
COORD -- UC14
COORD -- UC16
COORD -- UC18
COORD -- UC19
COORD -- UC20
COORD -- UC21
COORD -- UC22
COORD -- UC23
COORD -- UC24
COORD -- UC25
COORD -- UC26
COORD -- UC29
COORD -- UC30
COORD -- UC33
COORD -- UC35
COORD -- UC37

' --- Casos exclusivos da DESUP (herdados pelo SuperAdmin) ---
DESUP -- UC05
DESUP -- UC06
DESUP -- UC07
DESUP -- UC08
DESUP -- UC09
DESUP -- UC10
DESUP -- UC15
DESUP -- UC17
DESUP -- UC27
DESUP -- UC28
DESUP -- UC31
DESUP -- UC32
DESUP -- UC34
DESUP -- UC36

' --- Caso exclusivo do SuperAdmin ---
ADMIN -- UC04

' --- Ator externo Sistema RH (origem de dados) ---
UC11 ..> RH : lê dados cadastrais
UC24 ..> RH : leitura consolidada\n(lotação / CH)

@enduml
```

---

## 2. Diagrama de Classes — Estrutura Acadêmica (§6.1)

> Modelo de domínio da estrutura acadêmica e alocação (baseado nas entidades reais do
> sistema: Unidade, Curso, Matriz, Componente, Turma, Professor, Contrato, Alocação e Janela).

```plantuml
@startuml classes_estrutura_academica
skinparam shadowing false
skinparam backgroundColor #FFFFFF
skinparam ArrowColor #1E40AF
skinparam class {
  BackgroundColor #DBEAFE
  BorderColor #2563EB
  FontColor #1E3A8A
  AttributeFontColor #1E293B
}
skinparam enum {
  BackgroundColor #FEF3C7
  BorderColor #B45309
  FontColor #1E293B
}

title HARPIA-DESUP — Estrutura Acadêmica (Modelo de Domínio)

class Unidade {
  + nome
  + sigla
  + status : bool
}

class Course <<Curso>> {
  + nome
  + sigla
}

class CourseUnit <<Curso x Unidade>> {
  + ativo : bool
}

class CurricularComponent <<Componente base>> {
  + nome
  + codigo
  + carga_horaria_padrao
  + creditos
  + obrigatoria : bool
  + ementa
}

class CurriculumMatrix <<Matriz>> {
  + nome
  + periodo_letivo
  + turno
  + is_vigente : bool
  + is_rascunho : bool
}

class MatrixComponent <<Componente na matriz>> {
  + codigo
  + periodo
  + carga_horaria (HA)
  + creditos
  + carga_horaria_semanal
  + status
  --
  + hr_total() : HA x 50/60
}

class ClassGroup <<Turma>> {
  + ano_semestre
  + identificador
}

class Professor {
  + rh_matricula
  + rh_nome
  + desup_nome
  + ha
  + is_cedido : bool
  + status
}

class ContractType <<Tipo de Contrato>> {
  + nome
  + categoria
  + max_class_hours
  + max_total_hours (40h)
  + max_classes
}

class AlocacaoCurricular <<Alocação>> {
  + semestre
  + turno
  + status
  + sei_numero
}

class JanelaEntrega <<Janela Semestral>> {
  + semestre
  + data_inicio
  + data_fim
  + status
}

enum StatusComponente {
  COMPLETO
  INCOMPLETO
  SEM_PROFESSOR
  NAO_OFERECIDA
}

enum StatusAlocacao {
  RASCUNHO
  ENVIADO
  APROVADO
}

enum StatusJanela {
  ABERTO
  FECHADO
  REABERTO
}

' Relações
Course "1" --> "*" CourseUnit : oferecido em
Unidade "1" --> "*" CourseUnit : possui
CurriculumMatrix "*" --> "1" Course : pertence a
CurriculumMatrix "*" --> "*" Unidade : abrange
CurriculumMatrix "1" o-- "*" MatrixComponent : compõe
MatrixComponent "*" --> "1" CurricularComponent : instancia
MatrixComponent "*" --> "0..1" Professor : docente
CurriculumMatrix "1" --> "*" ClassGroup : gera
ClassGroup "*" --> "1" MatrixComponent : refere-se a
Professor "*" --> "1" ContractType : regido por
Professor "*" --> "1" Unidade : lotação principal
Professor "*" --> "*" Course : habilitado em
AlocacaoCurricular "*" --> "1" Unidade
AlocacaoCurricular "*" --> "1" CourseUnit
JanelaEntrega "*" --> "0..1" Unidade : escopo

MatrixComponent .. StatusComponente
AlocacaoCurricular .. StatusAlocacao
JanelaEntrega .. StatusJanela

@enduml
```

---

## 3. Diagrama de Sequência — UC01 Login e Autenticação (Figura 3)

```plantuml
@startuml seq_uc01_login
skinparam actorStyle stickman
skinparam shadowing false
skinparam backgroundColor #FFFFFF
skinparam sequence {
  ArrowColor #1E40AF
  LifeLineBorderColor #2563EB
  LifeLineBackgroundColor #DBEAFE
  ParticipantBorderColor #2563EB
  ParticipantBackgroundColor #DBEAFE
  ParticipantFontColor #1E3A8A
  ActorBorderColor #B45309
  ActorBackgroundColor #FDE68A
}

title UC01 — Autenticar-se no Sistema

actor "Usuário" as U
participant "Navegador\n(Tela de Login)" as UI
participant "View de\nAutenticação" as View
participant "Serviço de Auth\n/ Lockout" as Auth
database "Banco DESUP" as DB

U -> UI : acessa tela de login
U -> UI : informa e-mail e senha
UI -> View : POST credenciais
View -> Auth : autenticar(email, senha)
Auth -> DB : busca usuário ativo
DB --> Auth : dados do usuário

alt credenciais válidas e conta ativa/desbloqueada
  Auth -> Auth : verifica hash da senha
  Auth --> View : usuário autenticado + perfil
  View -> DB : cria sessão
  View --> UI : redireciona conforme perfil
  UI --> U : dashboard do perfil
else senha/e-mail incorretos (3A)
  Auth -> DB : incrementa tentativas falhas
  Auth --> View : falha de autenticação
  View --> UI : erro (preserva e-mail preenchido)
else conta bloqueada por tentativas (4A)
  Auth --> View : bloqueio temporário (lockout 15 min)
  View --> UI : acesso impedido até fim do bloqueio
else primeiro acesso / troca obrigatória (7A)
  Auth --> View : exige troca de senha
  View --> UI : redireciona p/ alteração de senha
end

@enduml
```

---

## 4. Diagrama de Sequência — Alocar Carga Horária de Professor (Figura 4)

> Corresponde ao **UC24 — Alocar Professor em Disciplina e Turma** (validação das travas 20/40).

```plantuml
@startuml seq_alocar_carga_horaria
skinparam actorStyle stickman
skinparam shadowing false
skinparam backgroundColor #FFFFFF
skinparam sequence {
  ArrowColor #1E40AF
  LifeLineBorderColor #2563EB
  LifeLineBackgroundColor #DBEAFE
  ParticipantBorderColor #2563EB
  ParticipantBackgroundColor #DBEAFE
  ParticipantFontColor #1E3A8A
  ActorBorderColor #B45309
  ActorBackgroundColor #FDE68A
}

title UC24 — Alocar Carga Horária de Professor (Sala de Aula)

actor "Coordenador /\nDESUP" as A
participant "Tela de\nAlocação" as UI
participant "View de\nAlocação" as View
participant "Regras de CH\n(travas 20/40)" as Regras
participant "ORM /\nModel" as Model
database "Banco DESUP" as DB

A -> UI : acessa turma na tela de alocação
UI -> View : solicita professores elegíveis
View -> Model : consulta docentes + CH disponível
Model --> UI : lista de elegíveis
A -> UI : seleciona professor e informa CH
UI -> View : POST alocação (professor, CH)
View -> Regras : validar travas de contrato + janela

alt CH em sala <= limite do contrato (20h ES / 24t-10temp BTT) e total <= 40h e janela Aberta/Reaberta
  Regras --> View : validação OK
  View -> Model : grava alocação
  Model -> DB : persiste
  Model -> Model : recalcula CH consolidada do professor
  View --> UI : sucesso
  UI --> A : feedback de alocação registrada
else excede limite de horas em sala (4A)
  Regras --> View : bloqueio (teto do contrato atingido)
  View --> UI : erro informando o teto
else soma sala + extracurricular > 40h (4B)
  Regras --> View : bloqueio (excedente global)
  View --> UI : erro informando excedente
else janela "Fechada" e ator é Coordenador (5A)
  Regras --> View : operação impedida no servidor
  View --> UI : erro (janela fechada)
end

@enduml
```

---

## 5. Diagrama de Sequência — Alocar Carga Horária Extracurricular (Figura 5)

> Corresponde ao **UC29 — Registrar Alocação Extracurricular** (TCC, extensão, redução de CH).

```plantuml
@startuml seq_alocar_extracurricular
skinparam actorStyle stickman
skinparam shadowing false
skinparam backgroundColor #FFFFFF
skinparam sequence {
  ArrowColor #1E40AF
  LifeLineBorderColor #2563EB
  LifeLineBackgroundColor #DBEAFE
  ParticipantBorderColor #2563EB
  ParticipantBackgroundColor #DBEAFE
  ParticipantFontColor #1E3A8A
  ActorBorderColor #B45309
  ActorBackgroundColor #FDE68A
}

title UC29 — Registrar Alocação Extracurricular

actor "Coordenador /\nDESUP" as A
participant "Painel de Carga\nExtracurricular" as UI
participant "View\nExtracurricular" as View
participant "Cálculo de CH\n(limites/modalidade)" as Calc
participant "ORM /\nModel" as Model
database "Banco DESUP" as DB

A -> UI : acessa painel extracurricular do professor
UI -> View : solicita modalidades disponíveis
View --> UI : TCC / Extensão / Redução de CH
A -> UI : informa modalidade e parâmetros\n(nº orientandos / estudantes)
UI -> View : POST carga extracurricular
View -> Calc : calcular CH e validar limites + teto 40h

alt dentro do limite da modalidade e total <= 40h e janela Aberta/Reaberta
  Calc --> View : CH válida
  View -> Model : grava carga extracurricular
  Model -> DB : persiste
  Model -> Model : recalcula carga total do professor
  View --> UI : sucesso
  UI --> A : registro confirmado
else TCC excede limite da modalidade (4A)\n(máx. 8 orientandos / 4h)
  Calc --> View : bloqueio do excedente
  View --> UI : erro (limite da modalidade)
else soma sala + extracurricular > 40h (4B)
  Calc --> View : bloqueio (excedente global)
  View --> UI : erro (teto de 40h)
else janela "Fechada" e ator é Coordenador (5A)
  Calc --> View : registro definitivo impedido
  View --> UI : erro (janela fechada)
end

@enduml
```

---

## 6. Diagrama de Sequência — Registrar Ausência de Professor

> Corresponde ao **UC14 — Registrar Ausência ou Afastamento de Professor**.

```plantuml
@startuml seq_registrar_ausencia
skinparam actorStyle stickman
skinparam shadowing false
skinparam backgroundColor #FFFFFF
skinparam sequence {
  ArrowColor #1E40AF
  LifeLineBorderColor #2563EB
  LifeLineBackgroundColor #DBEAFE
  ParticipantBorderColor #2563EB
  ParticipantBackgroundColor #DBEAFE
  ParticipantFontColor #1E3A8A
  ActorBorderColor #B45309
  ActorBackgroundColor #FDE68A
}

title UC14 — Registrar Ausência ou Afastamento de Professor

actor "Coordenador /\nDESUP" as A
participant "Formulário de\nAusência" as UI
participant "View de\nAusência" as View
participant "Validação\n(dados + anexo)" as Val
participant "ORM /\nModel" as Model
database "Banco DESUP" as DB

A -> UI : acessa funcionalidade de ausência/afastamento
UI --> A : exibe formulário
A -> UI : informa tipo, período, justificativa e anexo
UI -> View : POST ausência
View -> Val : validar dados e anexo

alt dados e anexo válidos
  Val --> View : validação OK
  View -> Model : registra afastamento
  Model -> DB : persiste
  Model -> Model : atualiza status do professor (ausente/afastado)
  View --> UI : sucesso + alerta visual no painel
  UI --> A : ausência registrada
else anexo inválido (4A)
  Val --> View : rejeita envio
  View --> UI : erro (anexo inválido)
else período inconsistente (4B)
  Val --> View : impede registro
  View --> UI : erro (datas inconsistentes)
end

@enduml
```

---

## 7. Diagrama de Atividades — UC01 Realizar Autenticação (Login)

```plantuml
@startuml atv_uc01_login
skinparam shadowing false
skinparam backgroundColor #FFFFFF
skinparam ArrowColor #1E40AF
skinparam activity {
  BackgroundColor #DBEAFE
  BorderColor #2563EB
  FontColor #1E3A8A
  DiamondBackgroundColor #FEF3C7
  DiamondBorderColor #B45309
  DiamondFontColor #1E293B
  StartColor #2563EB
  EndColor #B45309
}

title UC01 — Realizar Autenticação (Login)

|#FDE68A|Usuário|
start
:Acessa a tela de login;
:Informa e-mail e senha;
|#DBEAFE|Sistema|
:Valida as credenciais;
if (Conta bloqueada por tentativas?) then (sim)
  :Impede acesso até fim do bloqueio\n(lockout 15 min);
  |#FDE68A|Usuário|
  :Visualiza aviso de bloqueio;
  stop
else (não)
  |#DBEAFE|Sistema|
  if (Credenciais válidas?) then (sim)
    :Autentica e identifica o perfil;
    if (Exige troca de senha?\n(1º acesso / política)) then (sim)
      :Redireciona para alteração de senha;
      |#FDE68A|Usuário|
      :Altera a senha;
      |#DBEAFE|Sistema|
    else (não)
    endif
    :Cria sessão e redireciona conforme perfil;
    |#FDE68A|Usuário|
    :Acessa o dashboard do perfil;
    stop
  else (não)
    :Nega autenticação\n(preserva e-mail preenchido);
    |#FDE68A|Usuário|
    :Corrige os dados e tenta novamente;
    stop
  endif
endif

@enduml
```

---

## 8. Diagrama de Atividades — UC02 Gerenciar Usuários e Permissões

> Cobre o cadastro/edição de usuários (UC04/UC05).

```plantuml
@startuml atv_uc02_usuarios
skinparam shadowing false
skinparam backgroundColor #FFFFFF
skinparam ArrowColor #1E40AF
skinparam activity {
  BackgroundColor #DBEAFE
  BorderColor #2563EB
  FontColor #1E3A8A
  DiamondBackgroundColor #FEF3C7
  DiamondBorderColor #B45309
  DiamondFontColor #1E293B
  StartColor #2563EB
  EndColor #B45309
}

title UC02 — Gerenciar Usuários e Permissões

|#FDE68A|SuperAdmin / DESUP|
start
:Acessa a gestão de usuários;
if (Ação?) then (Cadastrar)
  :Preenche dados do novo usuário\n(e-mail, perfil, unidade);
else (Editar)
  :Seleciona usuário e altera campos;
endif
|#DBEAFE|Sistema|
:Valida os dados informados;
if (E-mail já em uso?\n(no cadastro)) then (sim)
  :Rejeita e informa duplicidade;
  |#FDE68A|SuperAdmin / DESUP|
  :Corrige os dados;
  stop
else (não)
  |#DBEAFE|Sistema|
  if (Perfil x escopo/grupos compatíveis?) then (sim)
    :Associa grupos e permissões;
    :Grava o cadastro/alteração;
    :Confirma a operação;
    |#FDE68A|SuperAdmin / DESUP|
    :Visualiza confirmação;
    stop
  else (não)
    :Rejeita operação\n(combinação inválida);
    stop
  endif
endif

@enduml
```

---

## 9. Diagrama de Atividades — UC04 Estruturar Matriz Curricular

> Cobre criar/editar matriz e componentes (UC18/UC19), sob controle da janela semestral.

```plantuml
@startuml atv_uc04_matriz
skinparam shadowing false
skinparam backgroundColor #FFFFFF
skinparam ArrowColor #1E40AF
skinparam activity {
  BackgroundColor #DBEAFE
  BorderColor #2563EB
  FontColor #1E3A8A
  DiamondBackgroundColor #FEF3C7
  DiamondBorderColor #B45309
  DiamondFontColor #1E293B
  StartColor #2563EB
  EndColor #B45309
}

title UC04 — Estruturar Matriz Curricular

|#FDE68A|Coordenador / DESUP|
start
:Acessa criação/edição de matriz;
|#DBEAFE|Sistema|
if (Ator é Coordenador\nE janela "Fechada"?) then (sim)
  :Bloqueia a operação\n(mantém versão atual);
  |#FDE68A|Coordenador / DESUP|
  :Aguarda reabertura da janela;
  stop
else (não)
  |#FDE68A|Coordenador / DESUP|
  :Informa curso, período, turno e unidades;
  :Vincula componentes curriculares;
  |#DBEAFE|Sistema|
  :Valida a configuração e recalcula\nvalores derivados (créditos, CH);
  if (Conflito com matriz vigente?) then (sim)
    :Alerta e impede duplicidade de vigência;
    stop
  else (não)
    if (Dados obrigatórios completos?) then (sim)
      :Persiste a matriz como vigente;
    else (não)
      :Mantém a matriz como rascunho;
    endif
    :Confirma a operação;
    |#FDE68A|Coordenador / DESUP|
    :Visualiza matriz salva;
    stop
  endif
endif

@enduml
```

---

## 10. Diagrama de Atividades — UC05 Alocar Carga Horária de Professor (Sala de Aula)

```plantuml
@startuml atv_uc05_alocar_sala
skinparam shadowing false
skinparam backgroundColor #FFFFFF
skinparam ArrowColor #1E40AF
skinparam activity {
  BackgroundColor #DBEAFE
  BorderColor #2563EB
  FontColor #1E3A8A
  DiamondBackgroundColor #FEF3C7
  DiamondBorderColor #B45309
  DiamondFontColor #1E293B
  StartColor #2563EB
  EndColor #B45309
}

title UC05 — Alocar Carga Horária de Professor (Sala de Aula)

|#FDE68A|Coordenador / DESUP|
start
:Acessa a turma na tela de alocação;
:Seleciona professor e informa a CH;
|#DBEAFE|Sistema|
if (Ator é Coordenador\nE janela "Fechada"?) then (sim)
  :Impede a operação no servidor;
  stop
else (não)
  :Valida travas do contrato;
  if (CH em sala > limite do contrato?\n(20h ES / 24t-10temp BTT)) then (sim)
    :Bloqueia e informa o teto atingido;
    stop
  else (não)
    if (Sala + extracurricular > 40h?) then (sim)
      :Bloqueia e informa o excedente;
      stop
    else (não)
      :Grava a alocação;
      :Recalcula a CH consolidada do professor;
      :Fornece feedback de sucesso;
      |#FDE68A|Coordenador / DESUP|
      :Visualiza alocação registrada;
      stop
    endif
  endif
endif

@enduml
```

---

## 11. Diagrama de Atividades — UC06 Alocar Carga Horária Extracurricular

```plantuml
@startuml atv_uc06_extracurricular
skinparam shadowing false
skinparam backgroundColor #FFFFFF
skinparam ArrowColor #1E40AF
skinparam activity {
  BackgroundColor #DBEAFE
  BorderColor #2563EB
  FontColor #1E3A8A
  DiamondBackgroundColor #FEF3C7
  DiamondBorderColor #B45309
  DiamondFontColor #1E293B
  StartColor #2563EB
  EndColor #B45309
}

title UC06 — Alocar Carga Horária Extracurricular

|#FDE68A|Coordenador / DESUP|
start
:Acessa o painel extracurricular do professor;
:Escolhe a modalidade\n(TCC / Extensão / Redução de CH);
:Informa os parâmetros\n(nº orientandos / estudantes);
|#DBEAFE|Sistema|
:Calcula a CH resultante;
if (Excede limite da modalidade?\n(ex.: TCC máx. 8 orientandos / 4h)) then (sim)
  :Bloqueia o excedente;
  stop
else (não)
  if (Sala + extracurricular > 40h?) then (sim)
    :Bloqueia e informa o excedente;
    stop
  else (não)
    if (Ator é Coordenador\nE janela "Fechada"?) then (sim)
      :Impede o registro definitivo;
      stop
    else (não)
      :Grava a carga extracurricular;
      :Recalcula a carga total do professor;
      :Confirma o registro;
      |#FDE68A|Coordenador / DESUP|
      :Visualiza registro confirmado;
      stop
    endif
  endif
endif

@enduml
```

---

## 12. Diagrama de Atividades — UC07 Registrar Ausência de Professor

```plantuml
@startuml atv_uc07_ausencia
skinparam shadowing false
skinparam backgroundColor #FFFFFF
skinparam ArrowColor #1E40AF
skinparam activity {
  BackgroundColor #DBEAFE
  BorderColor #2563EB
  FontColor #1E3A8A
  DiamondBackgroundColor #FEF3C7
  DiamondBorderColor #B45309
  DiamondFontColor #1E293B
  StartColor #2563EB
  EndColor #B45309
}

title UC07 — Registrar Ausência de Professor

|#FDE68A|Coordenador / DESUP|
start
:Acessa a funcionalidade de ausência/afastamento;
:Informa tipo, período, justificativa e anexo;
|#DBEAFE|Sistema|
:Valida os dados e o anexo;
if (Anexo inválido?) then (sim)
  :Rejeita o envio;
  |#FDE68A|Coordenador / DESUP|
  :Corrige o anexo;
  stop
else (não)
  |#DBEAFE|Sistema|
  if (Período inconsistente?) then (sim)
    :Impede o registro;
    stop
  else (não)
    :Registra o afastamento;
    :Atualiza o status do professor\n(ausente / afastado);
    :Exibe alerta visual no painel;
    |#FDE68A|Coordenador / DESUP|
    :Visualiza a ausência registrada;
    stop
  endif
endif

@enduml
```

---

## 13. Diagrama de Atividades — UC08 Visualizar Dashboards de Indicadores

> Cobre UC34 (institucional) e UC35 (unidade), com filtro de escopo por perfil.

```plantuml
@startuml atv_uc08_dashboards
skinparam shadowing false
skinparam backgroundColor #FFFFFF
skinparam ArrowColor #1E40AF
skinparam activity {
  BackgroundColor #DBEAFE
  BorderColor #2563EB
  FontColor #1E3A8A
  DiamondBackgroundColor #FEF3C7
  DiamondBorderColor #B45309
  DiamondFontColor #1E293B
  StartColor #2563EB
  EndColor #B45309
}

title UC08 — Visualizar Dashboards de Indicadores

|#FDE68A|Usuário autenticado|
start
:Acessa o dashboard;
|#DBEAFE|Sistema|
:Aplica o filtro de escopo por perfil\n(UnitBoundManager);
if (Perfil DESUP / SuperAdmin?) then (sim)
  :Agrega dados de todas as unidades\n(visão global / institucional);
else (Coordenador)
  if (Tenta acessar outra unidade?\n(ex.: manipulação de URL)) then (sim)
    :Nega o acesso no servidor;
    stop
  else (não)
    :Restringe aos dados da própria unidade;
  endif
endif
:Renderiza indicadores de conformidade\n(matriz, pendências, prazos);
|#FDE68A|Usuário autenticado|
:Consulta e filtra por unidade / curso / período;
stop

@enduml
```

---

*Gerado a partir do "Documento de elicitação de requisitos — Sistema HARPIA-DESUP v2.5",
seções §6.1 (Estrutura Acadêmica), §6.2 (Casos de Uso — Fig. 2), §6.3 (Sequência — Figs. 3–5)
e §6 (Diagrama de Atividades — UC01, UC02, UC04, UC05, UC06, UC07, UC08).*
