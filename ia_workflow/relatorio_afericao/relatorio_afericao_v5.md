# Relatório de Aferição V5 — AllocGest-DESUP

> **Data:** 19/05/2026 | **Resultado dos Testes:** ✅ 26/26 PASSANDO | **Status do Backend:** ROBUSTO & INTEGRADO

---

## 1. Suporte do Backend para Salvar Justificativas da DESUP

O backend do AllocGest-DESUP possui **suporte completo, nativo e extremamente robusto** para salvar justificativas aprovadas, reprovadas, motivos de parecer e status consolidados. Veja como a arquitetura está implementada:

### A. Granularidade por Justificativa Individual
Cada item inserido pela Unidade possui campos dedicados de avaliação pela DESUP nos modelos `OrientacaoTCC`, `AtividadeExtensionista` e `ReducaoCargaHoraria`:
- `parecer_desup`: Campo do tipo `CharField` que utiliza o `ParecerChoices` (`PENDENTE`, `APROVADO`, `REJEITADO`).
- `motivo_parecer`: Campo do tipo `TextField` que armazena a fundamentação da DESUP (especialmente obrigatória e útil em casos de rejeição).

### B. Consolidação na Pendência Extracurricular
O cabeçalho que agrupa os itens do professor no semestre (`PendenciaExtra`) possui:
- `status`: `RASCUNHO`, `ENVIADO`, `APROVADO`, `REJEITADO`.
- `motivo_status_desup`: Campo `TextField` (gerado na migração `0002`) para salvar o motivo global da decisão da DESUP sobre aquela unidade/docente.

