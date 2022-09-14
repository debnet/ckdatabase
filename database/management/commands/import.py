# coding: utf-8
import collections
import colorsys
import datetime
import json
import logging
import os
import re

from django.core.management import BaseCommand

from database.ckparser import parse_all_files, parse_all_locales, parse_file, variables
from database.models import (
    Building,
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
    to_pdx_date,
)

logger = logging.getLogger(__name__)

regex_date = re.compile(r"\d{1,4}\.\d{1,2}\.\d{1,2}")
regex_sublocale = re.compile(r"(\$([^\$]+)\$)")
regex_title = re.compile(r"^[ekdcbx]_")
title_tiers = {
    "e": "empire",
    "k": "kingdom",
    "d": "duchy",
    "c": "county",
    "b": "barony",
}


def convert_color(color):
    if not color:
        return ""
    if isinstance(color, str):
        return color
    if len(color) > 3 and isinstance(color[0], str):
        color_type, *color = color[:4]
        if color_type == "hsv360":
            color = [int(c) / 360 for c in color]
            color_type = "hsv"
        if color_type != "rgb":
            try:
                functions = {"hsv": colorsys.hsv_to_rgb, "hls": colorsys.hls_to_rgb}
                color = functions.get(color_type)(*color)
            except:  # noqa
                logger.warning(f"Unable to convert color {color} ({color_type}")
                return ""
    if any(isinstance(c, float) for c in color):
        color = [round(c * 255) for c in color]
    r, g, b = (hex(int(c)).split("x")[-1] for c in color[:3])
    return f"{r:02}{g:02}{b:02}"


