# Generated by Django 4.1.1 on 2022-09-15 14:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("database", "0005_remove_title_color2"),
    ]

    operations = [
        migrations.AlterField(
            model_name="religiontrait",
            name="piety",
            field=models.FloatField(blank=True, null=True),
        ),
    ]
