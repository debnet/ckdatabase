# Generated by Django 4.1 on 2022-08-30 21:12

import uuid

import common.fields
import common.utils
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("database", "0002_provinces_and_titles"),
    ]

    operations = [
        migrations.CreateModel(
            name="Era",
            fields=[
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
                (
                    "id",
                    models.CharField(max_length=64, primary_key=True, serialize=False),
                ),
                ("name", models.CharField(blank=True, max_length=128)),
                ("description", models.TextField(blank=True)),
                (
                    "raw_data",
                    common.fields.JsonField(
                        blank=True,
                        decoder=common.utils.JsonDecoder,
                        encoder=common.utils.JsonEncoder,
                        null=True,
                    ),
                ),
                ("exists", models.BooleanField(default=True)),
                ("year", models.PositiveSmallIntegerField(blank=True, null=True)),
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
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.RenameField(
            model_name="province",
            old_name="winter_severity",
            new_name="winter_severity_bias",
        ),
        migrations.RemoveField(
            model_name="menatarms",
            name="can_be_hired",
        ),
        migrations.AddField(
            model_name="building",
            name="construction_time",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="building",
            name="cost_gold",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="building",
            name="cost_prestige",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="building",
            name="garrison_reinforcement_factor",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="building",
            name="levy",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="building",
            name="max_garrison",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="building",
            name="type",
            field=models.CharField(
                blank=True,
                choices=[("duchy_capital", "Duchy"), ("special", "Special")],
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="menatarms",
            name="buy_cost",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="menatarms",
            name="high_maintenance_cost",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="menatarms",
            name="low_maintenance_cost",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="provincehistory",
            name="buildings",
            field=models.ManyToManyField(blank=True, related_name="province_history", to="database.building"),
        ),
        migrations.AlterField(
            model_name="provincehistory",
            name="culture",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="province_history",
                to="database.culture",
            ),
        ),
        migrations.AlterField(
            model_name="provincehistory",
            name="holding",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="province_history",
                to="database.holding",
            ),
        ),
        migrations.AlterField(
            model_name="provincehistory",
            name="religion",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="province_history",
                to="database.religion",
            ),
        ),
        migrations.CreateModel(
            name="Innovation",
            fields=[
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
                (
                    "id",
                    models.CharField(max_length=64, primary_key=True, serialize=False),
                ),
                ("name", models.CharField(blank=True, max_length=128)),
                ("description", models.TextField(blank=True)),
                (
                    "raw_data",
                    common.fields.JsonField(
                        blank=True,
                        decoder=common.utils.JsonDecoder,
                        encoder=common.utils.JsonEncoder,
                        null=True,
                    ),
                ),
                ("exists", models.BooleanField(default=True)),
                (
                    "group",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("culture_group_civic", "Civic"),
                            ("culture_group_regional", "Cultural and Regional"),
                            ("culture_group_military", "Military"),
                        ],
                        max_length=32,
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
                    "era",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="innovations",
                        to="database.era",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="HeritageHistory",
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
                    "discover_innovations",
                    models.ManyToManyField(
                        blank=True,
                        related_name="%(class)s_discovered",
                        to="database.innovation",
                    ),
                ),
                (
                    "heritage",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="history",
                        to="database.heritage",
                    ),
                ),
                (
                    "join_era",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_joined",
                        to="database.era",
                    ),
                ),
            ],
            options={
                "verbose_name_plural": "heritage histories",
                "unique_together": {("heritage", "date")},
            },
        ),
        migrations.CreateModel(
            name="CultureHistory",
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
                    "culture",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
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
                    "discover_innovations",
                    models.ManyToManyField(
                        blank=True,
                        related_name="%(class)s_discovered",
                        to="database.innovation",
                    ),
                ),
                (
                    "join_era",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_joined",
                        to="database.era",
                    ),
                ),
            ],
            options={
                "verbose_name_plural": "culture histories",
                "unique_together": {("culture", "date")},
            },
        ),
    ]
