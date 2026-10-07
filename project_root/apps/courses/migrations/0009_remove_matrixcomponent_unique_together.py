from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0008_curriculummatrix_turno_constraint'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='matrixcomponent',
            unique_together=set(),
        ),
    ]
