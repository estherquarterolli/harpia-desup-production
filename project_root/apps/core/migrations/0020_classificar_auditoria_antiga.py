from django.db import migrations


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
    # Migration separada da 0019 de propósito: no PostgreSQL, fazer UPDATE e depois
    # CREATE INDEX na mesma transação causa "pending trigger events".
    dependencies = [('core', '0019_auditoria_detalhada')]

    operations = [
        migrations.RunPython(classificar_registros_antigos, migrations.RunPython.noop),
    ]
