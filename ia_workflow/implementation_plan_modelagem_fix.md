# Plano de Implementação — Refatoração de Curso e Unidade

A solicitação busca resolver o problema de duplicação de cursos nos filtros e opções do sistema. Isso ocorre porque o modelo `Course` (Curso) atualmente possui uma chave estrangeira direta para `Unidade`, forçando a criação de um novo registro de curso (ex: "Administração") para cada unidade que o oferece.

Para corrigir isso, vamos implementar a arquitetura sugerida:
1. Uma tabela global `Course` (sem relação direta com unidade).
2. Uma tabela de `Unidade` (já existente).
3. Uma nova tabela associativa `CourseUnit` (CursoUnidade) para vincular quais cursos pertencem a quais unidades.

## Proposed Changes

### Modelagem de Dados (`apps/courses/models.py`)

#### [NEW] Modelo `CourseUnit`
Criaremos o novo modelo que representa um curso ofertado em uma unidade:
```python
class CourseUnit(models.Model):
    curso = models.ForeignKey('Course', on_delete=models.CASCADE, related_name='course_units')
    unidade = models.ForeignKey('core.Unidade', on_delete=models.CASCADE, related_name='course_units')
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Curso na Unidade"
        verbose_name_plural = "Cursos na Unidade"
        unique_together = ('curso', 'unidade')
        
    @property
    def nome(self):
        return self.curso.nome

    @property
    def sigla(self):
        return self.curso.sigla
```
*(Adicionaremos as propriedades `nome` e `sigla` para minimizar quebras em templates que já esperam `matriz.curso.nome`).*

#### [MODIFY] Modelo `Course`
- Remover o campo `unidade = models.ForeignKey(...)`.
- Adicionar restrição de unicidade (unique=True) nos campos `nome` e `sigla` para garantir que existam apenas cursos globais únicos.

#### [MODIFY] Modelo `CurriculumMatrix`
- Alterar o campo `curso` para apontar para `CourseUnit` em vez de `Course`.
*(Manteremos o nome do campo como `curso` no banco/ORM para evitar refatoração massiva de views/templates, mas ele apontará para a classe `CourseUnit` sob o capô).*

#### [MODIFY] Modelo `MatrixComponent`
- Alterar o campo `curso_compartilhado` para apontar para `CourseUnit`.

### Outros Modelos Afetados

#### [MODIFY] Modelo `Professor` (`apps/professors/models.py`)
- O campo `cursos = models.ManyToManyField('courses.Course', ...)` será alterado para apontar para `courses.CourseUnit`, já que os professores são alocados aos cursos de suas respectivas unidades.

#### [MODIFY] Modelo `Allocation` (`apps/allocations/models.py` - se aplicável)
- Alterar chaves estrangeiras de `Course` para `CourseUnit`.

### Ajustes no Código (Views, Forms e Seeds)

- **Views e Forms**: Todas as queries do tipo `Course.objects.filter(unidade_id=X)` serão substituídas por `CourseUnit.objects.filter(unidade_id=X)`.
- **Filtros e Duplicação**: A interface usará `CourseUnit` para listar os cursos da unidade sem repetições. A lógica de "duplicar matriz" buscará o `CourseUnit`.
- **Scripts de Seed**: Ajustaremos todos os arquivos de carga de dados (`seed_db.py`, `populate_desup.py`, `seed_faetec_completo.py`, etc.) para criar o `Course` globalmente e depois instanciar o `CourseUnit`.

---

## User Review Required

> [!WARNING]
> **Refatoração Massiva do Banco de Dados**
> A mudança afetará diretamente a estrutura relacional central do sistema.
> Se existem dados em produção ou dados vitais no banco atual, seria necessário criar migrações de dados complexas para preservar e desduplicar os registros de `Course`. Se for um ambiente de desenvolvimento/teste, é mais fácil recriar o banco e rodar os seeds novamente.

## Open Questions

> [!IMPORTANT]
> 1. **Banco de Dados**: Podemos apagar o banco de dados atual, apagar os arquivos de migração antigos, rodar o `makemigrations` do zero e re-popular usando os scripts de seed? Ou é **obrigatório** preservar os dados atuais através de uma migration de dados customizada? (Apagar e recriar os seeds é mais rápido e seguro nesta fase).
> 2. **Nomenclatura**: A nova tabela será nomeada `CourseUnit` a nível de código Python, e aparecerá como "Curso na Unidade" na interface. Concorda com essa nomenclatura?

---

## Verification Plan

### Automated Tests
- Rodar a suíte de testes existente (`pytest` ou `manage.py test`).
- Atualizar os testes unitários afetados em `apps/allocations/tests.py`, `apps/courses/tests.py`, etc.

### Manual Verification
1. Fazer login como Coordenador de Unidade.
2. Acessar a tela de Matriz Curricular.
3. Verificar que o filtro de Cursos não apresenta nomes duplicados.
4. Testar a criação de uma nova matriz e garantir que a opção "duplicar matriz" lista corretamente o curso da unidade.
5. Rodar os scripts de seed para confirmar que os dados entram perfeitamente.
