# Generated by Django 3.2.16 on 2024-06-29 02:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dataflow', '0009_merge_20230124_1604'),
    ]

    operations = [
        migrations.AlterField(
            model_name='project',
            name='last_pull',
            field=models.DateTimeField(blank=True, default=None, null=True),
        ),
    ]
