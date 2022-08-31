import logging

from common.fields import JsonField
from common.models import CommonModel, Entity, EntityQuerySet
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.db.models.utils import resolve_callables

from database.ckparser import parse_text

logger = logging.getLogger(__name__)


def to_pdx_date(date):
    year, month, day = date.year, date.month, date.day
    return f"{year}.{month}.{day}"


class User(AbstractUser, Entity):
    can_use_api = models.BooleanField(default=False)

    _ignore_log = ("date_joined", "last_login", "password")


class BaseModelQuerySet(EntityQuerySet):
    def import_update_or_create(self, defaults=None, **kwargs):
        defaults = defaults or {}
        self._for_write = True
        with transaction.atomic(using=self.db):
            obj, created = self.select_for_update().get_or_create(defaults, **kwargs)
            if created:
                return obj, created
            if not getattr(obj, "wip", False):
                for k, v in resolve_callables(defaults):
                    setattr(obj, k, v)
                obj.save(using=self.db)
            else:
                logger.info(f"Ignored {obj._meta.verbose_name} ({obj.keys}) due to work in progress")
        return obj, False


class BaseModel(Entity):
    id = models.CharField(max_length=64, primary_key=True, editable=True)
    name = models.CharField(max_length=128, blank=True)
    description = models.TextField(blank=True)
    raw_data = JsonField(blank=True, null=True)
    exists = models.BooleanField(default=True)
    wip = models.BooleanField(default=False)
    objects = BaseModelQuerySet.as_manager()

    _ignore_log = ("raw_data",)

    class Meta:
        abstract = True

    @property
    def keys(self):
        return self.id

    def __str__(self):
        return str(self.name or self.id)


class BaseCharacter(CommonModel):
    dynasty = models.ForeignKey(
        "Dynasty",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="%(class)ss",
    )
    house = models.ForeignKey(
        "House",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="%(class)ss",
    )
    nickname = models.ForeignKey(
        "Nickname",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="%(class)ss",
    )
    culture = models.ForeignKey(
        "Culture",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="%(class)ss",
    )
    religion = models.ForeignKey(
        "Religion",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="%(class)ss",
    )
    diplomacy = models.SmallIntegerField(blank=True, null=True)
    martial = models.SmallIntegerField(blank=True, null=True)
    stewardship = models.SmallIntegerField(blank=True, null=True)
    intrigue = models.SmallIntegerField(blank=True, null=True)
    learning = models.SmallIntegerField(blank=True, null=True)
    prowess = models.SmallIntegerField(blank=True, null=True)
    gold = models.SmallIntegerField(blank=True, null=True)
    prestige = models.SmallIntegerField(blank=True, null=True)
    piety = models.SmallIntegerField(blank=True, null=True)

    class Meta:
        abstract = True


