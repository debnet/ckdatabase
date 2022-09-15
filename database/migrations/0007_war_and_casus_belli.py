# Generated by Django 4.1.1 on 2022-09-15 17:12

import uuid

import common.fields
import common.utils
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("database", "0006_religion_trait_piety"),
    ]

    operations = [
        migrations.CreateModel(
            name="CasusBelli",
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
                ("wip", models.BooleanField(default=False)),
                (
                    "target_titles",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("all", "All titles"),
                            ("claim", "Claimed titles"),
                            ("de_jure", "De jure titles"),
                            ("independence_domain", "Independence"),
                            ("neighbor_land", "Neighbor land"),
                            ("neighbor_land_or_water", "Neighbor land or coast"),
                            ("none", "None"),
                        ],
                        max_length=32,
                    ),
                ),
                (
                    "target_title_tier",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("all", "All"),
                            ("county", "County"),
                            ("duchy", "Duchy"),
                            ("kingdom", "Kingdom"),
                            ("empire", "Empire"),
                        ],
                        max_length=8,
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
            ],
            options={
                "verbose_name_plural": "casus belli",
            },
        ),
        migrations.CreateModel(
            name="War",
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
                ("wip", models.BooleanField(default=False)),
                ("start_date", models.DateField(blank=True, null=True)),
                ("end_date", models.DateField(blank=True, null=True)),
                (
                    "attackers",
                    models.ManyToManyField(blank=True, related_name="attackers", to="database.character"),
                ),
                (
                    "casus_belli",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="wars",
                        to="database.casusbelli",
                    ),
                ),
                (
                    "claimant",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="claims",
                        to="database.character",
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
                    "defenders",
                    models.ManyToManyField(blank=True, related_name="defenders", to="database.character"),
                ),
                (
                    "targeted_titles",
                    models.ManyToManyField(blank=True, related_name="wars", to="database.title"),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="CasusBelliGroup",
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
                ("wip", models.BooleanField(default=False)),
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
        migrations.AddField(
            model_name="casusbelli",
            name="group",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="casus_belli",
                to="database.casusbelligroup",
            ),
        ),
    ]
