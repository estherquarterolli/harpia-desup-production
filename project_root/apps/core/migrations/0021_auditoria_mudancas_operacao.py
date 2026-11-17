from django.db import migrations, models


class Migration(migrations.Migration):
    """Auditoria: valores de antes/depois estruturados, código da operação e tela de origem."""

    dependencies = [('core', '0020_classificar_auditoria_antiga')]

    operations = [
        migrations.AddField(
            model_name='auditoriaglobal',
            name='mudancas',
            field=models.JSONField(
                blank=True, default=list,
                help_text='Lista de {campo, antes, depois} com o que mudou no registro.',
                verbose_name='Campos alterados',
            ),
        ),
        migrations.AddField(
            model_name='auditoriaglobal',
            name='operacao',
            field=models.CharField(
                blank=True, db_index=True, default='', max_length=32,
                help_text='Código comum a todos os registros gerados pela mesma ação do usuário.',
                verbose_name='Operação',
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='auditoriaglobal',
            name='caminho',
            field=models.CharField(
                blank=True, default='', max_length=255,
                help_text='Método e endereço da requisição que originou o registro.',
                verbose_name='Tela / endereço',
            ),
            preserve_default=False,
        ),
    ]