class Character(BaseModel, BaseCharacter):
    gender = models.CharField(
        max_length=1,
        default="M",
        choices=(
            ("M", "Male"),
            ("F", "Female"),
        ),
    )
    sexuality = models.CharField(
        max_length=16,
        blank=True,
        default="heterosexual",
        choices=(
            ("heterosexual", "Heterosexual"),
            ("homosexual", "Homosexual"),
            ("bisexual", "Bisexual"),
            ("asexual", "Asexual"),
        ),
    )
    birth_date = models.DateField(blank=True, null=True)
    death_date = models.DateField(blank=True, null=True)
    death_reason = models.ForeignKey(
        "DeathReason",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="characters",
    )
    killer = models.ForeignKey(
        "self",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="kills",
    )
    mother = models.ForeignKey(
        "self",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="mother_children",
        related_query_name="children",
    )
    father = models.ForeignKey(
        "self",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="father_children",
        related_query_name="children",
    )
    traits = models.ManyToManyField(
        "Trait",
        blank=True,
        related_name="characters",
    )
    random_traits = models.BooleanField(default=True)
    dna_text = models.TextField(blank=True)
    dna_data = JsonField(blank=True, null=True, editable=False)

    _ignore_log = (
        "raw_data",
        "dna_data",
    )

    def clean_fields(self, exclude=None):
        if not exclude or "dna_text" not in exclude:
            try:
                self.dna_data = parse_text(self.dna_text)
            except:  # noqa
                raise ValidationError({"dna_text": "Syntax error"})
        return super().clean_fields(exclude)

    def revert_data(self):
        data = dict(
            name=self.name,
            female=True if self.gender == "F" else False,
            sexuality=self.sexuality,
            father=self.father_id,
            mother=self.mother_id,
            dynasty=self.dynasty_id,
            dynasty_house=self.house_id,
            diplomacy=self.diplomacy,
            martial=self.martial,
            stewardship=self.stewardship,
            intrigue=self.intrigue,
            learning=self.learning,
            prowess=self.prowess,
            religion=self.religion_id,
            culture=self.culture_id,
            give_nickname=self.nickname_id,
            trait=list(self.traits.order_by("id").values_list("id", flat=True)),
            disallow_random_traits=not self.random_traits,
        )
        for key, value in (self.raw_data or {}).items():
            if key in data:
                continue
            data[key] = value
        if self.birth_date:
            data[to_pdx_date(self.birth_date)] = {"birth": True}
        for history in self.history.all().order_by("date"):
            subdata = {}
            if history.event == "birth" and self.birth_date == history.date:
                subdata.update(birth=True)
            elif history.event == "death" and self.death_date == history.date:
                if self.death_reason_id or self.killer_id:
                    subdata.update(
                        death=dict(
                            death_reason=self.death_reason_id,
                            killer=self.killer_id,
                        )
                    )
                else:
                    subdata.update(death=True)
            effect = {}
            subdata.update(
                dynasty=history.dynasty_id,
                dynasty_house=history.house_id,
                give_nickname=history.nickname_id,
                culture=history.culture_id,
                religion=history.religion_id,
                diplomacy=history.diplomacy,
                martial=history.martial,
                stewardship=history.stewardship,
                intrigue=history.intrigue,
                learning=history.learning,
                prowess=history.prowess,
                employer=0 if history.is_unemployed else history.employer_id,
                add_spouse=history.add_spouse_id,
                remove_spouse=history.remove_spouse_id,
                remove_trait=list(history.traits_removed.order_by("id").values_list("id", flat=True)),
                trait=list(history.traits_added.order_by("id").values_list("id", flat=True)),
                effect=effect,
            )
            raw_data = history.raw_data or {}
            raw_effect = raw_data.pop("effect", {})
            for key, value in raw_data.items():
                if key in subdata:
                    continue
                subdata[key] = value
            effect.update(
                add_gold=history.gold,
                add_prestige=history.prestige,
                add_piety=history.piety,
            )
            relations = (
                ("set_relation_soulmate", history.add_soulmate_id),
                ("remove_relation_soulmate", history.remove_soulmate_id),
                ("set_relation_best_friend", history.add_best_friend_id),
                ("remove_relation_best_friend", history.remove_best_friend_id),
                ("set_relation_nemesis", history.add_nemesis_id),
                ("remove_relation_nemesis", history.remove_nemesis_id),
                ("set_relation_guardian", history.add_guardian_id),
                ("remove_relation_guardian", history.remove_guardian_id),
            )
            for relation, field in relations:
                effect[relation] = f"character:{field}" if field else None
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
                effect[relation] = [f"character:{c}" for c in field.order_by("id").values_list("id", flat=True)]
            for key, value in raw_effect.items():
                if key in subdata:
                    continue
                effect[key] = value
            if not effect or not any(effect.values()):
                del subdata["effect"]
            data[to_pdx_date(history.date)] = subdata
        if self.death_date:
            subdata = data.setdefault(to_pdx_date(self.death_date), {})
            if not subdata.get("death"):
                if self.death_reason_id or self.killer_id:
                    subdata.update(
                        death=dict(
                            death_reason=self.death_reason_id,
                            killer=self.killer_id,
                        ),
                    )
                else:
                    subdata.update(death=True)
        return {self.id: data}


