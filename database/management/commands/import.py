# coding: utf-8
import collections
import datetime
import json
import logging
import os
import re
from functools import partial

from django.core.management import BaseCommand
from tqdm.auto import tqdm

from database.ckparser import convert_color, convert_date, parse_all_files, parse_all_locales, parse_file, variables
from database.models import (
    Building,
    CasusBelli,
    CasusBelliGroup,
    Character,
    CharacterHistory,
    Counter,
    Culture,
    CultureEthnicity,
    CultureHistory,
    DeathReason,
    Doctrine,
    DoctrineTrait,
    Dynasty,
    Era,
    Ethnicity,
    Ethos,
    Heritage,
    HeritageHistory,
    Holding,
    HolySite,
    House,
    Innovation,
    Language,
    Law,
    Localization,
    MartialCustom,
    MenAtArms,
    NameList,
    Nickname,
    Province,
    ProvinceHistory,
    Religion,
    ReligionTrait,
    Terrain,
    TerrainModifier,
    Title,
    TitleHistory,
    Tradition,
    Trait,
    War,
    to_pdx_date,
)

logger = logging.getLogger(__name__)

regex_date = re.compile(r"\d{1,4}\.\d{1,2}\.\d{1,2}")
regex_sublocale = re.compile(r"(\$([^\$]+)\$)")
regex_emphasis = re.compile(r"(\[([^|\]]+)\|E\])")
regex_title = re.compile(r"^[ekdcbx]_")
title_tiers = {
    "e": "empire",
    "k": "kingdom",
    "d": "duchy",
    "c": "county",
    "b": "barony",
}

tqdm = partial(tqdm, bar_format="{l_bar:.>40}{bar}{r_bar:.<40}")


