# Prompt Reutilizável: Redis + Celery no AllocGest-DESUP

Use este prompt quando quiser continuar a implementação ou pedir ajustes relacionados a Redis, Celery, cache, filas ou tarefas assíncronas neste projeto.

```text
Quero continuar a evolução do AllocGest-DESUP com Redis e Celery.

Contexto atual:
- O projeto é Django 6.0.
- Já existe inicialização do Celery em `project_root/config/celery.py`.
- `REDIS_URL` pode ser usado como cache backend e broker.
- Em ambiente sem Redis, o projeto usa `LocMemCache` e Celery em modo eager para desenvolvimento local.
- Os envios de e-mail já foram movidos para task assíncrona com `transaction.on_commit`.

O que eu quero que você faça agora:
1. Avalie o estado atual do suporte a Redis/Celery no código.
2. Aponte o que ainda falta para produção, desenvolvimento e testes.
3. Se eu pedir implementação, altere o mínimo necessário e mantenha compatibilidade com o fluxo atual.
4. Sempre preserve a lógica de negócio e o comportamento atual das telas.
5. Antes de editar, explique brevemente o que será alterado.
6. Depois de editar, valide com uma checagem de sintaxe ou teste aplicável.

Regras:
- Não remova o fallback de desenvolvimento.
- Não transforme em requisito obrigatório instalar Redis para rodar localmente.
- Se houver risco de alteração de comportamento, proponha antes de aplicar.
- Se eu pedir “tudo”, priorize primeiro cache compartilhado, depois filas, depois jobs recorrentes.

Formato esperado da resposta:
- diagnóstico objetivo
- arquivos envolvidos
- mudanças propostas ou aplicadas
- como testar
- riscos e pendências
```

Se quiser adaptar esse prompt para um pedido mais específico, troque a última parte por algo como:

```text
Agora implemente apenas a próxima etapa: [cache compartilhado / task de e-mail / fila de exportação / job agendado].
```
