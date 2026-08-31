# Runbook — Reparo do M2M `Professor.cursos` no Supabase (produção)

> **Objetivo:** corrigir no banco de **produção (Supabase)** o mesmo defeito já corrigido no
> banco local: a tabela `professors_professor_cursos` pode ter a coluna defasada
> `courseunit_id` em vez de `course_id`, causando **HTTP 500 em `/professores/`**.
>
> **Contexto completo:** `docs/relatorios/relatorio_correcao_professores_m2m_cursos.md`
> **Ferramenta:** `project_root/scripts/data_fixes/fix_professor_cursos_m2m.py`
>
> ⏱️ Tempo estimado: ~5 minutos. Requer apenas a **connection string do Supabase**.

---

## 0. Pré-requisitos (antes de começar)

- [ ] Acesso ao Supabase e à **connection string** do Postgres (formato
      `postgresql://USUARIO:SENHA@HOST:PORTA/NOME_DO_BANCO`).
- [ ] Terminal na raiz do projeto, com o venv disponível
      (`D:\Repositorios\HARPIA-DESUP\.venv`).
- [ ] **Recomendado:** um backup/snapshot recente do banco no Supabase (mesmo o reparo
      sendo seguro e transacional, snapshot é boa prática antes de DDL em produção).

> **Qual connection string usar:** prefira o **Session pooler (porta 5432)** ou a conexão
> direta. A URL do Supabase geralmente já exige SSL — o script/settings força
> `sslmode=require` automaticamente se faltar.

---

## 1. Apontar para o Supabase **apenas neste comando** (não editar o `.env`)

O `.env` atual aponta para o banco **local** (`harpia_db@localhost`) e **não** tem
`DATABASE_URL`. Vamos fornecer o `DATABASE_URL` do Supabase **só na sessão do terminal**,
usando as settings de desenvolvimento (que priorizam `DATABASE_URL`). Assim não há risco de
deixar seu ambiente local apontando para produção.

**PowerShell (Windows):**
```powershell
cd D:\Repositorios\HARPIA-DESUP\project_root\scripts\data_fixes

# Cole a connection string real do Supabase entre aspas:
$env:DATABASE_URL = "postgresql://postgres:SENHA@db.SEUPROJETO.supabase.co:5432/postgres"
```

> Faça isso num terminal **separado** do que você usa para o `runserver` local. Ao final
> (passo 5) removemos a variável para não afetar sessões futuras.

---

## 2. DIAGNÓSTICO primeiro (dry-run — não altera nada)

```powershell
..\..\..\.venv\Scripts\python.exe fix_professor_cursos_m2m.py
```

**Confira na saída:**
- [ ] A linha `Banco: ... @ ...` mostra o **host do Supabase** (NÃO `localhost`). Se aparecer
      `localhost`, PARE — o `DATABASE_URL` não foi lido; revise o passo 1.
- [ ] O estado reportado:

| Saída | Significado | Próximo passo |
|---|---|---|
| `[OK] Tabela já está correta` | Produção não tinha o defeito (ou já foi corrigida) | **Acabou** — vá ao passo 5 |
| `[DEFASADO] ... Linhas na tabela M2M: 0` | Defeito presente, **tabela vazia** | Passo 3 (caso simples) |
| `[DEFASADO] ... Linhas: N` (N>0) + preview | Defeito presente, **com dados** | Passo 4 (caso com dados) |
| `[!] Estado inesperado` / `ambíguo` | Situação fora do previsto | **NÃO aplique** — me chame |

---

## 3. Caso SIMPLES — tabela vazia → aplicar

```powershell
..\..\..\.venv\Scripts\python.exe fix_professor_cursos_m2m.py --apply
```

- O script detecta que **não é localhost** e pede confirmação:
  digite **`APLICAR`** (maiúsculas) para prosseguir.
