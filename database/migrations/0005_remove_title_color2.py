# Generated by Django 4.1.1 on 2022-09-09 12:48

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("database", "0004_localization_and_wip"),
    ]

    operations = [
        migrations.RenameField(
            model_name="title",
            old_name="color1",
            new_name="color",
        ),
        migrations.RemoveField(
            model_name="title",
            name="color2",
        ),
    ]