class CharacterHistory(Entity, BaseCharacter):
    character = models.ForeignKey(
        "Character",
        on_delete=models.CASCADE,
        related_name="history",
    )
    date = models.DateField()
    event = models.CharField(
        max_length=8,
        blank=True,
        choices=(
            ("birth", "Birth"),
            ("death", "Death"),
            ("other", "Other"),
        ),
    )
    is_unemployed = models.BooleanField(blank=True, null=True)
    employer = models.ForeignKey(
        "Character",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="employed",
    )
    add_spouse = models.ForeignKey(
        "Character",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="spouses_added",
    )
    remove_spouse = models.ForeignKey(
        "Character",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="spouses_removed",
    )
    add_lovers = models.ManyToManyField(
        "Character",
        blank=True,
        related_name="lover_added",
    )
    remove_lovers = models.ManyToManyField(
        "Character",
        blank=True,
        related_name="lover_removed",
    )
    add_soulmate = models.ForeignKey(
        "Character",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="soulmate_added",
    )
    remove_soulmate = models.ForeignKey(
        "Character",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="soulmate_removed",
    )
    add_potential_friends = models.ManyToManyField(
        "Character",
        blank=True,
        related_name="potential_friends_added",
    )
    remove_potential_friends = models.ManyToManyField(
        "Character",
        blank=True,
        related_name="potential_friends_removed",
    )
    add_friends = models.ManyToManyField(
        "Character",
        blank=True,
        related_name="friends_added",
    )
    remove_friends = models.ManyToManyField(
        "Character",
        blank=True,
        related_name="friends_removed",
    )
    add_best_friend = models.ForeignKey(
        "Character",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="best_friends_added",
    )
    remove_best_friend = models.ForeignKey(
        "Character",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="best_friends_removed",
    )
    add_potential_rivals = models.ManyToManyField(
        "Character",
        blank=True,
        related_name="potential_rivals_added",
    )
    remove_potential_rivals = models.ManyToManyField(
        "Character",
        blank=True,
        related_name="potential_rivals_removed",
    )
    add_rivals = models.ManyToManyField(
        "Character",
        blank=True,
        related_name="rivals_added",
    )
    remove_rivals = models.ManyToManyField(
        "Character",
        blank=True,
        related_name="rivals_removed",
    )
    add_nemesis = models.ForeignKey(
        "Character",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="nemesis_added",
    )
    remove_nemesis = models.ForeignKey(
        "Character",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="nemesis_removed",
    )
    add_guardian = models.ForeignKey(
        "Character",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="guardian_added",
    )
    remove_guardian = models.ForeignKey(
        "Character",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="guardian_removed",
    )
    traits_added = models.ManyToManyField(
        "Trait",
        blank=True,
        related_name="traits_added",
    )
    traits_removed = models.ManyToManyField(
        "Trait",
        blank=True,
        related_name="traits_removed",
    )
    raw_data = JsonField(blank=True, null=True)

    _ignore_log = ("raw_data",)

    @property
    def keys(self):
        return self.character_id, to_pdx_date(self.date)

    def __str__(self):
        return f"{self.character} - {to_pdx_date(self.date)}"

    class Meta:
        unique_together = ("character", "date")
        verbose_name_plural = "character histories"


class DeathReason(BaseModel):
    is_default = models.BooleanField(default=False)
    is_natural = models.BooleanField(default=False)
    is_public_knowledge = models.BooleanField(blank=True, null=True)


class Nickname(BaseModel):
    is_bad = models.BooleanField(default=False)
    is_prefix = models.BooleanField(default=False)


