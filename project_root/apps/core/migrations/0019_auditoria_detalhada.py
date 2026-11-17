from django.db import migrations, models


def _categoria_da_acao(acao):
    """Cópia local de `apps.core.audit.inferir_categoria` (migrations não importam código vivo)."""
    acao = (acao or '').upper()
    if acao.startswith(('LOGIN', 'LOGOUT')):
        return 'ACESSO'
    if 'PASSWORD' in acao or 'SENHA' in acao:
        return 'SEGURANCA'
    if any(chave in acao for chave in ('EXCLUID', 'REMOVID', 'DELETE')):
        return 'EXCLUSAO'
    if any(chave in acao for chave in ('CRIAD', 'CADASTRAD', 'CREATED')):
        return 'CRIACAO'
    if any(chave in acao for chave in (
        'ATUALIZAD', 'ALTERAD', 'DECIDID', 'ARQUIVAD', 'REATIVAD', 'PAUSAD', 'ENCERRAD',
    )):
        return 'ALTERACAO'
    return 'OUTRO'


def classificar_registros_antigos(apps, schema_editor):
    Auditoria = apps.get_model('core', 'AuditoriaGlobal')
    for acao in Auditoria.objects.values_list('acao', flat=True).distinct():
        categoria = _categoria_da_acao(acao)
        if categoria != 'OUTRO':
            Auditoria.objects.filter(acao=acao).update(categoria=categoria)


class Migration(migrations.Migration):
    dependencies = [('core', '0018_ocupacao_turno')]

    operations = [
        migrations.AddField(
            model_name='auditoriaglobal',
            name='perfil_usuario',
            field=models.CharField(
                blank=True, db_index=True, default='', max_length=80,
                verbose_name='Perfil de quem fez',
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='auditoriaglobal',
            name='unidade_usuario',
            field=models.CharField(
                blank=True, default='', max_length=255, verbose_name='Unidade de quem fez',
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='auditoriaglobal',
            name='categoria',
            field=models.CharField(
                choices=[
                    ('CRIACAO', 'Criação / cadastro'),
                    ('ALTERACAO', 'Alteração'),
                    ('EXCLUSAO', 'Exclusão'),
                    ('ACESSO', 'Acesso ao sistema'),
                    ('SEGURANCA', 'Segurança / senha'),
                    ('OUTRO', 'Outro'),
                ],
                db_index=True, default='OUTRO', max_length=12, verbose_name='Tipo de ação',
            ),
        ),
        migrations.AddField(
            model_name='auditoriaglobal',
            name='entidade',
            field=models.CharField(
                blank=True, db_index=True, default='', max_length=80,
                help_text='Ex.: Professor, Unidade, Curso.', verbose_name='O que foi mexido',
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='auditoriaglobal',
            name='objeto',
            field=models.CharField(
                blank=True, default='', max_length=255,
                help_text='Ex.: nome do professor, da unidade ou do curso afetado.',
                verbose_name='Nome do registro',
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='auditoriaglobal',
            name='objeto_id',
            field=models.CharField(blank=True, default='', max_length=40, verbose_name='ID do registro'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='auditoriaglobal',
            name='unidade_objeto',
            field=models.CharField(
                blank=True, default='', max_length=255,
                help_text='Unidade à qual o registro afetado pertence.',
                verbose_name='Unidade do registro',
            ),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='auditoriaglobal',
            name='email',
            field=models.EmailField(blank=True, max_length=254, verbose_name='E-mail de quem fez'),
        ),
        migrations.AlterField(
            model_name='auditoriaglobal',
            name='criado_em',
            field=models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Data e hora'),
        ),
        migrations.RunPython(classificar_registros_antigos, migrations.RunPython.noop),
    ]
