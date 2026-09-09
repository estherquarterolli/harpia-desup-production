from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("professors", "0004_remove_instrutor_contract_type"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="professor",
            name="limite_horas_extra",
        ),
    ]