class Dynasty(BaseModel):
    prefix = models.CharField(max_length=16, blank=True)
    culture = models.ForeignKey(
        "Culture",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="dynasties",
    )
    coa_text = models.TextField(blank=True)
    coa_data = JsonField(blank=True, null=True, editable=False)

    _ignore_log = (
        "raw_data",
        "coa_data",
    )

    def clean_fields(self, exclude=None):
        if not exclude or "coa_text" not in exclude:
            try:
                self.coa_data = parse_text(self.coa_text)
            except:  # noqa
                raise ValidationError({"coa_text": "Syntax error"})
        return super().clean_fields(exclude)

    def __str__(self):
        if self.prefix and self.name:
            return f"{self.prefix}{self.name}"
        return self.name or self.id

    class Meta:
        verbose_name_plural = "dynasties"


class House(BaseModel):
    prefix = models.CharField(max_length=16, blank=True)
    dynasty = models.ForeignKey(
        "Dynasty",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="houses",
    )
    coa_text = models.TextField(blank=True)
    coa_data = JsonField(blank=True, null=True, editable=False)

    _ignore_log = (
        "raw_data",
        "coa_data",
    )

    def clean_fields(self, exclude=None):
        if not exclude or "coa_text" not in exclude:
            try:
                self.coa_data = parse_text(self.coa_text)
            except:  # noqa
                raise ValidationError({"coa_text": "Syntax error"})
        return super().clean_fields(exclude)

    def __str__(self):
        if self.prefix and self.name:
            return f"{self.prefix}{self.name}"
        return self.name or self.id


class Culture(BaseModel):
    ethos = models.ForeignKey(
        "Ethos",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="cultures",
    )
    heritage = models.ForeignKey(
        "Heritage",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="cultures",
    )
    language = models.ForeignKey(
        "Language",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="cultures",
    )
    martial_custom = models.ForeignKey(
        "MartialCustom",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="cultures",
    )
    name_list = models.ForeignKey(
        "NameList",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="cultures",
    )
    traditions = models.ManyToManyField(
        "Tradition",
        blank=True,
        related_name="cultures",
    )


class Ethnicity(BaseModel):
    class Meta:
        verbose_name_plural = "ethnicities"


class CultureEthnicity(Entity):
    culture = models.ForeignKey(
        "Culture",
        on_delete=models.CASCADE,
        related_name="ethnicities",
    )
    ethnicity = models.ForeignKey(
        "Ethnicity",
        on_delete=models.CASCADE,
        related_name="cultures",
    )
    chance = models.PositiveSmallIntegerField(blank=True, null=True)

    @property
    def keys(self):
        return self.culture_id, self.ethnicity_id

    def __str__(self):
        return f"{self.culture} - {self.ethnicity}"

    class Meta:
        unique_together = ("culture", "ethnicity")
        verbose_name_plural = "culture ethnicities"


class Ethos(BaseModel):
    class Meta:
        verbose_name_plural = "ethos"


class Heritage(BaseModel):
    pass


class Language(BaseModel):
    pass


class MartialCustom(BaseModel):
    pass


class NameList(BaseModel):
    pass


class Tradition(BaseModel):
    category = models.CharField(
        max_length=8,
        blank=True,
        choices=(
            ("combat", "Combat"),
            ("law", "Law"),
            ("realm", "Realm"),
            ("regional", "Regional"),
            ("ritual", "Ritual"),
            ("societal", "Societal"),
        ),
    )


class Era(BaseModel):
    year = models.PositiveSmallIntegerField(blank=True, null=True)


class Innovation(BaseModel):
    group = models.CharField(
        max_length=32,
        blank=True,
        choices=(
            ("culture_group_civic", "Civic"),
            ("culture_group_regional", "Cultural and Regional"),
            ("culture_group_military", "Military"),
        ),
    )
    era = models.ForeignKey(
        "Era",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="innovations",
    )


