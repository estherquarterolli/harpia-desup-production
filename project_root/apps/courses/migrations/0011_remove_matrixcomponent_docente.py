from django.db import migrations


class Migration(migrations.Migration):
    """Remove `MatrixComponent.docente` depois que os dados foram copiados.

    A dependência de `allocations.0005` garante que a cópia para
    `AlocacaoTurmaDocente` já rodou. Na reversão, o campo volta nulo e
    `allocations.0005` (reversa) o preenche a partir das alocações.
    """

    dependencies = [
        ('courses', '0010_matrixcomponent_quantidade_turmas'),
        ('allocations', '0005_migrar_docente_componente_para_alocacao_turma'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='matrixcomponent',
            name='docente',
        ),
    ]
