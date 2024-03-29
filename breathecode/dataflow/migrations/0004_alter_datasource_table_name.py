# Generated by Django 3.2.15 on 2022-10-27 00:02

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dataflow', '0003_auto_20221026_2149'),
    ]

    operations = [
        migrations.AlterField(
            model_name='datasource',
            name='table_name',
            field=models.CharField(
                blank=True,
                default=None,
                help_text=
                'Ignored for CSV. If source is a destination, we will automatically prepend pipeline slug to the table name',
                max_length=100,
                null=True),
        ),
    ]
