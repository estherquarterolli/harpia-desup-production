from django.db import migrations, models
import django.db.models.deletion


def estruturar_dados_de_solicitacoes_existentes(apps, schema_editor):
    """Recupera do texto os dados dos pedidos criados antes dos novos campos."""
    Solicitacao = apps.get_model('core', 'SolicitacaoProfessorExterno')
    ContractType = apps.get_model('professors', 'ContractType')

    prefixos = {
        'ID Funcional': 'professor_id_funcional',
        'Matrícula RH': 'professor_rh_matricula',
        'Observações': 'observacao_cadastro',
    }
    vazios = {'Não informado', 'Não informada', 'Sem observações.'}

    for solicitacao in Solicitacao.objects.filter(tipo='CADASTRO'):
        alterados = []
        for linha in (solicitacao.justificativa or '').splitlines():
            rotulo, separador, valor = linha.partition(': ')
            if not separador:
                continue
            valor = valor.strip()
            if rotulo == 'Tipo de contrato':
                if valor not in vazios:
                    contrato = ContractType.objects.filter(nome=valor).first()
                    if contrato:
                        solicitacao.tipo_contrato_solicitado_id = contrato.pk
                        alterados.append('tipo_contrato_solicitado')
                continue
            campo = prefixos.get(rotulo)
            if campo and valor not in vazios:
                setattr(solicitacao, campo, valor)
                alterados.append(campo)
        if alterados:
            solicitacao.save(update_fields=alterados)


class Migration(migrations.Migration):

    dependencies = [
        ('professors', '0012_professor_area_atuacao'),
        ('core', '0010_tipocargodiretivo_carga_reducao_horas'),
    ]

    operations = [
        migrations.AddField(
            model_name='solicitacaoprofessorexterno',
            name='observacao_cadastro',
            field=models.TextField(blank=True, verbose_name='Observações do cadastro'),
        ),
        migrations.AddField(
            model_name='solicitacaoprofessorexterno',
            name='professor_id_funcional',
            field=models.CharField(blank=True, help_text='Usado nas solicitações de cadastro.', max_length=50, verbose_name='ID funcional informado'),
        ),
        migrations.AddField(
            model_name='solicitacaoprofessorexterno',
            name='professor_rh_matricula',
            field=models.CharField(blank=True, help_text='Usado nas solicitações de cadastro.', max_length=50, verbose_name='Matrícula RH informada'),
        ),
        migrations.AddField(
            model_name='solicitacaoprofessorexterno',
            name='tipo_contrato_solicitado',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='professors.contracttype', verbose_name='Tipo de contrato informado'),
        ),
        migrations.RunPython(
            estruturar_dados_de_solicitacoes_existentes,
            migrations.RunPython.noop,
        ),
    ]