class Command(BaseCommand):
    help = "Import data from Crusader Kings repositories"
    leave_locale_alone = True

    def add_arguments(self, parser):
        parser.add_argument("base_path", type=str, help="Path to CK3 base game directory")
        parser.add_argument("mod_path", type=str, nargs="?", help="Path to mod directory")
        parser.add_argument("--save", action="store_true", help="Save parsed files")
        parser.add_argument("--unused", action="store_true", help="Include unused files")
        parser.add_argument("--reset", action="store_true", help="Reset locales and parsed files")
        parser.add_argument("--purge", action="store_true", help="Purge non created/updated records")
        parser.add_argument("--skip-locales", action="store_true", help="Skip locales")

    def handle(
        self,
        base_path,
        mod_path,
        save=False,
        unused=False,
        reset=False,
        purge=False,
        skip_locales=False,
        *args,
        **options,
    ):
        global_start = datetime.datetime.now()
        all_objects, all_stats, all_missings, all_duplicates = {}, {}, {}, {}

        def mark_as_done(model, count, date):
            total_time = (datetime.datetime.now() - date).total_seconds()
            all_stats[model._meta.object_name] = {"count": count, "time": total_time}
            with open("_all_stats.json", "w") as file:
                json.dump(all_stats, file, indent=4, sort_keys=True)
            logger.info(f"{count} {model._meta.verbose_name_plural} in {total_time:0.2f}s")

        def get_object(model, key):
            if not key or str(key) == "none":
                return None
            model_name, verbose_name = model._meta.object_name, model._meta.verbose_name
            if isinstance(key, list):
                logger.warning(f"Multiple keys {key} provided for {verbose_name}")
                key = key[-1]
            pk_field = model._meta.get_field("id")
            key = pk_field.to_python(key)
            subobjects = all_objects.setdefault(model, {})
            if key in subobjects:
                return subobjects[key]
            name = (
                get_locale(key)
                or get_locale(f"{key}_name")
                or get_locale(f"{model_name}_{key}")
                or get_locale(f"{model_name}_{key}_name")
            )
            description = (
                get_locale(f"{key}_desc")
                or get_locale(f"{key}_flavor")
                or get_locale(f"{model_name}_{key}_desc")
                or get_locale(f"{model_name}_{key}_flavor")
            )
            obj, created = model.objects.get_or_create(
                id=key,
                defaults=dict(
                    name=name,
                    description=description,
                    exists=False,
                ),
            )
            if created:
                missings = all_missings.setdefault(model._meta.object_name, [])
                missings.append(key)
                missings.sort()
                logger.warning(f'Unknown {verbose_name} created for "{key}"')
            subobjects[key] = obj
            return obj

        def keep_object(model, object, warning=True):
            objects = all_objects.setdefault(model, {})
            if object.pk in objects:
                all_duplicates.setdefault(model._meta.object_name, []).append(object.keys)
                if warning:
                    logger.warning(f'Duplicated {model._meta.verbose_name} "{object.keys}" in different files')
            objects[object.pk] = object
            missings = all_missings.setdefault(model._meta.object_name, [])
            if object.pk in missings:
                missings.remove(key)

        def get_locale(key, keep=False):
            if isinstance(key, list):
                logger.warning(f"Multiple keys {key} requested for locale")
                key = key[-1]
            locale = all_locales.get(key) or (key if keep else "") or ""
            if locale:
                for key, sublocale in regex_emphasis.findall(locale):
                    locale = locale.replace(key, all_locales.get(sublocale) or key)
                for key, sublocale in regex_sublocale.findall(locale):
                    locale = locale.replace(key, all_locales.get(sublocale) or key)
            return locale

        def get_value(item, key):
            value = item.get(key)
            if isinstance(value, dict) and "@type" in value:
                return value.get("@result") or None
            return value

        # Parsing
        if not reset and os.path.exists("_all_data.json"):
            with open("_all_data.json") as file:
                all_data = json.load(file)
        else:
            start_date = datetime.datetime.now()
            all_data = parse_all_files(base_path, keep_data=True, save=save)
            if mod_path:
                for filename in os.listdir(mod_path):
                    if not filename.endswith(".mod"):
                        continue
                    if mod_data := parse_file(os.path.join(mod_path, filename), save=False):
                        excludes = mod_data.get("replace_path") or []
                        for key in list(all_data.keys()):
                            if any(key.startswith(exclude) for exclude in excludes):
                                all_data.pop(key)
                        logger.info(f"Excluded paths by mod: {' '.join(excludes)}")
                    break
                all_data.update(parse_all_files(mod_path, keep_data=True, save=save))
            all_data = {
                key.lower(): value for key, value in sorted(all_data.items()) if unused or "unused" not in key.lower()
            }
            with open("_all_data.json", "w") as file:
                json.dump(all_data, file, indent=4)
            with open("_all_data.json") as file:
                all_data = json.load(file)
            with open("_all_variables.json", "w") as file:
                json.dump(variables, file, indent=4, sort_keys=True)
            total_time = (datetime.datetime.now() - start_date).total_seconds()
            logger.info(f"Parsing files in {total_time:0.2f}s")

        # Localization
        start_date = datetime.datetime.now()
        all_locales, current_locales = {}, {}
        if not reset and os.path.exists("_all_locales.json"):
            with open("_all_locales.json") as file:
                all_locales = json.load(file)
            if mod_path and os.path.exists("_mod_locales.json"):
                with open("_mod_locales.json") as file:
                    current_locales = json.load(file)
        else:
            current_locales = parse_all_locales(base_path)
            all_locales.update(current_locales)
            if mod_path:
                current_locales = parse_all_locales(mod_path)
                all_locales.update(current_locales)
            if mod_path:
                with open("_mod_locales.json", "w") as file:
                    json.dump(current_locales, file, indent=4, sort_keys=True)
            with open("_all_locales.json", "w") as file:
                json.dump(all_locales, file, indent=4, sort_keys=True)
            with open("_all_locales.json") as file:
                all_locales = json.load(file)
        if not skip_locales:
            for key, value in tqdm(current_locales.items(), desc="Locales"):
                localization, created = Localization.objects.import_update_or_create(
                    key=key,
                    language="en",
                    defaults=dict(
                        text=value,
                    ),
                )
                keep_object(Localization, localization)
            total_time = (datetime.datetime.now() - start_date).total_seconds()
            logger.info(f"Parsing locales in {total_time:0.2f}s")

        # Terrains
        count, start_date = 0, datetime.datetime.now()
        files = []
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/terrain_types/"):
                continue
            files.append(file)
        for file in tqdm(files, desc="Terrains"):
            subdata = all_data[file]
            for key, item in tqdm(subdata.items(), desc=os.path.basename(file), leave=False):
                if isinstance(item, list) and all(isinstance(i, dict) for i in item):
                    logger.warning(f'Duplicated terrain "{key}"')
                    all_duplicates.setdefault(Terrain._meta.object_name, []).append(key)
                    item = {k: v for d in item for k, v in d.items()}
                if not isinstance(item, dict):
                    logger.debug(f'Unexpected data for terrain "{key}": "{item}"')
                    continue
                terrain, created = Terrain.objects.import_update_or_create(
                    id=key,
                    defaults=dict(
                        name=get_locale(key) or get_locale(f"{key}_terrain"),
                        color=convert_color(item.get("color")),
                        movement_speed=get_value(item, "movement_speed"),
                        combat_width=get_value(item, "combat_width"),
                        audio_parameter=get_value(item, "audio_parameter"),
                        supply_limit=item.get("province_modifier", {}).get("supply_limit_mult"),
                        development_growth=item.get("province_modifier", {}).get("development_growth_factor"),
                        attacker_hard_casualty=item.get("attacker_modifier", {}).get("hard_casualty_modifier"),
                        attacker_retreat_losses=item.get("attacker_modifier", {}).get("retreat_losses"),
                        defender_hard_casualty=item.get("defender_modifier", {}).get("hard_casualty_modifier"),
                        defender_retreat_losses=item.get("defender_modifier", {}).get("retreat_losses"),
                        defender_advantage=item.get("defender_combat_effects", {}).get("advantage"),
                        raw_data=item,
                        exists=True,
                    ),
                )
                keep_object(Terrain, terrain)
                count += 1
                terrain.created = created
        mark_as_done(Terrain, count, start_date)

        # Men-at-arms
        count, start_date = 0, datetime.datetime.now()
        files = []
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/men_at_arms_types/"):
                continue
            files.append(file)
        for file in tqdm(files, desc="Men-at-arms"):
            subdata = all_data[file]
            for key, item in tqdm(subdata.items(), desc=os.path.basename(file), leave=False):
                if isinstance(item, list) and all(isinstance(i, dict) for i in item):
                    logger.warning(f'Duplicated men-at-arms "{key}"')
                    all_duplicates.setdefault(MenAtArms._meta.object_name, []).append(key)
                    item = {k: v for d in item for k, v in d.items()}
                if not isinstance(item, dict):
                    logger.debug(f'Unexpected data for men-at-arms "{key}": "{item}"')
                    continue
                buy_cost = get_value(item.get("buy_cost", {}), "gold")
                if isinstance(buy_cost, str):
                    buy_cost = None
                low_maintenance_cost = get_value(item.get("low_maintenance_cost", {}), "gold")
                if isinstance(low_maintenance_cost, str):
                    low_maintenance_cost = None
                high_maintenance_cost = get_value(item.get("high_maintenance_cost", {}), "gold")
                if isinstance(high_maintenance_cost, str):
                    high_maintenance_cost = None
                men_at_arms, created = MenAtArms.objects.import_update_or_create(
                    id=key,
                    defaults=dict(
                        name=get_locale(key) or get_locale(f"{key}_name"),
                        description=get_locale(f"{key}_flavor"),
                        type=get_value(item, "type"),
                        buy_cost=buy_cost,
                        low_maintenance_cost=low_maintenance_cost,
                        high_maintenance_cost=high_maintenance_cost,
                        damage=get_value(item, "damage"),
                        toughness=get_value(item, "toughness"),
                        pursuit=get_value(item, "pursuit"),
                        screen=get_value(item, "screen"),
                        siege_tier=get_value(item, "siege_tier"),
                        siege_value=get_value(item, "siege_value"),
                        stack=get_value(item, "stack"),
                        raw_data=item,
                        exists=True,
                    ),
                )
                keep_object(MenAtArms, men_at_arms)
                count += 1
                men_at_arms.created = created
                if men_at_arms.wip:
                    continue
                # Terrain modifiers
                if modifiers := item.get("terrain_bonus"):
                    for terrain, modifiers in modifiers.items():
                        terrain_modifier, _ = TerrainModifier.objects.update_or_create(
                            men_at_arms=men_at_arms,
                            terrain=get_object(Terrain, terrain),
                            defaults=dict(
                                damage=modifiers.get("damage"),
                                toughness=modifiers.get("toughness"),
                                pursuit=modifiers.get("pursuit"),
                                screen=modifiers.get("screen"),
                            ),
                        )
                        keep_object(TerrainModifier, terrain_modifier)
                # Counters
                if counters := item.get("counters"):
                    for type, factor in counters.items():
                        counter, _ = Counter.objects.update_or_create(
                            men_at_arms=men_at_arms,
                            type=type,
                            defaults=dict(
                                factor=factor,
                            ),
                        )
                        keep_object(Counter, counter)
        mark_as_done(MenAtArms, count, start_date)

        # Casus belli groups
        count, start_date = 0, datetime.datetime.now()
        files = []
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/casus_belli_groups/"):
                continue
            files.append(file)
        for file in tqdm(files, desc="Casus belli groups"):
            subdata = all_data[file]
            for key, item in tqdm(subdata.items(), desc=os.path.basename(file), leave=False):
                if isinstance(item, list) and all(isinstance(i, dict) for i in item):
                    logger.warning(f'Duplicated casus belli group "{key}"')
                    all_duplicates.setdefault(Heritage._meta.object_name, []).append(key)
                    item = {k: v for d in item for k, v in d.items()}
                if not isinstance(item, dict):
                    continue
                casus_belli_group, created = CasusBelliGroup.objects.import_update_or_create(
                    id=key,
                    defaults=dict(
                        name=get_locale(key) or get_locale(f"{key}_name"),
                        description=get_locale(f"{key}_desc"),
                        raw_data=item,
                        exists=True,
                    ),
                )
                keep_object(CasusBelliGroup, casus_belli_group)
                count += 1
                casus_belli_group.created = created
        mark_as_done(CasusBelliGroup, count, start_date)

        # Casus belli
        count, start_date = 0, datetime.datetime.now()
        files = []
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/casus_belli_types/"):
                continue
            files.append(file)
        for file in tqdm(files, desc="Casus belli"):
            subdata = all_data[file]
            for key, item in tqdm(subdata.items(), desc=os.path.basename(file), leave=False):
                if isinstance(item, list) and all(isinstance(i, dict) for i in item):
                    logger.warning(f'Duplicated casus belli "{key}"')
                    all_duplicates.setdefault(Heritage._meta.object_name, []).append(key)
                    item = {k: v for d in item for k, v in d.items()}
                if not isinstance(item, dict):
                    continue
                casus_belli, created = CasusBelli.objects.import_update_or_create(
                    id=key,
                    defaults=dict(
                        name=get_locale(key) or get_locale(f"{key}_name"),
                        description=get_locale(item.get("war_name") or f"{key}_desc"),
                        group=get_object(CasusBelliGroup, item.get("group")),
                        target_titles=get_value(item, "target_titles") or "",
                        target_title_tier=get_value(item, "target_title_tier") or "",
                        raw_data=item,
                        exists=True,
                    ),
                )
                keep_object(CasusBelli, casus_belli)
                count += 1
                casus_belli.created = created
        mark_as_done(CasusBelli, count, start_date)

        # Laws
        count, start_date = 0, datetime.datetime.now()
        files = []
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/laws/"):
                continue
            files.append(file)
        for file in tqdm(files, desc="Laws"):
            subdata = all_data[file]
            for group_key, group in tqdm(subdata.items(), desc=os.path.basename(file), leave=False):
                if not group or not isinstance(group, dict):
                    continue
                for key, item in group.items():
                    if isinstance(item, list) and all(isinstance(i, dict) for i in item):
                        logger.warning(f'Duplicated law "{key}"')
                        all_duplicates.setdefault(Law._meta.object_name, []).append(key)
                        item = {k: v for d in item for k, v in d.items()}
                    if not isinstance(item, dict):
                        logger.debug(f'Unexpected data for law "{key}": "{item}"')
                        continue
                    law, created = Law.objects.import_update_or_create(
                        id=key,
                        defaults=dict(
                            name=get_locale(key) or get_locale(f"{key}_name"),
                            description=get_locale(f"{key}_effects") or get_locale(f"{key}_desc"),
                            group=group.get("flag", group_key),
                            raw_data=item,
                            exists=True,
                        ),
                    )
                    keep_object(Law, law)
                    count += 1
                    law.created = created
        mark_as_done(Law, count, start_date)

        # Buildings
        count, start_date = 0, datetime.datetime.now()
        files = []
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/buildings/"):
                continue
            files.append(file)
        for file in tqdm(files, desc="Buildings"):
            subdata = all_data[file]
            for key, item in tqdm(subdata.items(), desc=os.path.basename(file), leave=False):
                if isinstance(item, list) and all(isinstance(i, dict) for i in item):
                    logger.warning(f'Duplicated building "{key}"')
                    all_duplicates.setdefault(Building._meta.object_name, []).append(key)
                    item = {k: v for d in item for k, v in d.items()}
                if not isinstance(item, dict):
                    logger.debug(f'Unexpected data for building "{key}": "{item}"')
                    continue
                building, created = Building.objects.import_update_or_create(
                    id=key,
                    defaults=dict(
                        name=get_locale(f"building_{key}"),
                        description=get_locale(f"building_{key}_desc"),
                        type=get_value(item, "type") or "",
                        construction_time=get_value(item, "construction_time"),
                        cost_gold=get_value(item, "cost_gold"),
                        cost_prestige=get_value(item, "cost_prestige"),
                        levy=get_value(item, "cost_gold"),
                        max_garrison=get_value(item, "max_garrison"),
                        garrison_reinforcement_factor=get_value(item, "garrison_reinforcement_factor"),
                        raw_data=item,
                        exists=True,
                    ),
                )
                keep_object(Building, building)
                count += 1
                building.created = created
        # Next buildings
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/buildings/"):
                continue
            for key, item in subdata.items():
                if not isinstance(item, dict) or not item.get("next_building"):
                    continue
                building = get_object(Building, key)
                if building.wip:
                    continue
                building.next_building = get_object(Building, item["next_building"])
                if building.modified:
                    building.save()
        mark_as_done(Building, count, start_date)

        # Ethos
        count, start_date = 0, datetime.datetime.now()
        files = []
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/culture/pillars/"):
                continue
            files.append(file)
        for file in tqdm(files, desc="Ethos"):
            subdata = all_data[file]
            for key, item in tqdm(subdata.items(), desc=os.path.basename(file), leave=False):
                if isinstance(item, list) and all(isinstance(i, dict) for i in item):
                    logger.warning(f'Duplicated ethos "{key}"')
                    item = {k: v for d in item for k, v in d.items()}
                if not isinstance(item, dict) or item.get("type") != "ethos":
                    continue
                ethos, created = Ethos.objects.import_update_or_create(
                    id=key,
                    defaults=dict(
                        name=get_locale(key) or get_locale(f"{key}_name"),
                        description=get_locale(f"{key}_desc"),
                        raw_data=item,
                        exists=True,
                    ),
                )
                keep_object(Ethos, ethos)
                count += 1
                ethos.created = created
        mark_as_done(Ethos, count, start_date)

        # Heritages
        count, start_date = 0, datetime.datetime.now()
        files = []
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/culture/pillars/"):
                continue
            files.append(file)
        for file in tqdm(files, desc="Heritages"):
            subdata = all_data[file]
            for key, item in tqdm(subdata.items(), desc=os.path.basename(file), leave=False):
                if isinstance(item, list) and all(isinstance(i, dict) for i in item):
                    logger.warning(f'Duplicated heritage "{key}"')
                    all_duplicates.setdefault(Heritage._meta.object_name, []).append(key)
                    item = {k: v for d in item for k, v in d.items()}
                if not isinstance(item, dict) or item.get("type") != "heritage":
                    continue
                heritage, created = Heritage.objects.import_update_or_create(
                    id=key,
                    defaults=dict(
                        name=get_locale(key) or get_locale(f"{key}_name"),
                        description=get_locale(f"{key}_collective_noun"),
                        raw_data=item,
                        exists=True,
                    ),
                )
                keep_object(Heritage, heritage)
                count += 1
                heritage.created = created
        mark_as_done(Heritage, count, start_date)

        # Languages
        count, start_date = 0, datetime.datetime.now()
        files = []
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/culture/pillars/"):
                continue
            files.append(file)
        for file in tqdm(files, desc="Languages"):
            subdata = all_data[file]
            for key, item in tqdm(subdata.items(), desc=os.path.basename(file), leave=False):
                if isinstance(item, list) and all(isinstance(i, dict) for i in item):
                    logger.warning(f'Duplicated language "{key}"')
                    all_duplicates.setdefault(Language._meta.object_name, []).append(key)
                    item = {k: v for d in item for k, v in d.items()}
                if not isinstance(item, dict) or item.get("type") != "language":
                    continue
                language, created = Language.objects.import_update_or_create(
                    id=key,
                    defaults=dict(
                        name=get_locale(key) or get_locale(f"{key}_name"),
                        raw_data=item,
                        exists=True,
                    ),
                )
                keep_object(Language, language)
                count += 1
                language.created = created
        mark_as_done(Language, count, start_date)

        # Martial customs
        count, start_date = 0, datetime.datetime.now()
        files = []
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/culture/pillars/"):
                continue
            files.append(file)
        for file in tqdm(files, desc="Martial customs"):
            subdata = all_data[file]
            for key, item in tqdm(subdata.items(), desc=os.path.basename(file), leave=False):
                if isinstance(item, list) and all(isinstance(i, dict) for i in item):
                    logger.warning(f'Duplicated martial custom "{key}"')
                    all_duplicates.setdefault(MartialCustom._meta.object_name, []).append(key)
                    item = {k: v for d in item for k, v in d.items()}
                if not isinstance(item, dict) or item.get("type") != "martial_custom":
                    continue
                martial_custom, created = MartialCustom.objects.import_update_or_create(
                    id=key,
                    defaults=dict(
                        name=get_locale(key) or get_locale(f"{key}_name"),
                        description=get_locale(f"{key}_desc"),
                        raw_data=item,
                        exists=True,
                    ),
                )
                keep_object(MartialCustom, martial_custom)
                count += 1
                martial_custom.created = created
        mark_as_done(MartialCustom, count, start_date)

        # Name lists
        count, start_date = 0, datetime.datetime.now()
        files = []
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/culture/name_lists/"):
                continue
            files.append(file)
        for file in tqdm(files, desc="Name lists"):
            subdata = all_data[file]
            for key, item in tqdm(subdata.items(), desc=os.path.basename(file), leave=False):
                if isinstance(item, list) and all(isinstance(i, dict) for i in item):
                    logger.warning(f'Duplicated name list "{key}"')
                    all_duplicates.setdefault(NameList._meta.object_name, []).append(key)
                    item = {k: v for d in item for k, v in d.items()}
                if not isinstance(item, dict):
                    logger.debug(f'Unexpected data for name list "{key}": "{item}"')
                    continue
                name_list, created = NameList.objects.import_update_or_create(
                    id=key,
                    defaults=dict(
                        name=get_locale(key) or get_locale(f"{key}_name"),
                        raw_data=item,
                        exists=True,
                    ),
                )
                keep_object(NameList, name_list)
                count += 1
                name_list.created = created
        mark_as_done(NameList, count, start_date)

        # Traditions
        count, start_date = 0, datetime.datetime.now()
        files = []
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/culture/traditions/"):
                continue
            files.append(file)
        for file in tqdm(files, desc="Traditions"):
            subdata = all_data[file]
            for key, item in tqdm(subdata.items(), desc=os.path.basename(file), leave=False):
                if isinstance(item, list) and all(isinstance(i, dict) for i in item):
                    logger.warning(f'Duplicated tradition "{key}"')
                    all_duplicates.setdefault(Tradition._meta.object_name, []).append(key)
                    item = {k: v for d in item for k, v in d.items()}
                if not isinstance(item, dict):
                    logger.debug(f'Unexpected data for tradition "{key}": "{item}"')
                    continue
                tradition, created = Tradition.objects.import_update_or_create(
                    id=key,
                    defaults=dict(
                        name=get_locale(key) or get_locale(f"{key}_name"),
                        description=get_locale(f"{key}_desc"),
                        category=get_value(item, "category"),
                        raw_data=item,
                        exists=True,
                    ),
                )
                keep_object(Tradition, tradition)
                count += 1
                tradition.created = created
        mark_as_done(Tradition, count, start_date)

        # Eras
        count, start_date = 0, datetime.datetime.now()
        files = []
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/culture/eras/"):
                continue
            files.append(file)
        for file in tqdm(files, desc="Eras"):
            subdata = all_data[file]
            for key, item in tqdm(subdata.items(), desc=os.path.basename(file), leave=False):
                if isinstance(item, list) and all(isinstance(i, dict) for i in item):
                    logger.warning(f'Duplicated era "{key}"')
                    all_duplicates.setdefault(Era._meta.object_name, []).append(key)
                    item = {k: v for d in item for k, v in d.items()}
                if not isinstance(item, dict):
                    logger.debug(f'Unexpected data for era "{key}": "{item}"')
                    continue
                era, created = Era.objects.import_update_or_create(
                    id=key,
                    defaults=dict(
                        name=get_locale(key) or get_locale(f"{key}_name"),
                        description=get_locale(f"{key}_desc"),
                        year=get_value(item, "year"),
                        raw_data=item,
                        exists=True,
                    ),
                )
                keep_object(Era, era)
                count += 1
                era.created = created
        mark_as_done(Era, count, start_date)

        # Innovations
        count, start_date = 0, datetime.datetime.now()
        files = []
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/culture/innovations/"):
                continue
            files.append(file)
        for file in tqdm(files, desc="Innovations"):
            subdata = all_data[file]
            for key, item in tqdm(subdata.items(), desc=os.path.basename(file), leave=False):
                if isinstance(item, list) and all(isinstance(i, dict) for i in item):
                    logger.warning(f'Duplicated innovation "{key}"')
                    all_duplicates.setdefault(Innovation._meta.object_name, []).append(key)
                    item = {k: v for d in item for k, v in d.items()}
                if not isinstance(item, dict):
                    logger.debug(f'Unexpected data for era "{key}": "{item}"')
                    continue
                innovation, created = Innovation.objects.import_update_or_create(
                    id=key,
                    defaults=dict(
                        name=get_locale(key) or get_locale(f"{key}_name"),
                        description=get_locale(f"{key}_desc"),
                        group=get_value(item, "group"),
                        era=get_object(Era, item.get("culture_era")),
                        raw_data=item,
                        exists=True,
                    ),
                )
                if laws := item.get("unlock_law"):
                    laws = laws if isinstance(laws, list) else [laws]
                    innovation.unlock_laws.set([get_object(Law, key) for key in laws])
                if men_at_arms := item.get("unlock_maa"):
                    men_at_arms = men_at_arms if isinstance(men_at_arms, list) else [men_at_arms]
                    innovation.unlock_men_at_arms.set([get_object(MenAtArms, key) for key in men_at_arms])
                if buildings := item.get("unlock_building"):
                    buildings = buildings if isinstance(buildings, list) else [buildings]
                    innovation.unlock_buildings.set([get_object(Building, key) for key in buildings])
                if casus_belli := item.get("unlock_casus_belli"):
                    casus_belli = casus_belli if isinstance(casus_belli, list) else [casus_belli]
                    innovation.unlock_casus_belli.set([get_object(CasusBelli, key) for key in casus_belli])
                keep_object(Innovation, innovation)
                count += 1
                innovation.created = created
        mark_as_done(Innovation, count, start_date)

        # Ethnicities
        count, start_date = 0, datetime.datetime.now()
        files = []
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/ethnicities/"):
                continue
            files.append(file)
        for file in tqdm(files, desc="Ethnicities"):
            subdata = all_data[file]
            for key, item in tqdm(subdata.items(), desc=os.path.basename(file), leave=False):
                if isinstance(item, list) and all(isinstance(i, dict) for i in item):
                    logger.warning(f'Duplicated ethnicity "{key}"')
                    all_duplicates.setdefault(Ethnicity._meta.object_name, []).append(key)
                    item = {k: v for d in item for k, v in d.items()}
                if not isinstance(item, dict):
                    logger.debug(f'Unexpected data for ethnicity "{key}": "{item}"')
                    continue
                if not item.get("template"):
                    continue
                ethnicity, created = Ethnicity.objects.import_update_or_create(
                    id=key,
                    defaults=dict(
                        name=get_locale(key) or get_locale(f"{key}_name"),
                        raw_data=item,
                        exists=True,
                    ),
                )
                keep_object(Ethnicity, ethnicity)
                count += 1
                ethnicity.created = created
        mark_as_done(Ethnicity, count, start_date)

        # Cultures
        count, start_date = 0, datetime.datetime.now()
        files = []
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/culture/cultures/"):
                continue
            files.append(file)
        for file in tqdm(files, desc="Cultures"):
            subdata = all_data[file]
            for key, item in tqdm(subdata.items(), desc=os.path.basename(file), leave=False):
                if isinstance(item, list) and all(isinstance(i, dict) for i in item):
                    logger.warning(f'Duplicated culture "{key}"')
                    all_duplicates.setdefault(Culture._meta.object_name, []).append(key)
                    item = {k: v for d in item for k, v in d.items()}
                if not isinstance(item, dict):
                    logger.debug(f'Unexpected data for culture "{key}": "{item}"')
                    continue
                culture, created = Culture.objects.import_update_or_create(
                    id=key,
                    defaults=dict(
                        name=get_locale(key) or get_locale(f"{key}_name"),
                        ethos=get_object(Ethos, item.get("ethos")),
                        heritage=get_object(Heritage, item.get("heritage")),
                        language=get_object(Language, item.get("language")),
                        martial_custom=get_object(MartialCustom, item.get("martial_custom")),
                        name_list=get_object(NameList, item.get("name_list")),
                        raw_data=item,
                        exists=True,
                    ),
                )
                keep_object(Culture, culture)
                count += 1
                culture.created = created
                if culture.wip:
                    continue
                # Culture traditions
                if traditions := item.get("traditions"):
                    traditions = traditions if isinstance(traditions, list) else [traditions]
                    culture.traditions.set([get_object(Tradition, key) for key in traditions])
                # Culture ethnicities
                if item.get("ethnicities"):
                    for chance, keys in item.get("ethnicities").items():
                        for key in keys if isinstance(keys, list) else [keys]:
                            culture_ethnicity, _ = CultureEthnicity.objects.update_or_create(
                                culture=culture,
                                ethnicity=get_object(Ethnicity, key),
                                defaults=dict(
                                    chance=int(chance),
                                ),
                            )
                            keep_object(CultureEthnicity, culture_ethnicity)
        mark_as_done(Culture, count, start_date)

        # Culture & heritage history
        count_heritage, count_culture, start_date = 0, 0, datetime.datetime.now()
        files = {}
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("history/cultures/"):
                continue
            key = os.path.basename(file)
            for model in (Heritage, Culture):
                instance = all_objects.setdefault(model, {}).get(key)
                if not instance or instance.wip:
                    continue
                files.setdefault(model, []).append(file)
        for model, history_model, field, name in (
            (Heritage, HeritageHistory, "heritage", "Heritage history"),
            (Culture, CultureHistory, "culture", "Culture history"),
        ):
            histories = {}
            for file in tqdm(files[model], desc=name):
                subdata = all_data[file]
                key = os.path.basename(file)
                instance = all_objects.setdefault(model, {}).get(key)
                if not instance or instance.wip:
                    continue
                for date, item in tqdm(subdata.items(), desc=os.path.basename(file), leave=False):
                    if date := regex_date.fullmatch(date) and convert_date(date, key):
                        pdx_date = to_pdx_date(date)
                        if isinstance(item, list):
                            logger.warning(f'Duplicated {field} history "{key}" for "{pdx_date}"')
                            all_duplicates.setdefault(history_model._meta.object_name, []).append((key, pdx_date))
                            item = {k: v for d in item for k, v in d.items()}
                        if not isinstance(item, dict):
                            continue
                        if previous_history := histories.get((key, date)):
                            logger.warning(f'Duplicated {field} history "{key}" for "{pdx_date}" in different files')
                            item = {**previous_history, **item}
                        histories[key, date] = item
                        history, created = history_model.objects.update_or_create(
                            defaults=dict(
                                join_era=get_object(Era, item.get("join_era")),
                                raw_data=item,
                            ),
                            date=date,
                            **{field: instance},
                        )
                        keep_object(history_model, history, warning=True)
                        count_heritage += 1 if history_model is HeritageHistory else 0
                        count_culture += 1 if history_model is CultureHistory else 0
                        history.created = created
                        if innovations := item.get("discover_innovation"):
                            innovations = innovations if isinstance(innovations, list) else [innovations]
                            history.discover_innovations.set(
                                [get_object(Innovation, innovation) for innovation in innovations]
                            )
        mark_as_done(HeritageHistory, count_heritage, start_date)
        mark_as_done(CultureHistory, count_culture, start_date)

        # Traits
        count, start_date = 0, datetime.datetime.now()
        files = []
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/traits/"):
                continue
            files.append(file)
        for file in tqdm(files, desc="Traits"):
            subdata = all_data[file]
            for key, item in tqdm(subdata.items(), desc=os.path.basename(file), leave=False):
                if isinstance(item, list) and all(isinstance(i, dict) for i in item):
                    logger.warning(f'Duplicated trait "{key}"')
                    all_duplicates.setdefault(Trait._meta.object_name, []).append(key)
                    item = {k: v for d in item for k, v in d.items()}
                if not isinstance(item, dict):
                    logger.debug(f'Unexpected data for trait "{key}": "{item}"')
                    continue
                group = None
                if group_key := item.get("group"):
                    group = all_objects.setdefault(Trait, {}).get(group_key)
                    if not group:
                        group, _ = Trait.objects.import_update_or_create(
                            id=group_key,
                            defaults=dict(
                                name=get_locale(f"trait_{group_key}"),
                                description=get_locale(f"trait_{group_key}_desc"),
                                is_group=True,
                                exists=True,
                            ),
                        )
                        keep_object(Trait, group)
                trait, created = Trait.objects.import_update_or_create(
                    id=key,
                    defaults=dict(
                        name=get_locale(f"trait_{key}"),
                        description=get_locale(f"trait_{key}_desc"),
                        group=group,
                        is_group=False,
                        category=item.get("category", ""),
                        level=item.get("level"),
                        is_good=bool(item.get("good")),
                        is_physical=bool(item.get("physical")),
                        is_genetic=bool(item.get("genetic")),
                        is_health=bool(item.get("health_trait")),
                        is_fame=bool(item.get("fame")),
                        is_incapacitating=bool(item.get("incapacitating")),
                        is_immortal=bool(item.get("immortal")),
                        has_tracks=bool(item.get("track") or item.get("tracks")),
                        can_inbred=bool(item.get("enables_inbred")),
                        can_have_children=bool(item.get("can_have_children")),
                        can_inherit=bool(item.get("can_inherit")),
                        can_not_marry=bool((item.get("flag") == "can_not_marry") or None),
                        can_be_taken=bool(item.get("shown_in_ruler_designer")),
                        cost=get_value(item, "ruler_designer_cost"),
                        inherit_chance=get_value(item, "inherit_chance"),
                        diplomacy=get_value(item, "diplomacy"),
                        martial=get_value(item, "martial"),
                        stewardship=get_value(item, "stewardship"),
                        intrigue=get_value(item, "intrigue"),
                        learning=get_value(item, "learning"),
                        prowess=get_value(item, "prowess"),
                        health=get_value(item, "health"),
                        fertility=get_value(item, "fertility"),
                        monthly_prestige=get_value(item, "monthly_prestige"),
                        monthly_prestige_mult=get_value(item, "monthly_prestige_gain_mult"),
                        monthly_piety=get_value(item, "monthly_piety"),
                        monthly_piety_mult=get_value(item, "monthly_piety_gain_mult"),
                        same_opinion=get_value(item, "same_opinion"),
                        opposite_opinion=get_value(item, "opposite_opinion"),
                        general_opinion=get_value(item, "general_opinion"),
                        attraction_opinion=get_value(item, "attraction_opinion"),
                        vassal_opinion=get_value(item, "vassal_opinion"),
                        liege_opinion=get_value(item, "liege_opinion"),
                        clergy_opinion=get_value(item, "clergy_opinion"),
                        same_faith_opinion=get_value(item, "same_faith_opinion"),
                        same_culture_opinion=get_value(item, "same_culture_opinion"),
                        dynasty_opinion=get_value(item, "dynasty_opinion"),
                        house_opinion=get_value(item, "dynasty_house_opinion"),
                        minimum_age=get_value(item, "minimum_age"),
                        maximum_age=get_value(item, "maximum_age"),
                        ai_energy=get_value(item, "ai_energy"),
                        ai_boldness=get_value(item, "ai_boldness"),
                        ai_compassion=get_value(item, "ai_compassion"),
                        ai_greed=get_value(item, "ai_greed"),
                        ai_honor=get_value(item, "ai_honor"),
                        ai_rationality=get_value(item, "ai_rationality"),
                        ai_sociability=get_value(item, "ai_sociability"),
                        ai_vengefulness=get_value(item, "ai_vengefulness"),
                        ai_zeal=get_value(item, "ai_zeal"),
                        raw_data=item,
                        exists=True,
                    ),
                )
                keep_object(Trait, trait)
                count += 1
                trait.created = created
        # Opposite traits
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/traits/"):
                continue
            for key, item in subdata.items():
                if isinstance(item, list) and all(isinstance(i, dict) for i in item):
                    item = {k: v for d in item for k, v in d.items()}
                if not isinstance(item, dict):
                    continue
                if opposites := item.get("opposites"):
                    trait = get_object(Trait, key)
                    if trait.wip:
                        continue
                    opposites = opposites if isinstance(opposites, list) else [opposites]
                    trait.opposites.set([get_object(Trait, key) for key in opposites])
        mark_as_done(Trait, count, start_date)

        # Holdings
        count, start_date = 0, datetime.datetime.now()
        files = []
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/holdings/"):
                continue
            files.append(file)
        for file in tqdm(files, desc="Holdings"):
            subdata = all_data[file]
            for key, item in tqdm(subdata.items(), desc=os.path.basename(file), leave=False):
                if isinstance(item, list) and all(isinstance(i, dict) for i in item):
                    logger.warning(f'Duplicated holding "{key}"')
                    all_duplicates.setdefault(Holding._meta.object_name, []).append(key)
                    item = {k: v for d in item for k, v in d.items()}
                if not isinstance(item, dict):
                    logger.debug(f'Unexpected data for holding "{key}": "{item}"')
                    continue
                holding, created = Holding.objects.import_update_or_create(
                    id=key,
                    defaults=dict(
                        name=get_locale(key) or get_locale(f"{key}_name"),
                        primary_building=get_object(Building, item.get("primary_building")),
                        raw_data=item,
                        exists=True,
                    ),
                )
                keep_object(Holding, holding)
                count += 1
                holding.created = created
                if holding.wip:
                    continue
                # Holding buildings
                if buildings := item.get("buildings"):
                    buildings = buildings if isinstance(buildings, list) else [buildings]
                    holding.buildings.set([get_object(Building, key) for key in buildings])
        mark_as_done(Holding, count, start_date)

        # Doctrines
        doctrines_by_group = {}
        count, start_date = 0, datetime.datetime.now()
        files = []
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/religion/doctrines/"):
                continue
            files.append(file)
        for file in tqdm(files, desc="Doctrines"):
            subdata = all_data[file]
            for group_key, group in tqdm(subdata.items(), desc=os.path.basename(file), leave=False):
                if not group or not isinstance(group, dict):
                    continue
                group_set = doctrines_by_group.setdefault(group_key, set())
                for key, item in group.items():
                    if isinstance(item, list) and all(isinstance(i, dict) for i in item):
                        logger.warning(f'Duplicated doctrine "{key}"')
                        all_duplicates.setdefault(Doctrine._meta.object_name, []).append(key)
                        item = {k: v for d in item for k, v in d.items()}
                    if not isinstance(item, dict) or not ("doctrine" in key or "tenet" in key):
                        logger.debug(f'Unexpected data for doctrine "{key}": "{item}"')
                        continue
                    group_set.add(key)
                    group_name = get_locale(group_key) or get_locale(f"{group_key}_name")
                    doctrine_name = get_locale(key) or get_locale(f"{key}_name")
                    if group_name and doctrine_name:
                        doctrine_name = f"{group_name}: {doctrine_name}"
                    doctrine, created = Doctrine.objects.import_update_or_create(
                        id=key,
                        defaults=dict(
                            name=doctrine_name,
                            description=get_locale(f"{key}_desc"),
                            group=group_key,
                            multiple=group.get("number_of_picks"),
                            raw_data=item,
                            exists=True,
                        ),
                    )
                    keep_object(Doctrine, doctrine)
                    count += 1
                    doctrine.created = created
                    if doctrine.wip:
                        continue
                    # Doctrine traits
                    if traits := item.get("traits"):
                        for trait_type, values in traits.items():
                            values = values.items() if isinstance(values, dict) else ((val, 1) for val in values)
                            for trait, piety in values:
                                if isinstance(piety, dict):
                                    piety = piety["weight"]
                                doctrine_trait, _ = DoctrineTrait.objects.update_or_create(
                                    doctrine=doctrine,
                                    trait=get_object(Trait, trait),
                                    defaults=dict(
                                        is_virtue=trait_type == "virtues",
                                        piety=piety,
                                    ),
                                )
                                keep_object(DoctrineTrait, doctrine_trait)
        mark_as_done(Doctrine, count, start_date)

        # Religions
        count, start_date = 0, datetime.datetime.now()
        files = []
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/religion/religions/"):
                continue
            files.append(file)
        for file in tqdm(files, desc="Religions"):
            subdata = all_data[file]
            for group_key, group in tqdm(subdata.items(), desc=os.path.basename(file), leave=False):
                if not group or not isinstance(group, dict):
                    continue
                group_doctrines = set(group.get("doctrine") or [])
                for key, item in group.get("faiths", {}).items():
                    if isinstance(item, list) and all(isinstance(i, dict) for i in item):
                        logger.warning(f'Duplicated religion "{key}"')
                        all_duplicates.setdefault(Religion._meta.object_name, []).append(key)
                        item = {k: v for d in item for k, v in d.items()}
                    if not isinstance(item, dict):
                        logger.debug(f'Unexpected data for religion "{key}": "{item}"')
                        continue
                    religion, created = Religion.objects.import_update_or_create(
                        id=key,
                        defaults=dict(
                            name=get_locale(key) or get_locale(f"{key}_name"),
                            description=get_locale(f"{key}_desc"),
                            group=group_key,
                            color=convert_color(item.get("color")),
                            # religious_head=get_object(Title, item.get("religious_head")),
                            raw_data=item,
                            exists=True,
                        ),
                    )
                    keep_object(Religion, religion)
                    count += 1
                    religion.created = created
                    if religion.wip:
                        continue
                    # Religion doctrines
                    doctrines = group_doctrines.copy()
                    for doctrine in item.get("doctrine") or ():
                        for name, values in doctrines_by_group.items():
                            if "tenets" in name or doctrine not in values:
                                continue
                            doctrines -= values
                            doctrines.add(doctrine)
                            break
                    if doctrines:
                        religion.doctrines.set([get_object(Doctrine, doctrine) for doctrine in doctrines])
                    # Religion traits
                    if traits := group.get("traits"):
                        for trait_type, values in traits.items():
                            values = values.items() if isinstance(values, dict) else ((val, 1) for val in values)
                            for trait, piety in values:
                                religion_trait, _ = ReligionTrait.objects.update_or_create(
                                    religion=religion,
                                    trait=get_object(Trait, trait),
                                    defaults=dict(
                                        is_virtue=trait_type == "virtues",
                                        piety=piety,
                                    ),
                                )
                                keep_object(ReligionTrait, religion_trait)
                    # Religion men-at-arms
                    if men_at_arms := group.get("holy_order_maa"):
                        men_at_arms = men_at_arms if isinstance(men_at_arms, list) else [men_at_arms]
                        religion.men_at_arms.set([get_object(MenAtArms, maa) for maa in men_at_arms])
        mark_as_done(Religion, count, start_date)

        # Province terrains
        province_terrains, default_terrain = {}, ""
        files = []
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/province_terrain/"):
                continue
            files.append(file)
        for file in tqdm(files, desc="Province terrains"):
            subdata = all_data[file]
            default_terrain = subdata.get("default")
            for key, item in tqdm(subdata.items(), desc=os.path.basename(file), leave=False):
                if not key.isdigit():
                    continue
                if isinstance(item, list):
                    logger.warning(f'Duplicated province "{key}"')
                    all_duplicates.setdefault(Province._meta.object_name, []).append(key)
                    if all(isinstance(i, dict) for i in item):
                        item = {k: v for d in item for k, v in d.items()}
                    else:
                        item = item[-1]
                if not isinstance(item, dict):
                    item = {"terrain": item}
                province_terrain = province_terrains.setdefault(str(key), {})
                province_terrain.update(item)

        provinces = {}
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("history/provinces/"):
                continue
            for key, item in subdata.items():
                provinces[key] = item

        def walk_titles(titles, from_key=None, prev_key=None):
            copy = titles.copy()
            for key, value in titles.items():
                if regex_title.match(key):
                    del copy[key]
                    yield from walk_titles(value, from_key=key, prev_key=from_key)
            if from_key:
                yield from_key, copy, prev_key

        # Provinces
        count, start_date = 0, datetime.datetime.now()
        files = []
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/landed_titles/"):
                continue
            files.append(file)
        for file in tqdm(files, desc="Provinces"):
            subdata = all_data[file]
            total = len({key for key, *_ in walk_titles(subdata)})
            all_titles = tqdm(walk_titles(subdata), total=total, desc=os.path.basename(file), leave=False)
            for key, item, liege_key in all_titles:
                if province_id := item.get("province"):
                    province_data = provinces.get(str(province_id)) or {}
                    province_data = {k: v for k, v in province_data.items() if not regex_date.fullmatch(k)}
                    terrain, winter_severity_bias = default_terrain, None
                    if province_terrain := province_terrains.get(str(province_id)):
                        terrain, winter_severity_bias = (
                            province_terrain.get("terrain", default_terrain),
                            get_value(province_terrain, "winter_severity_bias"),
                        )
                    title_prefix = get_locale(f"{key}_article")
                    title_name = get_locale(key) or get_locale(f"{key}_name")
                    if title_prefix and title_name:
                        title_name = f"{title_prefix} {title_name}"
                    province, created = Province.objects.import_update_or_create(
                        id=province_id,
                        defaults=dict(
                            name=title_name,
                            culture=get_object(Culture, province_data.get("culture")),
                            religion=get_object(Religion, province_data.get("religion")),
                            holding=get_object(Holding, province_data.get("holding")),
                            special_building_slot=get_object(Building, province_data.get("special_building_slot")),
                            special_building=get_object(Building, province_data.get("special_building")),
                            terrain=get_object(Terrain, terrain),
                            winter_severity_bias=winter_severity_bias,
                            raw_data=province_data or None,
                            exists=True,
                        ),
                    )
                    keep_object(Province, province)
                    count += 1
                    province.created = created
        mark_as_done(Province, count, start_date)

        # Province history
        histories = {}
        count, start_date = 0, datetime.datetime.now()
        for key, item in tqdm(provinces.items(), desc="Province history"):
            for date, subitem in item.items():
                if date := regex_date.fullmatch(date) and convert_date(date, key):
                    pdx_date = to_pdx_date(date)
                    if isinstance(subitem, list):
                        logger.warning(f'Duplicated province history "{key}" for "{pdx_date}"')
                        all_duplicates.setdefault(ProvinceHistory._meta.object_name, []).append((key, pdx_date))
                        subitem = {k: v for d in subitem for k, v in d.items()}
                    if not isinstance(subitem, dict):
                        continue
                    province = get_object(Province, key)
                    if province.wip:
                        continue
                    if previous_history := histories.get((key, date)):
                        logger.warning(f'Duplicated province history "{key}" for "{pdx_date}" in different files')
                        subitem = {**previous_history, **subitem}
                    histories[key, date] = subitem
                    province_history, created = ProvinceHistory.objects.update_or_create(
                        province=province,
                        date=date,
                        defaults=dict(
                            holding=get_object(Holding, subitem.get("holding")),
                            culture=get_object(Culture, subitem.get("culture")),
                            religion=get_object(Religion, subitem.get("religion")),
                            raw_data=subitem,
                        ),
                    )
                    if buildings := subitem.get("buildings"):
                        buildings = buildings if isinstance(buildings, list) else [buildings]
                        province_history.buildings.set([get_object(Building, building) for building in buildings])
                    keep_object(ProvinceHistory, province_history, warning=False)
                    count += 1
                    province_history.created = created
        mark_as_done(ProvinceHistory, count, start_date)

        # Titles
        count, start_date = 0, datetime.datetime.now()
        files = []
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/landed_titles/"):
                continue
            files.append(file)
        for file in tqdm(files, desc="Titles"):
            subdata = all_data[file]
            total = len({key for key, *_ in walk_titles(subdata)})
            all_titles = tqdm(walk_titles(subdata), total=total, desc=os.path.basename(file), leave=False)
            for key, item, liege_key in all_titles:
                province = get_object(Province, item.get("province"))
                try:
                    if province and province.title.id != key:
                        logger.warning(
                            f'Province "{province}" ({province.id}) is already related to '
                            f'title "{province.title}" ({province.title.id}) and will be deleted'
                        )
                        province_title = province.title
                        province_title.province = None
                        province_title.save(update_fields=("province",))
                except:  # noqa
                    pass
                title, created = Title.objects.import_update_or_create(
                    id=key,
                    defaults=dict(
                        name=get_locale(key) or get_locale(f"{key}_name"),
                        prefix=get_locale(f"{key}_article"),
                        tier=title_tiers.get(key.split("_")[0]),
                        color=convert_color(item.get("color")),
                        province=get_object(Province, item.get("province")),
                        raw_data=item,
                        exists=True,
                    ),
                )
                keep_object(Title, title)
                count += 1
                title.created = created
            for key, item, liege_key in walk_titles(subdata):
                title = get_object(Title, key)
                if title.wip:
                    continue
                title.de_jure_liege = get_object(Title, liege_key)
                title.capital = get_object(Title, item.get("capital"))
                if title.modified:
                    title.save()
        mark_as_done(Title, count, start_date)

        # Holy sites
        count, start_date = 0, datetime.datetime.now()
        files = []
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/religion/holy_sites/"):
                continue
            files.append(file)
        for file in tqdm(files, desc="Holy sites"):
            subdata = all_data[file]
            for key, item in tqdm(subdata.items(), desc=os.path.basename(file), leave=False):
                if isinstance(item, list) and all(isinstance(i, dict) for i in item):
                    logger.warning(f'Duplicated holy site "{key}"')
                    all_duplicates.setdefault(HolySite._meta.object_name, []).append(key)
                    item = {k: v for d in item for k, v in d.items()}
                if not isinstance(item, dict):
                    logger.debug(f'Unexpected data for holy site "{key}": "{item}"')
                    continue
                holy_site, created = HolySite.objects.import_update_or_create(
                    id=key,
                    defaults=dict(
                        name=get_locale(key) or get_locale(f"{key}_name"),
                        county=get_object(Title, item.get("county")),
                        barony=get_object(Title, item.get("barony")),
                        raw_data=item,
                        exists=True,
                    ),
                )
                keep_object(HolySite, holy_site)
                count += 1
                holy_site.created = created
        # Holy site and religious head in religions
        files = []
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/religion/religions/"):
                continue
            files.append(file)
        for file in tqdm(files, desc="Religious heads/sites"):
            subdata = all_data[file]
            for group_key, group in tqdm(subdata.items(), desc=os.path.basename(file), leave=False):
                if not group or not isinstance(group, dict):
                    continue
                for key, item in group.get("faiths", {}).items():
                    if isinstance(item, list) and all(isinstance(i, dict) for i in item):
                        item = {k: v for d in item for k, v in d.items()}
                    if not isinstance(item, dict):
                        continue
                    religion = get_object(Religion, key)
                    if religion.wip:
                        continue
                    if holy_sites := item.get("holy_site"):
                        holy_sites = holy_sites if isinstance(holy_sites, list) else [holy_sites]
                        religion.holy_sites.set([get_object(HolySite, holy_site) for holy_site in holy_sites])
                    if religious_head := item.get("religious_head"):
                        religion.religious_head = get_object(Title, religious_head)
                        if religion.modified:
                            religion.save()
        mark_as_done(HolySite, count, start_date)

        # Nicknames
        count, start_date = 0, datetime.datetime.now()
        files = []
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/nicknames/"):
                continue
            files.append(file)
        for file in tqdm(files, desc="Nicknames"):
            subdata = all_data[file]
            for key, item in tqdm(subdata.items(), desc=os.path.basename(file), leave=False):
                if isinstance(item, list) and all(isinstance(i, dict) for i in item):
                    logger.warning(f'Duplicated nickname "{key}"')
                    all_duplicates.setdefault(Nickname._meta.object_name, []).append(key)
                    item = {k: v for d in item for k, v in d.items()}
                if not isinstance(item, dict):
                    logger.debug(f'Unexpected data for nickname "{key}": "{item}"')
                    continue
                nickname, created = Nickname.objects.import_update_or_create(
                    id=key,
                    defaults=dict(
                        name=get_locale(key) or get_locale(f"{key}_name"),
                        description=get_locale(f"{key}_desc"),
                        is_bad=item.get("is_bad", False),
                        is_prefix=item.get("is_prefix", False),
                        raw_data=item,
                        exists=True,
                    ),
                )
                keep_object(Nickname, nickname)
                count += 1
                nickname.created = created
        mark_as_done(Nickname, count, start_date)

        # Death reasons
        count, start_date = 0, datetime.datetime.now()
        files = []
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/deathreasons/"):
                continue
            files.append(file)
        for file in tqdm(files, desc="Death reasons"):
            subdata = all_data[file]
            for key, item in tqdm(subdata.items(), desc=os.path.basename(file), leave=False):
                if isinstance(item, list) and all(isinstance(i, dict) for i in item):
                    logger.warning(f'Duplicated death reason "{key}"')
                    all_duplicates.setdefault(DeathReason._meta.object_name, []).append(key)
                    item = {k: v for d in item for k, v in d.items()}
                if not isinstance(item, dict):
                    logger.debug(f'Unexpected data for death reason "{key}": "{item}"')
                    continue
                death_reason, created = DeathReason.objects.import_update_or_create(
                    id=key,
                    defaults=dict(
                        name=get_locale(key) or get_locale(f"{key}_name"),
                        is_default=item.get("default", False),
                        is_natural=item.get("natural", False),
                        is_public_knowledge=item.get("public_knowledge"),
                        raw_data=item,
                        exists=True,
                    ),
                )
                keep_object(DeathReason, death_reason)
                count += 1
                death_reason.created = created
        mark_as_done(DeathReason, count, start_date)

        # Coat of Arms
        coat_of_arms = {}
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/coat_of_arms/coat_of_arms/"):
                continue
            coat_of_arms.update(subdata)

        # Dynasties
        count, start_date = 0, datetime.datetime.now()
        files = []
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/dynasties/"):
                continue
            files.append(file)
        for file in tqdm(files, desc="Dynasties"):
            subdata = all_data[file]
            for key, item in tqdm(subdata.items(), desc=os.path.basename(file), leave=False):
                if isinstance(item, list) and all(isinstance(i, dict) for i in item):
                    logger.warning(f'Duplicated dynasty "{key}"')
                    all_duplicates.setdefault(Dynasty._meta.object_name, []).append(key)
                    item = {k: v for d in item for k, v in d.items()}
                if not isinstance(item, dict):
                    logger.debug(f'Unexpected data for dynasty "{key}": "{item}"')
                    continue
                dynasty, created = Dynasty.objects.import_update_or_create(
                    id=key,
                    defaults=dict(
                        name=get_locale(item.get("name")),
                        prefix=get_locale(item.get("prefix")),
                        description=get_locale(item.get("motto")),
                        culture=get_object(Culture, item.get("culture")),
                        coa_data=coat_of_arms.get(key),
                        raw_data=item,
                        exists=True,
                    ),
                )
                keep_object(Dynasty, dynasty)
                count += 1
                dynasty.created = created
        mark_as_done(Dynasty, count, start_date)

        # Houses
        count, start_date = 0, datetime.datetime.now()
        files = []
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/dynasty_houses/"):
                continue
            files.append(file)
        for file in tqdm(files, desc="Houses"):
            subdata = all_data[file]
            for key, item in tqdm(subdata.items(), desc=os.path.basename(file), leave=False):
                if isinstance(item, list) and all(isinstance(i, dict) for i in item):
                    logger.warning(f'Duplicated house "{key}"')
                    all_duplicates.setdefault(House._meta.object_name, []).append(key)
                    item = {k: v for d in item for k, v in d.items()}
                if not isinstance(item, dict):
                    logger.debug(f'Unexpected data for house "{key}": "{item}"')
                    continue
                house, created = House.objects.import_update_or_create(
                    id=key,
                    defaults=dict(
                        name=get_locale(item.get("name")),
                        prefix=get_locale(item.get("prefix")),
                        description=get_locale(item.get("motto")),
                        dynasty=get_object(Dynasty, item.get("dynasty")),
                        coa_data=coat_of_arms.get(key),
                        raw_data=item,
                        exists=True,
                    ),
                )
                keep_object(House, house)
                count += 1
                house.created = created
        mark_as_done(House, count, start_date)

        # DNA
        dna = {}
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/dna_data/"):
                continue
            dna.update(subdata)

        # Characters
        count, start_date = 0, datetime.datetime.now()
        files = []
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("history/characters/"):
                continue
            files.append(file)
        for file in tqdm(files, desc="Characters"):
            subdata = all_data[file]
            for key, item in tqdm(subdata.items(), desc=os.path.basename(file), leave=False):
                if isinstance(item, list) and all(isinstance(i, dict) for i in item):
                    logger.warning(f'Duplicated character "{key}"')
                    all_duplicates.setdefault(Character._meta.object_name, []).append(key)
                    item = {k: v for d in item for k, v in d.items()}
                if not isinstance(item, dict):
                    logger.debug(f'Unexpected data for character "{key}": "{item}"')
                    continue
                item = {k: v for k, v in item.items() if not regex_date.fullmatch(k)}
                house = get_object(House, item.get("dynasty_house"))
                dynasty = get_object(Dynasty, item.get("dynasty"))
                dynasty = dynasty or (house.dynasty if house else None)
                character, created = Character.objects.import_update_or_create(
                    id=key,
                    defaults=dict(
                        name=get_locale(item.get("name"), keep=True),
                        gender="F" if item.get("female") else "M",
                        sexuality=item.get("sexuality", ""),
                        random_traits=not item.get("disallow_random_traits", False),
                        dynasty=dynasty,
                        house=house,
                        nickname=get_object(Nickname, item.get("give_nickname")),
                        culture=get_object(Culture, item.get("culture")),
                        religion=get_object(Religion, item.get("religion")),
                        diplomacy=get_value(item, "diplomacy"),
                        martial=get_value(item, "martial"),
                        stewardship=get_value(item, "stewardship"),
                        intrigue=get_value(item, "intrigue"),
                        learning=get_value(item, "learning"),
                        prowess=get_value(item, "prowess"),
                        gold=get_value(item, "add_gold"),
                        prestige=get_value(item, "add_prestige"),
                        piety=get_value(item, "add_piety"),
                        dna_data=dna.get(item.get("dna")) or dna.get(key),
                        raw_data=item,
                        exists=True,
                    ),
                )
                keep_object(Character, character)
                count += 1
                character.created = created
                if character.wip:
                    continue
                if traits := item.get("trait"):
                    traits = traits if isinstance(traits, list) else [traits]
                    character.traits.set([get_object(Trait, trait) for trait in traits])
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("history/characters/"):
                continue
            for key, item in subdata.items():
                if isinstance(item, list) and all(isinstance(i, dict) for i in item):
                    item = {k: v for d in item for k, v in d.items()}
                if not isinstance(item, dict):
                    continue
                if "father" in item or "mother" in item:
                    character = get_object(Character, key)
                    if character.wip:
                        continue
                    character.father = get_object(Character, item.get("father"))
                    character.mother = get_object(Character, item.get("mother"))
                    if character.modified:
                        character.save()
        mark_as_done(Character, count, start_date)

        # Character history
        histories = {}
        count, start_date = 0, datetime.datetime.now()
        files = []
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("history/characters/"):
                continue
            files.append(file)
        for file in tqdm(files, desc="Character history"):
            subdata = all_data[file]
            for key, item in tqdm(subdata.items(), desc=os.path.basename(file), leave=False):
                if isinstance(item, list) and all(isinstance(i, dict) for i in item):
                    item = {k: v for d in item for k, v in d.items()}
                if not isinstance(item, dict):
                    continue
                character = get_object(Character, key)
                if character.wip:
                    continue
                for date, subitem in item.items():
                    if date := regex_date.fullmatch(date) and convert_date(date, key):
                        pdx_date = to_pdx_date(date)
                        if isinstance(subitem, list):
                            logger.warning(f'Duplicated character history "{key}" for "{pdx_date}"')
                            all_duplicates.setdefault(CharacterHistory._meta.object_name, []).append((key, pdx_date))
                            subitem = {k: v for i in subitem for k, v in i.items() if isinstance(i, dict)}
                        if not subitem:
                            continue
                        if previous_history := histories.get((key, date)):
                            logger.warning(f'Duplicated character history "{key}" for "{pdx_date}" in different files')
                            subitem = {**previous_history, **subitem}
                        histories[key, date] = subitem
                        effect = subitem.get("effect", {})
                        if isinstance(effect, list):
                            effect = {k: v for i in effect for k, v in i.items()}
                        if culture := effect.get("set_culture"):
                            scope, culture = culture.split(":")
                            culture = get_object(Culture, culture) if scope == "culture" else None
                        event = "other"
                        if subitem.get("birth"):
                            event = "birth"
                            character.birth_date = date
                        if death := subitem.get("death"):
                            event = "death"
                            character.death_date = date
                            if isinstance(death, dict):
                                character.death_reason = get_object(DeathReason, death.get("death_reason"))
                                character.killer = get_object(Character, death.get("killer"))
                        employer, is_unemployed = None, (subitem.get("employer") == 0) or None
                        if not is_unemployed:
                            employer = get_object(Character, subitem.get("employer"))
                            is_unemployed = False if employer else is_unemployed
                        if add_soulmate := effect.get("set_relation_soulmate"):
                            if isinstance(add_soulmate, dict):
                                add_soulmate = add_soulmate.get("target")
                            scope, add_soulmate = add_soulmate.split(":")
                            add_soulmate = get_object(Character, add_soulmate) if scope == "character" else None
                        if rem_soulmate := effect.get("remove_relation_soulmate"):
                            if isinstance(rem_soulmate, dict):
                                rem_soulmate = rem_soulmate.get("target")
                            scope, rem_soulmate = rem_soulmate.split(":")
                            rem_soulmate = get_object(Character, rem_soulmate) if scope == "character" else None
                        if add_best_friend := effect.get("set_relation_best_friend"):
                            if isinstance(add_best_friend, dict):
                                add_best_friend = add_best_friend.get("target")
                            scope, add_best_friend = add_best_friend.split(":")
                            add_best_friend = get_object(Character, add_best_friend) if scope == "character" else None
                        if rem_best_friend := effect.get("remove_relation_best_friend"):
                            if isinstance(rem_best_friend, dict):
                                rem_best_friend = rem_best_friend.get("target")
                            scope, rem_best_friend = rem_best_friend.split(":")
                            rem_best_friend = get_object(Character, rem_best_friend) if scope == "character" else None
                        if add_nemesis := effect.get("set_relation_nemesis"):
                            if isinstance(add_nemesis, dict):
                                add_nemesis = add_nemesis.get("target")
                            scope, add_nemesis = add_nemesis.split(":")
                            add_nemesis = get_object(Character, add_nemesis) if scope == "character" else None
                        if rem_nemesis := effect.get("remove_relation_nemesis"):
                            if isinstance(rem_nemesis, dict):
                                rem_nemesis = rem_nemesis.get("target")
                            scope, rem_nemesis = rem_nemesis.split(":")
                            rem_nemesis = get_object(Character, rem_nemesis) if scope == "character" else None
                        if add_guardian := effect.get("set_relation_guardian"):
                            if isinstance(add_guardian, dict):
                                add_guardian = add_guardian.get("target")
                            scope, add_guardian = add_guardian.split(":")
                            add_guardian = get_object(Character, add_guardian) if scope == "character" else None
                        if rem_guardian := effect.get("remove_relation_guardian"):
                            if isinstance(rem_guardian, dict):
                                rem_guardian = rem_guardian.get("target")
                            scope, rem_guardian = rem_guardian.split(":")
                            rem_guardian = get_object(Character, rem_guardian) if scope == "character" else None
                        history, created = CharacterHistory.objects.update_or_create(
                            character=character,
                            date=date,
                            defaults=dict(
                                event=event,
                                is_unemployed=is_unemployed,
                                employer=employer,
                                add_spouse=get_object(Character, subitem.get("add_spouse")),
                                add_matrilineal_spouse=get_object(Character, subitem.get("add_matrilineal_spouse")),
                                remove_spouse=get_object(Character, subitem.get("remove_spouse")),
                                add_soulmate=add_soulmate,
                                remove_soulmate=rem_soulmate,
                                add_best_friend=add_best_friend,
                                remove_best_friend=rem_best_friend,
                                add_nemesis=add_nemesis,
                                remove_nemesis=rem_nemesis,
                                add_guardian=add_guardian,
                                remove_guardian=rem_guardian,
                                dynasty=get_object(Dynasty, subitem.get("dynasty")),
                                house=get_object(House, effect.get("set_house")),
                                nickname=get_object(Nickname, subitem.get("give_nickname")),
                                culture=culture or None,
                                religion=get_object(Religion, subitem.get("religion") or subitem.get("faith")),
                                diplomacy=get_value(subitem, "diplomacy"),
                                martial=get_value(subitem, "martial"),
                                stewardship=get_value(subitem, "stewardship"),
                                intrigue=get_value(subitem, "intrigue"),
                                learning=get_value(subitem, "learning"),
                                prowess=get_value(subitem, "prowess"),
                                gold=get_value(subitem, "add_gold") or effect.get("add_gold"),
                                prestige=get_value(subitem, "add_prestige") or effect.get("add_prestige"),
                                piety=get_value(subitem, "add_piety") or effect.get("add_piety"),
                                raw_data=subitem,
                            ),
                        )
                        keep_object(CharacterHistory, history, warning=False)
                        count += 1
                        history.created = created
                        relations_m2m = (
                            ("set_relation_lover", history.add_lovers),
                            ("remove_relation_lover", history.remove_lovers),
                            ("set_relation_potential_friend", history.add_potential_friends),
                            ("remove_relation_potential_friend", history.remove_potential_friends),
                            ("set_relation_friend", history.add_friends),
                            ("remove_relation_friend", history.remove_friends),
                            ("set_relation_potential_rival", history.add_potential_rivals),
                            ("remove_relation_potential_rival", history.remove_potential_rivals),
                            ("set_relation_rival", history.add_rivals),
                            ("remove_relation_rival", history.remove_rivals),
                        )
                        for relation, field in relations_m2m:
                            if targets := effect.get(relation):
                                values = []
                                for target in targets if isinstance(targets, list) else [targets]:
                                    if isinstance(target, dict):
                                        target = target.get("target")
                                    values.append(target.split(":"))
                                field.set(
                                    [get_object(Character, target) for scope, target in values if scope == "character"]
                                )
                        if traits := subitem.get("trait"):
                            traits = traits if isinstance(traits, list) else [traits]
                            history.traits_added.set([get_object(Trait, trait) for trait in traits])
                        if traits := subitem.get("remove_trait"):
                            traits = traits if isinstance(traits, list) else [traits]
                            history.traits_removed.set([get_object(Trait, trait) for trait in traits])
                if character.modified:
                    character.save()
        mark_as_done(CharacterHistory, count, start_date)

        # Title history
        histories = {}
        count, start_date = 0, datetime.datetime.now()
        files = []
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("history/titles/"):
                continue
            files.append(file)
        for file in tqdm(files, desc="Title history"):
            subdata = all_data[file]
            for key, item in tqdm(subdata.items(), desc=os.path.basename(file), leave=False):
                if isinstance(item, list) and all(isinstance(i, dict) for i in item):
                    logger.warning(f'Duplicated title "{key}"')
                    all_duplicates.setdefault(Title._meta.object_name, []).append(key)
                    item = {k: v for d in item for k, v in d.items()}
                if not isinstance(item, dict):
                    logger.debug(f'Unexpected data for title "{key}": "{item}"')
                    continue
                title = get_object(Title, key)
                if title.wip:
                    continue
                for date, subitem in item.items():
                    if date := regex_date.fullmatch(date) and convert_date(date, key):
                        pdx_date = to_pdx_date(date)
                        if isinstance(subitem, list):
                            logger.warning(f'Duplicated title history "{key}" for "{pdx_date}"')
                            all_duplicates.setdefault(TitleHistory._meta.object_name, []).append((key, pdx_date))
                            subitem = {k: v for i in subitem for k, v in i.items() if isinstance(i, dict)}
                        if not subitem:
                            continue
                        if previous_history := histories.get((key, date)):
                            logger.warning(f'Duplicated title history "{key}" for "{pdx_date}" in different files')
                            subitem = {**previous_history, **subitem}
                        histories[key, date] = subitem
                        liege, is_independent = None, (subitem.get("liege") == 0) or None
                        if not is_independent:
                            liege = get_object(Title, subitem.get("liege"))
                        holder, is_destroyed = None, (subitem.get("holder") == 0) or None
                        if not is_destroyed:
                            holder = get_object(Character, subitem.get("holder"))
                        history, created = TitleHistory.objects.update_or_create(
                            title=title,
                            date=date,
                            defaults=dict(
                                de_jure_liege=get_object(Title, subitem.get("de_jure_liege")),
                                liege=liege,
                                holder=holder,
                                is_independent=is_independent,
                                is_destroyed=is_destroyed,
                                development_level=get_value(subitem, "change_development_level"),
                                raw_data=subitem,
                            ),
                        )
                        keep_object(TitleHistory, history, warning=False)
                        count += 1
                        history.created = created
                        if succession_laws := subitem.get("succession_laws"):
                            succession_laws = (
                                succession_laws if isinstance(succession_laws, list) else [succession_laws]
                            )
                            history.succession_laws.set([get_object(Law, law) for law in succession_laws])
        mark_as_done(TitleHistory, count, start_date)

        # Wars
        count, start_date = 0, datetime.datetime.now()
        files = []
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("history/wars/"):
                continue
            files.append(file)
        for file in tqdm(files, desc="Wars"):
            subdata = all_data[file]
            wars = subdata.get("war")
            wars = wars if isinstance(wars, list) else [wars]
            for item in tqdm(wars, desc=os.path.basename(file), leave=False):
                if not isinstance(item, dict) and not item.get("name"):
                    continue
                war, created = War.objects.import_update_or_create(
                    id=item.get("name"),
                    defaults=dict(
                        name=get_locale(item.get("name")),
                        start_date=convert_date(item.get("start_date")),
                        end_date=convert_date(item.get("end_date")),
                        casus_belli=get_object(CasusBelli, item.get("casus_belli")),
                        claimant=get_object(Character, item.get("claimant")),
                    ),
                )
                keep_object(War, war)
                count += 1
                war.created = created
                if attackers := item.get("attackers"):
                    war.attackers.set([get_object(Character, attacker) for attacker in attackers])
                if defenders := item.get("defenders"):
                    war.defenders.set([get_object(Character, defender) for defender in defenders])
                if titles := item.get("targeted_titles"):
                    war.targeted_titles.set([get_object(Title, title) for title in titles])
        mark_as_done(War, count, start_date)

        # Mass cleaning
        all_deleted = collections.Counter()
        if purge:
            for model, keys in tqdm(all_objects.items(), desc=f"Purge"):
                deleted, total_deleted = model.objects.exclude(id__in=keys).delete()
                all_deleted.update(total_deleted or {})
            for key, value in sorted(all_deleted.items()):
                logger.info(f"{value} {key} deleted!")

        with open("_all_missings.json", "w") as file:
            json.dump(all_missings, file, indent=4, sort_keys=True)
        with open("_all_duplicates.json", "w") as file:
            json.dump(all_duplicates, file, indent=4, sort_keys=True)
        total_time = (datetime.datetime.now() - global_start).total_seconds()
        logger.info(f"Importing data in {total_time:0.2f}s")
