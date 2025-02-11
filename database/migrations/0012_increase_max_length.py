# Generated by Django 5.1.6 on 2025-02-10 23:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("database", "0011_new_trait_data"),
    ]

    operations = [
        migrations.AlterField(
            model_name="building",
            name="type",
            field=models.CharField(
                blank=True,
                choices=[("duchy_capital", "Duchy"), ("special", "Special")],
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name="casusbelli",
            name="target_titles",
            field=models.CharField(
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
                max_length=64,
            ),
        ),
        migrations.AlterField(
            model_name="counter",
            name="type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("archer_cavalry", "Archer cavalry"),
                    ("archers", "Archers"),
                    ("camel_cavalry", "Camel cavalry"),
                    ("elephant_cavalry", "Elephant cavalry"),
                    ("heavy_cavalry", "Heavy cavalry"),
                    ("heavy_infantry", "Heavy infantry"),
                    ("light_cavalry", "Light cavalry"),
                    ("pikemen", "Pikemen"),
                    ("siege_weapon", "Siege weapon"),
                    ("skirmishers", "Skirmishers"),
                ],
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name="doctrine",
            name="group",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AlterField(
            model_name="house",
            name="prefix",
            field=models.CharField(blank=True, max_length=32),
        ),
        migrations.AlterField(
            model_name="innovation",
            name="group",
            field=models.CharField(
                blank=True,
                choices=[
                    ("culture_group_civic", "Civic"),
                    ("culture_group_regional", "Cultural and Regional"),
                    ("culture_group_military", "Military"),
                ],
                max_length=64,
            ),
        ),
        migrations.AlterField(
            model_name="law",
            name="group",
            field=models.CharField(
                blank=True,
                choices=[
                    ("realm_law", "Realm law"),
                    ("succession_faith", "Succession faith law"),
                    ("succession_order_laws", "Succession order law"),
                    ("succession_gender_laws", "Succession gender law"),
                    ("title_succession_laws", "Title succession law"),
                ],
                max_length=64,
            ),
        ),
        migrations.AlterField(
            model_name="menatarms",
            name="type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("archer_cavalry", "Archer cavalry"),
                    ("archers", "Archers"),
                    ("camel_cavalry", "Camel cavalry"),
                    ("elephant_cavalry", "Elephant cavalry"),
                    ("heavy_cavalry", "Heavy cavalry"),
                    ("heavy_infantry", "Heavy infantry"),
                    ("light_cavalry", "Light cavalry"),
                    ("pikemen", "Pikemen"),
                    ("siege_weapon", "Siege weapon"),
                    ("skirmishers", "Skirmishers"),
                ],
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name="religion",
            name="color",
            field=models.CharField(blank=True, max_length=32),
        ),
        migrations.AlterField(
            model_name="religion",
            name="group",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AlterField(
            model_name="terrain",
            name="color",
            field=models.CharField(blank=True, max_length=32),
        ),
        migrations.AlterField(
            model_name="title",
            name="prefix",
            field=models.CharField(blank=True, max_length=32),
        ),
        migrations.AlterField(
            model_name="trait",
            name="category",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AlterField(
            model_name="traittrack",
            name="code",
            field=models.CharField(blank=True, max_length=32),
        ),
    ]