def convert_date(date, key=None):
    if not date:
        return None
    try:
        year, month, day = (int(d) for d in date.split("."))
        return datetime.date(year, month, day)
    except Exception as error:
        logger.error(f'Error converting date "{date}" for "{key}": {error}')
        return None


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

    def handle(self, base_path, mod_path, save=False, unused=False, reset=False, purge=False, *args, **options):
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

        def keep_object(model, object):
            objects = all_objects.setdefault(model, {})
            if object.id in objects:
                all_duplicates.setdefault(model._meta.object_name, []).append(object.keys)
                logger.warning(f'Duplicated {model._meta.verbose_name} "{object.keys}" in different files')
            objects[object.pk] = object
            missings = all_missings.setdefault(model._meta.object_name, [])
            if key in missings:
                missings.remove(key)

        def get_locale(key, keep=False):
            if isinstance(key, list):
                logger.warning(f"Multiple keys {key} requested for locale")
                key = key[-1]
            locale = all_locales.get(key, key if keep else "")
            for key, sublocale in regex_sublocale.findall(locale):
                locale = locale.replace(key, all_locales.get(sublocale, key if keep else ""))
            return locale

        def get_value(item):
            if isinstance(item, dict) and "@type" in item:
                return item.get("@result") or None
            return item

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
            if os.path.exists("_mod_locales.json"):
                with open("_mod_locales.json") as file:
                    current_locales = json.load(file)
        else:
            current_locales = parse_all_locales(base_path)
            all_locales.update(current_locales)
            if mod_path:
                current_locales = parse_all_locales(mod_path)
                all_locales.update(current_locales)
            with open("_mod_locales.json", "w") as file:
                json.dump(current_locales, file, indent=4, sort_keys=True)
            with open("_all_locales.json", "w") as file:
                json.dump(all_locales, file, indent=4, sort_keys=True)
            with open("_all_locales.json") as file:
                all_locales = json.load(file)
        for key, value in current_locales.items():
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

        # Ethos
        count, start_date = 0, datetime.datetime.now()
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/culture/pillars/"):
                continue
            for key, item in subdata.items():
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

        # Heritage
        count, start_date = 0, datetime.datetime.now()
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/culture/pillars/"):
                continue
            for key, item in subdata.items():
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

        # Language
        count, start_date = 0, datetime.datetime.now()
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/culture/pillars/"):
                continue
            for key, item in subdata.items():
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

        # Martial custom
        count, start_date = 0, datetime.datetime.now()
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/culture/pillars/"):
                continue
            for key, item in subdata.items():
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

        # Name list
        count, start_date = 0, datetime.datetime.now()
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/culture/name_lists/"):
                continue
            for key, item in subdata.items():
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

        # Tradition
        count, start_date = 0, datetime.datetime.now()
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/culture/traditions/"):
                continue
            for key, item in subdata.items():
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
                        category=item.get("category"),
                        raw_data=item,
                        exists=True,
                    ),
                )
                keep_object(Tradition, tradition)
                count += 1
                tradition.created = created
        mark_as_done(Tradition, count, start_date)

        # Era
        count, start_date = 0, datetime.datetime.now()
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/culture/eras/"):
                continue
            for key, item in subdata.items():
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
                        year=item.get("year"),
                        raw_data=item,
                        exists=True,
                    ),
                )
                keep_object(Era, era)
                count += 1
                era.created = created
        mark_as_done(Era, count, start_date)

        # Innovation
        count, start_date = 0, datetime.datetime.now()
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/culture/innovations/"):
                continue
            for key, item in subdata.items():
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
                        group=item.get("group"),
                        era=get_object(Era, item.get("culture_era")),
                        raw_data=item,
                        exists=True,
                    ),
                )
                keep_object(Innovation, innovation)
                count += 1
                innovation.created = created
        mark_as_done(Innovation, count, start_date)

        # Ethnicity
        count, start_date = 0, datetime.datetime.now()
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/ethnicities/"):
                continue
            for key, item in subdata.items():
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

        # Culture
        count, start_date = 0, datetime.datetime.now()
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/culture/cultures/"):
                continue
            for key, item in subdata.items():
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
                    culture.traditions.set([get_object(Tradition, key) for key in sorted(traditions)])
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

        # Culture history
        count_heritage, count_culture, start_date = 0, 0, datetime.datetime.now()
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("history/cultures/"):
                continue
            key = os.path.basename(file)
            for model, history_model, field_name in (
                (Heritage, HeritageHistory, "heritage"),
                (Culture, CultureHistory, "culture"),
            ):
                instance = all_objects.setdefault(model, {}).get(key)
                if not instance or instance.wip:
                    continue
                for date, item in subdata.items():
                    if date := regex_date.fullmatch(date) and convert_date(date, key):
                        if isinstance(item, list):
                            pdx_date = to_pdx_date(date)
                            logger.warning(f'Duplicated {history_model._meta.verbose_name} "{key}" for "{pdx_date}"')
                            all_duplicates.setdefault(history_model._meta.object_name, []).append((key, pdx_date))
                            item = {k: v for d in item for k, v in d.items()}
                        if not isinstance(item, dict):
                            continue
                        history, created = history_model.objects.update_or_create(
                            defaults=dict(
                                join_era=get_object(Era, item.get("join_era")),
                            ),
                            date=date,
                            **{field_name: instance},
                        )
                        keep_object(history_model, history)
                        count_heritage += 1 if history_model is HeritageHistory else 0
                        count_culture += 1 if history_model is CultureHistory else 0
                        history.created = created
                        if innovations := item.get("discover_innovation"):
                            innovations = innovations if isinstance(innovations, list) else [innovations]
                            history.discover_innovations.set(
                                [get_object(Innovation, innovation) for innovation in sorted(innovations)]
                            )
        mark_as_done(HeritageHistory, count_heritage, start_date)
        mark_as_done(CultureHistory, count_culture, start_date)

        # Trait
        count, start_date = 0, datetime.datetime.now()
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/traits/"):
                continue
            for key, item in subdata.items():
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
                            name=get_locale(f"trait_{group_key}"),
                            description=get_locale(f"trait_{group_key}_desc"),
                            is_group=True,
                            exists=True,
                        )
                        keep_object(Trait, group)
                trait, created = Trait.objects.import_update_or_create(
                    id=key,
                    defaults=dict(
                        name=get_locale(f"trait_{key}"),
                        description=get_locale(f"trait_{key}_desc"),
                        is_group=False,
                        group=group,
                        level=item.get("level"),
                        is_good=item.get("good"),
                        is_physical=item.get("physical"),
                        is_genetic=item.get("genetic"),
                        is_health=item.get("health_trait"),
                        is_fame=item.get("fame"),
                        is_incapacitating=item.get("incapacitating"),
                        is_immortal=item.get("immortal"),
                        can_inbred=item.get("enables_inbred"),
                        can_have_children=item.get("can_have_children"),
                        can_inherit=item.get("can_inherit"),
                        can_not_marry=(item.get("flag") == "can_not_marry") or None,
                        can_be_taken=item.get("shown_in_ruler_designer"),
                        cost=item.get("ruler_designer_cost"),
                        inherit_chance=item.get("inherit_chance"),
                        diplomacy=item.get("diplomacy"),
                        martial=item.get("martial"),
                        stewardship=item.get("stewardship"),
                        intrigue=item.get("intrigue"),
                        learning=item.get("learning"),
                        prowess=item.get("prowess"),
                        health=item.get("health"),
                        fertility=item.get("fertility"),
                        monthly_prestige=item.get("monthly_prestige"),
                        monthly_prestige_mult=item.get("monthly_prestige_gain_mult"),
                        monthly_piety=item.get("monthly_piety"),
                        monthly_piety_mult=item.get("monthly_piety_gain_mult"),
                        same_opinion=item.get("same_opinion"),
                        opposite_opinion=item.get("opposite_opinion"),
                        general_opinion=item.get("general_opinion"),
                        attraction_opinion=item.get("attraction_opinion"),
                        vassal_opinion=item.get("vassal_opinion"),
                        clergy_opinion=item.get("clergy_opinion"),
                        same_faith_opinion=item.get("same_faith_opinion"),
                        dynasty_opinion=item.get("dynasty_opinion"),
                        house_opinion=item.get("dynasty_house_opinion"),
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
                    trait.opposites.set([get_object(Trait, key) for key in sorted(opposites)])
        mark_as_done(Trait, count, start_date)

        # Building
        count, start_date = 0, datetime.datetime.now()
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/buildings/"):
                continue
            for key, item in subdata.items():
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
                        type=item.get("type") or "",
                        construction_time=get_value(item.get("construction_time")),
                        cost_gold=get_value(item.get("cost_gold")),
                        cost_prestige=get_value(item.get("cost_prestige")),
                        levy=get_value(item.get("cost_gold")),
                        max_garrison=get_value(item.get("max_garrison")),
                        garrison_reinforcement_factor=get_value(item.get("garrison_reinforcement_factor")),
                        raw_data=item,
                        exists=True,
                    ),
                )
                keep_object(Building, building)
                count += 1
                building.created = created
        # Next building
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

        # Holding
        count, start_date = 0, datetime.datetime.now()
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/holdings/"):
                continue
            for key, item in subdata.items():
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
                    holding.buildings.set([get_object(Building, key) for key in sorted(buildings)])
        mark_as_done(Holding, count, start_date)

        # Terrain
        count, start_date = 0, datetime.datetime.now()
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/terrain_types/"):
                continue
            for key, item in subdata.items():
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
                        movement_speed=item.get("movement_speed"),
                        combat_width=item.get("combat_width"),
                        audio_parameter=item.get("audio_parameter"),
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
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/men_at_arms_types/"):
                continue
            for key, item in subdata.items():
                if isinstance(item, list) and all(isinstance(i, dict) for i in item):
                    logger.warning(f'Duplicated men-at-arms "{key}"')
                    all_duplicates.setdefault(MenAtArms._meta.object_name, []).append(key)
                    item = {k: v for d in item for k, v in d.items()}
                if not isinstance(item, dict):
                    logger.debug(f'Unexpected data for men-at-arms "{key}": "{item}"')
                    continue
                men_at_arms, created = MenAtArms.objects.import_update_or_create(
                    id=key,
                    defaults=dict(
                        name=get_locale(key) or get_locale(f"{key}_name"),
                        description=get_locale(f"{key}_flavor"),
                        type=item.get("type"),
                        buy_cost=get_value(item.get("buy_cost", {}).get("gold")),
                        low_maintenance_cost=get_value(item.get("low_maintenance_cost", {}).get("gold")),
                        high_maintenance_cost=get_value(item.get("high_maintenance_cost", {}).get("gold")),
                        damage=item.get("damage"),
                        toughness=item.get("toughness"),
                        pursuit=item.get("pursuit"),
                        screen=item.get("screen"),
                        siege_tier=item.get("siege_tier"),
                        siege_value=item.get("siege_value"),
                        stack=item.get("stack"),
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

        # Doctrines
        doctrines_by_group = {}
        count, start_date = 0, datetime.datetime.now()
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/religion/doctrines/"):
                continue
            for group_key, group in subdata.items():
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

        # Religion
        count, start_date = 0, datetime.datetime.now()
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/religion/religions/"):
                continue
            for group_key, group in subdata.items():
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
                        religion.doctrines.set([get_object(Doctrine, doctrine) for doctrine in sorted(doctrines)])
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
                        religion.men_at_arms.set([get_object(MenAtArms, maa) for maa in sorted(men_at_arms)])
        mark_as_done(Religion, count, start_date)

        # Province
        province_terrains, default_terrain = {}, ""
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/province_terrain/"):
                continue
            default_terrain = subdata.get("default")
            for key, item in subdata.items():
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

        count, start_date = 0, datetime.datetime.now()
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/landed_titles/"):
                continue
            for key, item, liege_key in walk_titles(subdata):
                if province_id := item.get("province"):
                    province_data = provinces.get(str(province_id)) or {}
                    province_data = {k: v for k, v in province_data.items() if not regex_date.fullmatch(k)}
                    terrain, winter_severity_bias = default_terrain, None
                    if province_terrain := province_terrains.get(str(province_id)):
                        terrain, winter_severity_bias = (
                            province_terrain.get("terrain", default_terrain),
                            get_value(province_terrain.get("winter_severity_bias")),
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
        count, start_date = 0, datetime.datetime.now()
        for key, item in provinces.items():
            for date, subitem in item.items():
                if date := regex_date.fullmatch(date) and convert_date(date, key):
                    if isinstance(subitem, list):
                        pdx_date = to_pdx_date(date)
                        logger.warning(f'Duplicated province history "{key}" for "{pdx_date}"')
                        all_duplicates.setdefault(ProvinceHistory._meta.object_name, []).append((key, pdx_date))
                        subitem = {k: v for d in subitem for k, v in d.items()}
                    if not isinstance(subitem, dict):
                        continue
                    province = get_object(Province, key)
                    if province.wip:
                        continue
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
                        province_history.buildings.set(
                            [get_object(Building, building) for building in sorted(buildings)]
                        )
                    keep_object(ProvinceHistory, province_history)
                    count += 1
                    province_history.created = created
        mark_as_done(ProvinceHistory, count, start_date)

        # Title
        count, start_date = 0, datetime.datetime.now()
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/landed_titles/"):
                continue
            item = {k: v for k, v in item.items() if not regex_date.fullmatch(k)}
            for key, item, liege_key in walk_titles(subdata):
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

        # Holy site
        count, start_date = 0, datetime.datetime.now()
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/religion/holy_sites/"):
                continue
            for key, item in subdata.items():
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
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/religion/religions/"):
                continue
            for group_key, group in subdata.items():
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
                        religion.holy_sites.set([get_object(HolySite, holy_site) for holy_site in sorted(holy_sites)])
                    if religious_head := item.get("religious_head"):
                        religion.religious_head = get_object(Title, religious_head)
                        if religion.modified:
                            religion.save()
        mark_as_done(HolySite, count, start_date)

        # Nicknames
        count, start_date = 0, datetime.datetime.now()
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/nicknames/"):
                continue
            for key, item in subdata.items():
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
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/deathreasons/"):
                continue
            for key, item in subdata.items():
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

        # Dynasty
        count, start_date = 0, datetime.datetime.now()
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/dynasties/"):
                continue
            for key, item in subdata.items():
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

        # House
        count, start_date = 0, datetime.datetime.now()
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/dynasty_houses/"):
                continue
            for key, item in subdata.items():
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

        # Character
        count, start_date = 0, datetime.datetime.now()
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("history/characters/"):
                continue
            for key, item in subdata.items():
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
                        diplomacy=item.get("diplomacy"),
                        martial=item.get("martial"),
                        stewardship=item.get("stewardship"),
                        intrigue=item.get("intrigue"),
                        learning=item.get("learning"),
                        prowess=item.get("prowess"),
                        gold=item.get("add_gold"),
                        prestige=item.get("add_prestige"),
                        piety=item.get("add_piety"),
                        dna_data=dna.get(item.get("dna")),
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
                    character.traits.set([get_object(Trait, trait) for trait in sorted(traits)])
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
        count, start_date = 0, datetime.datetime.now()
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("history/characters/"):
                continue
            for key, item in subdata.items():
                if isinstance(item, list) and all(isinstance(i, dict) for i in item):
                    item = {k: v for d in item for k, v in d.items()}
                if not isinstance(item, dict):
                    continue
                character = get_object(Character, key)
                if character.wip:
                    continue
                for date, subitem in item.items():
                    if date := regex_date.fullmatch(date) and convert_date(date, key):
                        if isinstance(subitem, list):
                            pdx_date = to_pdx_date(date)
                            logger.warning(f'Duplicated character history "{key}" for "{pdx_date}"')
                            all_duplicates.setdefault(CharacterHistory._meta.object_name, []).append((key, pdx_date))
                            subitem = {k: v for i in subitem for k, v in i.items() if isinstance(i, dict)}
                        if not subitem:
                            continue
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
                                diplomacy=subitem.get("diplomacy"),
                                martial=subitem.get("martial"),
                                stewardship=subitem.get("stewardship"),
                                intrigue=subitem.get("intrigue"),
                                learning=subitem.get("learning"),
                                prowess=subitem.get("prowess"),
                                gold=subitem.get("add_gold") or effect.get("add_gold"),
                                prestige=subitem.get("add_prestige") or effect.get("add_prestige"),
                                piety=subitem.get("add_piety") or effect.get("add_piety"),
                                raw_data=subitem,
                            ),
                        )
                        keep_object(CharacterHistory, history)
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
                                    [
                                        get_object(Character, target)
                                        for scope, target in sorted(values)
                                        if scope == "character"
                                    ]
                                )
                        if traits := subitem.get("trait"):
                            traits = traits if isinstance(traits, list) else [traits]
                            history.traits_added.set([get_object(Trait, trait) for trait in sorted(traits)])
                        if traits := subitem.get("remove_trait"):
                            traits = traits if isinstance(traits, list) else [traits]
                            history.traits_removed.set([get_object(Trait, trait) for trait in sorted(traits)])
                if character.modified:
                    character.save()
        mark_as_done(CharacterHistory, count, start_date)

        # Law
        count, start_date = 0, datetime.datetime.now()
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("common/laws/"):
                continue
            for group_key, group in subdata.items():
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

        # Title history
        count, start_date = 0, datetime.datetime.now()
        for file, subdata in all_data.items():
            if not subdata or not file.startswith("history/titles/"):
                continue
            for key, item in subdata.items():
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
                        if isinstance(subitem, list):
                            pdx_date = to_pdx_date(date)
                            logger.warning(f'Duplicated title history "{key}" for "{pdx_date}"')
                            all_duplicates.setdefault(TitleHistory._meta.object_name, []).append((key, pdx_date))
                            subitem = {k: v for i in subitem for k, v in i.items() if isinstance(i, dict)}
                        if not subitem:
                            continue
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
                                development_level=subitem.get("change_development_level"),
                                raw_data=subitem,
                            ),
                        )
                        keep_object(TitleHistory, history)
                        count += 1
                        history.created = created
                        if succession_laws := subitem.get("succession_laws"):
                            succession_laws = (
                                succession_laws if isinstance(succession_laws, list) else [succession_laws]
                            )
                            history.succession_laws.set([get_object(Law, law) for law in sorted(succession_laws)])
        mark_as_done(TitleHistory, count, start_date)

        # Mass cleaning
        all_deleted = collections.Counter()
        if purge:
            for model, keys in all_objects.items():
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