class CultureOrHeritageHistory(Entity):
    date = models.DateField()
    join_era = models.ForeignKey(
        "Era",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="%(class)s_joined",
    )
    discover_innovations = models.ManyToManyField(
        "Innovation",
        blank=True,
        related_name="%(class)s_discovered",
    )
    raw_data = JsonField(blank=True, null=True)

    _ignore_log = ("raw_data",)

    class Meta:
        abstract = True


class HeritageHistory(CultureOrHeritageHistory):
    heritage = models.ForeignKey(
        "Heritage",
        on_delete=models.CASCADE,
        related_name="history",
    )

    @property
    def keys(self):
        return self.heritage_id, to_pdx_date(self.date)

    def __str__(self):
        return f"{self.heritage} - {to_pdx_date(self.date)}"

    class Meta:
        unique_together = ("heritage", "date")
        verbose_name_plural = "heritage histories"


class CultureHistory(CultureOrHeritageHistory):
    culture = models.ForeignKey(
        "Culture",
        on_delete=models.CASCADE,
        related_name="history",
    )

    @property
    def keys(self):
        return self.culture_id, to_pdx_date(self.date)

    def __str__(self):
        return f"{self.culture} - {to_pdx_date(self.date)}"

    class Meta:
        unique_together = ("culture", "date")
        verbose_name_plural = "culture histories"


class Religion(BaseModel):
    group = models.CharField(max_length=32, blank=True)
    color = models.CharField(max_length=16, blank=True)
    religious_head = models.ForeignKey(
        "Title",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="religions",
    )
    holy_sites = models.ManyToManyField(
        "HolySite",
        blank=True,
        related_name="religions",
    )
    doctrines = models.ManyToManyField(
        "Doctrine",
        blank=True,
        related_name="religions",
    )
    men_at_arms = models.ManyToManyField(
        "MenAtArms",
        blank=True,
        related_name="religions",
    )


class ReligionTrait(Entity):
    religion = models.ForeignKey(
        "Religion",
        on_delete=models.CASCADE,
        related_name="traits",
    )
    trait = models.ForeignKey(
        "Trait",
        on_delete=models.CASCADE,
        related_name="religions",
    )
    is_virtue = models.BooleanField(default=False)
    piety = models.SmallIntegerField(blank=True, null=True)

    @property
    def keys(self):
        return self.religion_id, self.trait_id

    def __str__(self):
        return f"{self.religion} - {self.trait}"

    class Meta:
        unique_together = ("religion", "trait")


class HolySite(BaseModel):
    county = models.ForeignKey(
        "Title",
        blank=True,
        null=True,
        limit_choices_to={"tier": "county"},
        on_delete=models.SET_NULL,
        related_name="county_holy_sites",
        related_query_name="holy_sites",
    )
    barony = models.ForeignKey(
        "Title",
        blank=True,
        null=True,
        limit_choices_to={"tier": "barony"},
        on_delete=models.SET_NULL,
        related_name="barony_holy_sites",
        related_query_name="holy_sites",
    )


class Doctrine(BaseModel):
    group = models.CharField(max_length=32, blank=True)
    multiple = models.SmallIntegerField(blank=True, null=True)


class DoctrineTrait(Entity):
    doctrine = models.ForeignKey(
        "Doctrine",
        on_delete=models.CASCADE,
        related_name="traits",
    )
    trait = models.ForeignKey(
        "Trait",
        on_delete=models.CASCADE,
        related_name="doctrines",
    )
    is_virtue = models.BooleanField(default=False)
    piety = models.SmallIntegerField(blank=True, null=True)

    @property
    def keys(self):
        return self.doctrine_id, self.trait_id

    def __str__(self):
        return f"{self.doctrine} - {self.trait}"

    class Meta:
        unique_together = ("doctrine", "trait")


