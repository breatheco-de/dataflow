# Generated by Django 3.2.16 on 2022-11-16 03:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dataflow', '0005_alter_datasource_table_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='pipelineexecution',
            name='incoming_stream',
            field=models.JSONField(blank=True, default=None, null=True),
        ),
    ]