# Generated by Django 4.1 on 2022-08-30 00:25

import common.fields
import common.utils
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("database", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="province",
            name="special_building",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="provinces",
                to="database.building",
            ),
        ),
        migrations.AddField(
            model_name="province",
            name="special_building_slot",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="province_slots",
                to="database.building",
            ),
        ),
        migrations.AlterField(
            model_name="titlehistory",
            name="de_jure_liege",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="de_jure_liege_history",
                to="database.title",
            ),
        ),
        migrations.AlterField(
            model_name="titlehistory",
            name="holder",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="holder_history",
                to="database.character",
            ),
        ),
        migrations.AlterField(
            model_name="titlehistory",
            name="liege",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="liege_history",
                to="database.title",
            ),
        ),
        migrations.AlterField(
            model_name="titlehistory",
            name="succession_laws",
            field=models.ManyToManyField(
                blank=True,
                limit_choices_to=models.Q(("group__icontains", "succession")),
                related_name="title_history",
                to="database.law",
            ),
        ),
        migrations.CreateModel(
            name="ProvinceHistory",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "uuid",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        unique=True,
                        verbose_name="UUID",
                    ),
                ),
                (
                    "creation_date",
                    models.DateTimeField(auto_now_add=True, verbose_name="date de création"),
                ),
                (
                    "modification_date",
                    models.DateTimeField(auto_now=True, verbose_name="date de modification"),
                ),
                ("date", models.DateField()),
                (
                    "raw_data",
                    common.fields.JsonField(
                        blank=True,
                        decoder=common.utils.JsonDecoder,
                        encoder=common.utils.JsonEncoder,
                        null=True,
                    ),
                ),
                (
                    "buildings",
                    models.ManyToManyField(blank=True, related_name="history", to="database.building"),
                ),
                (
                    "culture",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="history",
                        to="database.culture",
                    ),
                ),
                (
                    "current_user",
                    models.ForeignKey(
                        blank=True,
                        editable=False,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="dernier utilisateur",
                    ),
                ),
                (
                    "holding",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="history",
                        to="database.holding",
                    ),
                ),
                (
                    "province",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="history",
                        to="database.province",
                    ),
                ),
                (
                    "religion",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="history",
                        to="database.religion",
                    ),
                ),
            ],
            options={
                "verbose_name_plural": "province histories",
                "unique_together": {("province", "date")},
            },
        ),
    ]