### C. Mecanismo de Sincronização Dinâmica (`sincronizar_status_pendencia`)
A lógica de negócio em [apps/extra_curricular/services.py](file:///d:/Repositorios/AllocGest-DESUP/project_root/apps/extra_curricular/services.py) avalia os pareceres individuais e atualiza o status global de forma inteligente:
- Se **qualquer** subitem for rejeitado (`REJEITADO`) $\rightarrow$ a pendência inteira torna-se `REJEITADO`.
- Se **todos** os subitems forem aprovados (`APROVADO`) $\rightarrow$ a pendência inteira torna-se `APROVADO`.
- Se a pendência não estiver em rascunho e houver itens pendentes $\rightarrow$ mantém-se como `ENVIADO`.

### D. Impacto na Carga Horária Justificada do Professor
No modelo [Professor](file:///d:/Repositorios/AllocGest-DESUP/project_root/apps/professors/models.py), o cálculo de `ch_justificada` foi atualizado para **somar a CH apenas se a pendência consolidada estiver aprovada**:
```python
    @property
    def ch_justificada(self) -> float:
        total = 0.0
        for pendencia in self.pendencias_extra.filter(status='APROVADO'):
            tcc = pendencia.orientacoes_tcc.aggregate(total=models.Sum('carga_horaria'))['total'] or 0
            ext = pendencia.atividades_extensao.aggregate(total=models.Sum('carga_horaria'))['total'] or 0
            red = pendencia.reducoes_ch.aggregate(total=models.Sum('horas_reduzidas'))['total'] or 0
            total += float(tcc) + float(ext) + float(red)
        return total
```
E no model `PendenciaExtra`, a propriedade `ch_total_justificada` retorna `0.0` se `status != 'APROVADO'`. Isto garante que horas não validadas pela DESUP jamais constem como computadas na carga horária ativa do docente.

---

## 2. Grandes Alterações e Revisão do Código Recente

Durante a revisão profunda do código nesta versão 5, identificamos e validamos as seguintes alterações:

### A. Campo `id_funcional` e Separação Estrita de RH vs DESUP
No modelo `Professor`, foram feitas alterações essenciais para segurança de dados:
- Adição do campo `id_funcional` (`unique=True`, `db_index=True`) para servir como o identificador primário funcional do docente.
- O campo `rh_matricula` foi renomeado e serve para auditoria interna de RH.
- Implementação de um validador `clean()` que **impede que a matrícula do RH seja idêntica ao ID Funcional**, forçando a separação:
  ```python
  def clean(self):
      super().clean()
      if self.id_funcional and self.rh_matricula and self.id_funcional == self.rh_matricula:
          raise ValidationError({"rh_matricula": "A matrícula deve ser diferente do ID Funcional."})
  ```

### B. Correção Crítica dos Testes Unitários (IntegrityError de Unique Constraint)
A introdução do campo `id_funcional` com a restrição `unique=True` causou falha em **3 testes** de isolamento de unidade e visualização de professores (`apps/core/tests.py`). Como os testes criavam professores fictícios sem preencher o `id_funcional`, o SQLite disparava erro de violação de unicidade.
- **Correção Efetuada:** Atualizamos todas as chamadas `Professor.objects.create` em [apps/core/tests.py](file:///d:/Repositorios/AllocGest-DESUP/project_root/apps/core/tests.py) para incluir valores fictícios exclusivos (`IDF001`, `IDF002`, `IDF123`) que diferem de suas respectivas matrículas, garantindo o sucesso imediato dos testes.

---

## 3. Resultado dos Testes Automatizados (V5)

```
Ran 26 tests in 85.668s — OK (All 26 tests passed!) ✅
```

Toda a suíte de testes (autenticação, redirecionamento de perfis, isolamento UnitBound, validador de número SEI, status de janela e formsets de matrizes) foi executada e retornou **100% de sucesso**.

---

## 4. Prompts Úteis para Homologação e Testes

### A. Rodar os testes unitários via console
```powershell
Set-Location d:\Repositorios\AllocGest-DESUP\project_root
python manage.py test --verbosity=2
```

### B. Popular o Banco com Dados Reais do SEI e Justificativas DESUP
Cole o seguinte script no shell do Django (`python manage.py shell`) para povoar o banco local com dados prontos para homologação do frontend da DESUP:

```python
from django.contrib.auth import get_user_model
from apps.core.models import Unidade, JanelaEntrega
from apps.professors.models import Professor, ContractType
from apps.extra_curricular.models import PendenciaExtra, OrientacaoTCC, AtividadeExtensionista, ReducaoCargaHoraria

User = get_user_model()
u_iserj = Unidade.objects.filter(sigla="ISERJ").first()
ct_sup = ContractType.objects.filter(nome__icontains="Superior").first()

if u_iserj and ct_sup:
    # Criar Professor para testes extracurriculares
    p, _ = Professor.objects.get_or_create(
        id_funcional="IDF_EXTRA_99",
        defaults={
            "rh_matricula": "M_EXTRA_99",
            "rh_nome": "Professora de Teste Extracurricular",
            "rh_email": "prof.extra@iserj.rj.gov.br",
            "unidade_principal": u_iserj,
            "tipo_contrato": ct_sup,
        }
    )
    
    # Criar Pendência Extracurricular
    pend, _ = PendenciaExtra.objects.get_or_create(
        professor=p,
        semestre="2026.1",
        defaults={
            "unidade": u_iserj,
            "status": "ENVIADO",
            "sei_numero": "SEI-123456/123456/2026"
        }
    )
    
    # Criar justificativas de TCC e Extensão
    OrientacaoTCC.objects.get_or_create(pendencia=pend, num_orientandos=6)
    AtividadeExtensionista.objects.get_or_create(pendencia=pend, num_estudantes=12)
    
    print(f"✨ Professor '{p.rh_nome}' e Pendência Extracurricular criados com sucesso no ISERJ!")
    print(f"🔗 Acesse a Mesa de Lote/Detalhes para validar os pareceres e os campos de 'motivo_parecer' no frontend.")
else:
    print("❌ Unidade ISERJ ou Contrato Superior não encontrados. Por favor, rode a semente de dados básica primeiro!")
```

---

## 5. Recomendações Técnicas

1. **Validação do ID Funcional no Frontend:** Garanta que a tela de criação/edição de professores no frontend exiba tanto o campo "ID Funcional" quanto "Matrícula RH" e realize a mesma validação para assegurar que eles sejam diferentes e únicos.
2. **Sincronização do status no admin:** Ao editar itens de parecer via Django Admin, lembre-se de chamar a função `sincronizar_status_pendencia(pendencia)` para evitar que o status da `PendenciaExtra` fique dessincronizado no frontend.
