from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0006_rename_tables_harpiadb_prefix'),
    ]

    operations = [
        migrations.AddField(
            model_name='matrixcomponent',
            name='nome_temporario',
            field=models.CharField(
                blank=True,
                default='',
                help_text=(
                    'Nome da disciplina quando ela ainda não existe no catálogo de '
                    'Componentes Curriculares (uso pontual, só nesta matriz — não cria '
                    'registro em CurricularComponent). Preenchido no lugar de '
                    '`componente_curricular`, nunca junto.'
                ),
                max_length=255,
                verbose_name='Disciplina temporária',
            ),
        ),
        migrations.AlterField(
            model_name='matrixcomponent',
            name='componente_curricular',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='vinculos_matriz',
                to='courses.curricularcomponent',
                verbose_name='Componente Curricular',
            ),
        ),
    ]