class Trait(BaseModel):
    group = models.ForeignKey(
        "self",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="traits",
    )
    is_group = models.BooleanField(default=False)
    is_good = models.BooleanField(blank=True, null=True)
    is_genetic = models.BooleanField(blank=True, null=True)
    is_physical = models.BooleanField(blank=True, null=True)
    is_health = models.BooleanField(blank=True, null=True)
    is_fame = models.BooleanField(blank=True, null=True)
    is_incapacitating = models.BooleanField(blank=True, null=True)
    is_immortal = models.BooleanField(blank=True, null=True)
    can_inbred = models.BooleanField(blank=True, null=True)
    can_have_children = models.BooleanField(blank=True, null=True)
    can_inherit = models.BooleanField(blank=True, null=True)
    can_not_marry = models.BooleanField(blank=True, null=True)
    can_be_taken = models.BooleanField(blank=True, null=True)
    cost = models.SmallIntegerField(blank=True, null=True)
    inherit_chance = models.SmallIntegerField(blank=True, null=True)
    diplomacy = models.SmallIntegerField(blank=True, null=True)
    martial = models.SmallIntegerField(blank=True, null=True)
    stewardship = models.SmallIntegerField(blank=True, null=True)
    intrigue = models.SmallIntegerField(blank=True, null=True)
    learning = models.SmallIntegerField(blank=True, null=True)
    prowess = models.SmallIntegerField(blank=True, null=True)
    health = models.FloatField(blank=True, null=True)
    fertility = models.FloatField(blank=True, null=True)
    monthly_prestige = models.FloatField(blank=True, null=True)
    monthly_prestige_mult = models.FloatField(blank=True, null=True)
    monthly_piety = models.FloatField(blank=True, null=True)
    monthly_piety_mult = models.FloatField(blank=True, null=True)
    same_opinion = models.SmallIntegerField(blank=True, null=True)
    opposite_opinion = models.SmallIntegerField(blank=True, null=True)
    general_opinion = models.SmallIntegerField(blank=True, null=True)
    attraction_opinion = models.SmallIntegerField(blank=True, null=True)
    vassal_opinion = models.SmallIntegerField(blank=True, null=True)
    clergy_opinion = models.SmallIntegerField(blank=True, null=True)
    same_faith_opinion = models.SmallIntegerField(blank=True, null=True)
    dynasty_opinion = models.SmallIntegerField(blank=True, null=True)
    house_opinion = models.SmallIntegerField(blank=True, null=True)
    level = models.PositiveSmallIntegerField(blank=True, null=True)
    opposites = models.ManyToManyField(
        "self",
        blank=True,
    )


class Law(BaseModel):
    group = models.CharField(
        max_length=32,
        blank=True,
        choices=(
            ("realm_law", "Realm law"),
            ("succession_faith", "Succession faith law"),
            ("succession_order_laws", "Succession order law"),
            ("succession_gender_laws", "Succession gender law"),
            ("title_succession_laws", "Title succession law"),
        ),
    )