- Esperado ao final:
  ```
  [SUCESSO] Reparo aplicado e commitado.
  Verificação: estado=ok, colunas=['course_id', 'id', 'professor_id'], ...
  [OK] Tabela agora está em conformidade com as migrações.
  ```
- Vá ao passo 5.

---

## 4. Caso COM DADOS — tabela não vazia → revisar antes

Se o dry-run (passo 2) mostrou linhas > 0, **leia o preview** que o script imprime:

```
Preview do mapeamento courseunit_id -> courses_courseunit.course_id:
  - linhas órfãs (courseunit inexistente):        X
  - linhas sem course_id no courseunit:           Y
  - pares (professor, course) distintos após map: Z
```

- **Se X = 0 e Y = 0** (todo mundo mapeia com segurança), pode aplicar:
  ```powershell
  ..\..\..\.venv\Scripts\python.exe fix_professor_cursos_m2m.py --apply --migrate-data
  ```
  Digite `APLICAR` na confirmação. O script mapeia `courseunit_id → course_id`,
  **deduplica** os pares `(professor, course)` e recria FK/UNIQUE, tudo em transação.

- **Se X > 0 ou Y > 0** (há linhas órfãs / sem course): o script **aborta com rollback** por
  segurança. **NÃO force.** Me envie a saída do preview — tratamos os dados manualmente
  antes (essas linhas apontam para vínculos que não têm curso correspondente).

> Em qualquer erro, o script faz **rollback** automático (transação atômica): ou aplica tudo,
> ou não aplica nada.

---

## 5. Encerrar e validar

1. **Remover a variável** para não afetar sessões futuras:
   ```powershell
   Remove-Item Env:\DATABASE_URL
   ```
2. **Validar em produção:** abra a aplicação e acesse a tela **`/professores/`** com um
   usuário Coordenador de Unidade — deve carregar sem erro 500.
3. (Opcional) Rodar o dry-run mais uma vez (repetindo o passo 1 e 2) — deve reportar
   `[OK] ... idempotente`.

---

## Resumo dos comandos (cola rápida)

```powershell
cd D:\Repositorios\HARPIA-DESUP\project_root\scripts\data_fixes
$env:DATABASE_URL = "postgresql://postgres:SENHA@db.SEUPROJETO.supabase.co:5432/postgres"

# 1) diagnóstico (sempre primeiro)
..\..\..\.venv\Scripts\python.exe fix_professor_cursos_m2m.py

# 2) aplicar — escolha UM conforme o diagnóstico:
..\..\..\.venv\Scripts\python.exe fix_professor_cursos_m2m.py --apply                 # tabela vazia
..\..\..\.venv\Scripts\python.exe fix_professor_cursos_m2m.py --apply --migrate-data  # com dados (se preview limpo)

# 3) encerrar
Remove-Item Env:\DATABASE_URL
```

---

## Salvaguardas embutidas (por que é seguro)

- **Dry-run por padrão** — sem `--apply`, nada é alterado.
- **Confirmação interativa** — em banco remoto (não-localhost), exige digitar `APLICAR`.
- **Transação atômica** — qualquer falha faz rollback total.
- **Idempotente** — se já estiver correto, não faz nada; pode rodar quantas vezes quiser.
- **Aborta com dados ambíguos** — linhas órfãs/sem curso impedem a migração automática.
- **Imprime o banco alvo** — você confirma que é o Supabase antes de aplicar.

## Alternativa (settings de produção)

Se preferir usar as settings de produção em vez de dev + `DATABASE_URL`:
```powershell
$env:DJANGO_SETTINGS_MODULE = "config.settings.production"
$env:DATABASE_URL = "postgresql://...supabase..."
$env:ALLOWED_HOSTS = "*"
..\..\..\.venv\Scripts\python.exe fix_professor_cursos_m2m.py            # e depois --apply
```
Ambos os caminhos funcionam; **dev + `DATABASE_URL` é o mais simples** e evita exigências
extras (SECRET_KEY/ALLOWED_HOSTS/HTTPS) das settings de produção.
