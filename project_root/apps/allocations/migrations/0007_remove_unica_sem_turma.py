from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('allocations', '0006_indices_performance'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='alocacaoturmadocente',
            name='harpia_alocturmadocente_unica_sem_turma',
        ),
    ]