class Title(BaseModel):
    tier = models.CharField(
        max_length=8,
        blank=True,
        choices=(
            ("barony", "Barony"),
            ("county", "County"),
            ("duchy", "Duchy"),
            ("kingdom", "Kingdom"),
            ("empire", "Empire"),
        ),
    )
    prefix = models.CharField(max_length=16, blank=True)
    color1 = models.CharField(max_length=8, blank=True)
    color2 = models.CharField(max_length=8, blank=True)
    de_jure_liege = models.ForeignKey(
        "self",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="de_jure_vassals",
    )
    capital = models.ForeignKey(
        "self",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    province = models.OneToOneField(
        "Province",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="title",
    )

    def __str__(self):
        if self.prefix and self.name:
            return f"{self.prefix}{self.name}"
        return self.name or self.id


class TitleHistory(Entity):
    title = models.ForeignKey(
        "Title",
        on_delete=models.CASCADE,
        related_name="history",
    )
    date = models.DateField()
    de_jure_liege = models.ForeignKey(
        "Title",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="de_jure_liege_history",
    )
    liege = models.ForeignKey(
        "Title",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="liege_history",
    )
    holder = models.ForeignKey(
        "Character",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="holder_history",
    )
    is_independent = models.BooleanField(blank=True, null=True)
    is_destroyed = models.BooleanField(blank=True, null=True)
    development_level = models.SmallIntegerField(blank=True, null=True)
    succession_laws = models.ManyToManyField(
        "Law",
        blank=True,
        limit_choices_to=Q(group__icontains="succession"),
        related_name="title_history",
    )
    raw_data = JsonField(blank=True, null=True)

    _ignore_log = ("raw_data",)

    @property
    def keys(self):
        return self.title_id, to_pdx_date(self.date)

    def __str__(self):
        return f"{self.title} - {to_pdx_date(self.date)}"

    class Meta:
        unique_together = ("title", "date")
        verbose_name_plural = "title histories"


class Terrain(BaseModel):
    color = models.CharField(max_length=16, blank=True)
    movement_speed = models.FloatField(blank=True, null=True)
    combat_width = models.FloatField(blank=True, null=True)
    audio_parameter = models.FloatField(blank=True, null=True)
    supply_limit = models.FloatField(blank=True, null=True)
    development_growth = models.FloatField(blank=True, null=True)
    attacker_hard_casualty = models.FloatField(blank=True, null=True)
    attacker_retreat_losses = models.FloatField(blank=True, null=True)
    defender_hard_casualty = models.FloatField(blank=True, null=True)
    defender_retreat_losses = models.FloatField(blank=True, null=True)
    defender_advantage = models.SmallIntegerField(blank=True, null=True)


class Province(BaseModel):
    id = models.PositiveIntegerField(primary_key=True)
    culture = models.ForeignKey(
        "Culture",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="provinces",
    )
    religion = models.ForeignKey(
        "Religion",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="provinces",
    )
    holding = models.ForeignKey(
        "Holding",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="provinces",
    )
    terrain = models.ForeignKey(
        "Terrain",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="provinces",
    )
    special_building_slot = models.ForeignKey(
        "Building",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="province_slots",
    )
    special_building = models.ForeignKey(
        "Building",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="provinces",
    )
    winter_severity_bias = models.FloatField(blank=True, null=True)


class ProvinceHistory(Entity):
    province = models.ForeignKey(
        "Province",
        on_delete=models.CASCADE,
        related_name="history",
    )
    date = models.DateField()
    culture = models.ForeignKey(
        "Culture",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="province_history",
    )
    religion = models.ForeignKey(
        "Religion",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="province_history",
    )
    holding = models.ForeignKey(
        "Holding",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="province_history",
    )
    buildings = models.ManyToManyField(
        "Building",
        blank=True,
        related_name="province_history",
    )
    raw_data = JsonField(blank=True, null=True)

    _ignore_log = ("raw_data",)

    @property
    def keys(self):
        return self.province_id, to_pdx_date(self.date)

    def __str__(self):
        return f"{self.province} - {to_pdx_date(self.date)}"

    class Meta:
        unique_together = ("province", "date")
        verbose_name_plural = "province histories"


class Holding(BaseModel):
    primary_building = models.OneToOneField(
        "Building",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="primary_holding",
    )
    buildings = models.ManyToManyField(
        "Building",
        blank=True,
        related_name="holdings",
    )


class Building(BaseModel):
    type = models.CharField(
        max_length=16,
        blank=True,
        choices=(
            ("duchy_capital", "Duchy"),
            ("special", "Special"),
        ),
    )
    next_building = models.OneToOneField(
        "self",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="previous_building",
    )
    construction_time = models.PositiveIntegerField(blank=True, null=True)
    cost_gold = models.PositiveIntegerField(blank=True, null=True)
    cost_prestige = models.PositiveIntegerField(blank=True, null=True)
    levy = models.PositiveIntegerField(blank=True, null=True)
    max_garrison = models.PositiveIntegerField(blank=True, null=True)
    garrison_reinforcement_factor = models.FloatField(blank=True, null=True)


MEN_AT_ARMS_TYPES = (
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
)


class MenAtArms(BaseModel):
    type = models.CharField(max_length=16, blank=True, choices=MEN_AT_ARMS_TYPES)
    buy_cost = models.FloatField(blank=True, null=True)
    low_maintenance_cost = models.FloatField(blank=True, null=True)
    high_maintenance_cost = models.FloatField(blank=True, null=True)
    stack = models.PositiveSmallIntegerField(blank=True, null=True)
    damage = models.PositiveSmallIntegerField(blank=True, null=True)
    toughness = models.PositiveSmallIntegerField(blank=True, null=True)
    pursuit = models.PositiveSmallIntegerField(blank=True, null=True)
    screen = models.PositiveSmallIntegerField(blank=True, null=True)
    siege_tier = models.PositiveSmallIntegerField(blank=True, null=True)
    siege_value = models.FloatField(blank=True, null=True)

    class Meta:
        verbose_name = "men-at-arms"
        verbose_name_plural = "men-at-arms"


class TerrainModifier(Entity):
    men_at_arms = models.ForeignKey(
        "MenAtArms",
        on_delete=models.CASCADE,
        related_name="modifiers",
    )
    terrain = models.ForeignKey(
        "Terrain",
        on_delete=models.CASCADE,
        related_name="modifiers",
    )
    damage = models.SmallIntegerField(blank=True, null=True)
    toughness = models.SmallIntegerField(blank=True, null=True)
    pursuit = models.SmallIntegerField(blank=True, null=True)
    screen = models.SmallIntegerField(blank=True, null=True)

    @property
    def keys(self):
        return self.men_at_arms_id, self.terrain_id

    def __str__(self):
        return f"{self.men_at_arms} - {self.terrain}"

    class Meta:
        unique_together = ("men_at_arms", "terrain")


class Counter(Entity):
    men_at_arms = models.ForeignKey(
        "MenAtArms",
        on_delete=models.CASCADE,
        related_name="counters",
    )
    type = models.CharField(max_length=16, blank=True, choices=MEN_AT_ARMS_TYPES)
    factor = models.FloatField(default=1.0)

    @property
    def keys(self):
        return self.men_at_arms_id, self.type

    def __str__(self):
        return f"{self.men_at_arms} - {self.get_type_display()}"

    class Meta:
        unique_together = ("men_at_arms", "type")


class Localization(Entity):
    key = models.CharField(max_length=128)
    language = models.CharField(
        max_length=2,
        default="en",
        choices=(
            ("en", "English"),
            ("fr", "French"),
            ("de", "German"),
            ("sp", "Spanish"),
            ("ko", "Korean"),
            ("ru", "Russian"),
            ("zh", "Chinese"),
        ),
    )
    text = models.TextField(blank=True)
    wip = models.BooleanField(default=False)
    objects = BaseModelQuerySet.as_manager()

    def __str__(self):
        return f"{self.key} ({self.get_language_display()}"

    class Meta:
        unique_together = ("key", "language")


MODELS = (
    Character,
    CharacterHistory,
    DeathReason,
    Nickname,
    Dynasty,
    House,
    Culture,
    CultureHistory,
    Ethnicity,
    CultureEthnicity,
    Ethos,
    Heritage,
    HeritageHistory,
    Language,
    MartialCustom,
    NameList,
    Tradition,
    Era,
    Innovation,
    Religion,
    ReligionTrait,
    HolySite,
    Doctrine,
    DoctrineTrait,
    Trait,
    Law,
    Title,
    TitleHistory,
    Terrain,
    Province,
    ProvinceHistory,
    Holding,
    Building,
    MenAtArms,
    TerrainModifier,
    Counter,
    Localization,
)
M2M_MODELS = [getattr(model, field.name).through for model in MODELS for field in model._meta.many_to_many]

__all__ = ["User", *(model.__name__ for model in MODELS)]
