from common.admin import EntityAdmin, EntityStackedInline, EntityTabularInline
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.http import HttpResponse
from django.urls import reverse
from django.utils.safestring import mark_safe

from database.ckparser import revert
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
    User,
    War,
)

admin.site.site_header = "Crusader Kings Database"


@admin.register(User)
class UserAdmin(BaseUserAdmin, EntityAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "Custom",
            dict(
                fields=("can_use_api",),
                classes=(),
            ),
        ),
    )
    list_display = BaseUserAdmin.list_display + ("can_use_api",)
    list_display_links = ("username",)
    list_filter = BaseUserAdmin.list_filter + ("can_use_api",)
    filter_horizontal = ("groups", "user_permissions")

    def metadata_url(self, obj):
        if obj.metadata:
            url = reverse("admin:common_usermetadata_change", args=(obj.pk,))
            return mark_safe(f'<a href="{url}">{len(obj.metadata.data)}</a>')


class BaseAdmin(EntityAdmin):
    fieldsets = (
        (
            "General",
            {
                "fields": (
                    "id",
                    "name",
                    "description",
                ),
                "classes": (),
            },
        ),
        (
            "Internal",
            {
                "fields": (
                    "raw_data",
                    "exists",
                    "wip",
                ),
                "classes": ("collapse",),
            },
        ),
    )
    list_display = (
        "name",
        "exists",
        "wip",
    )
    list_filter = (
        "exists",
        "wip",
        "current_user",
    )
    ordering = ("id",)
    search_fields = (
        "id",
        "name",
        "description",
    )
    save_on_top = True
    actions_on_bottom = True

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ("id",)
        return self.readonly_fields


@admin.register(Ethos)
class EthosAdmin(BaseAdmin):
    pass


class HeritageHistoryInlineAdmin(EntityTabularInline):
    model = HeritageHistory
    extra = 0
    show_change_link = True
    ordering = (
        "heritage",
        "date",
    )
    autocomplete_fields = (
        "join_era",
        "discover_innovations",
    )
    exclude = ("raw_data",)

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("heritage", "join_era")
            .prefetch_related("discover_innovations")
        )


@admin.register(Heritage)
class HeritageAdmin(BaseAdmin):
    inlines = (HeritageHistoryInlineAdmin,)


@admin.register(HeritageHistory)
class HeritageHistoryAdmin(BaseAdmin):
    fieldsets = (
        (
            "General",
            {
                "fields": (
                    "heritage",
                    "date",
                ),
                "classes": (),
            },
        ),
        (
            "Changes",
            {
                "fields": (
                    "join_era",
                    "discover_innovations",
                ),
                "classes": (),
            },
        ),
        (
            "Internal",
            {
                "fields": ("raw_data",),
                "classes": ("collapse",),
            },
        ),
    )
    list_display = (
        "heritage_link",
        "date",
        "join_era_link",
    )
    list_filter = (
        "date",
        "current_user",
    )
    search_fields = (
        "heritage__id",
        "heritage__name",
        "join_era__id",
        "join_era__name",
    )
    ordering = (
        "heritage",
        "date",
    )
    autocomplete_fields = (
        "heritage",
        "join_era",
        "discover_innovations",
    )
    readonly_fields = ("heritage",)

    @admin.display(description="heritage", ordering="heritage__name")
    def heritage_link(self, obj):
        if obj.heritage:
            url = reverse("admin:database_heritage_change", args=(obj.heritage.pk,))
            return mark_safe(f'<a href="{url}">{obj.heritage}</a>')

    @admin.display(description="join_era", ordering="join_era__name")
    def join_era_link(self, obj):
        if obj.join_era:
            url = reverse("admin:database_era_change", args=(obj.join_era.pk,))
            return mark_safe(f'<a href="{url}">{obj.join_era}</a>')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("heritage", "join_era")


@admin.register(Language)
class LanguageAdmin(BaseAdmin):
    pass


@admin.register(MartialCustom)
class MartialCustomAdmin(BaseAdmin):
    pass


@admin.register(NameList)
class NameListAdmin(BaseAdmin):
    pass


@admin.register(Tradition)
class TraditionAdmin(BaseAdmin):
    fieldsets = (
        (
            "General",
            {
                "fields": (
                    "id",
                    "name",
                    "description",
                    "category",
                ),
                "classes": (),
            },
        ),
        (
            "Internal",
            {
                "fields": (
                    "raw_data",
                    "exists",
                    "wip",
                ),
                "classes": ("collapse",),
            },
        ),
    )
    list_display = (
        "name",
        "category",
        "exists",
        "wip",
    )
    search_fields = (
        "id",
        "name",
        "description",
        "category",
    )


@admin.register(Ethnicity)
class EthnicityAdmin(BaseAdmin):
    pass


@admin.register(Era)
class EraAdmin(BaseAdmin):
    fieldsets = (
        (
            "General",
            {
                "fields": (
                    "id",
                    "name",
                    "description",
                    "year",
                ),
                "classes": (),
            },
        ),
        (
            "Internal",
            {
                "fields": (
                    "raw_data",
                    "exists",
                    "wip",
                ),
                "classes": ("collapse",),
            },
        ),
    )
    list_display = (
        "name",
        "year",
        "exists",
        "wip",
    )


@admin.register(Innovation)
class InnovationAdmin(BaseAdmin):
    fieldsets = (
        (
            "General",
            {
                "fields": (
                    "id",
                    "name",
                    "description",
                    "group",
                    "era",
                ),
                "classes": (),
            },
        ),
        (
            "Unlocks",
            {
                "fields": (
                    "unlock_laws",
                    "unlock_men_at_arms",
                    "unlock_buildings",
                    "unlock_casus_belli",
                ),
                "classes": (),
            },
        ),
        (
            "Internal",
            {
                "fields": (
                    "raw_data",
                    "exists",
                    "wip",
                ),
                "classes": ("collapse",),
            },
        ),
    )
    list_display = (
        "name",
        "group",
        "era_link",
        "exists",
        "wip",
    )
    list_filter = (
        "exists",
        "wip",
        "group",
        "current_user",
    )
    search_fields = (
        "id",
        "name",
        "description",
        "group",
    )

    @admin.display(description="era", ordering="era__name")
    def era_link(self, obj):
        if obj.era:
            url = reverse("admin:database_era_change", args=(obj.era.pk,))
            return mark_safe(f'<a href="{url}">{obj.era}</a>')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("era")


class CultureEthnicityInlineAdmin(EntityTabularInline):
    model = CultureEthnicity
    extra = 0
    show_change_link = True
    ordering = (
        "culture",
        "ethnicity",
    )
    autocomplete_fields = ("ethnicity",)
    exclude = ("raw_data",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("culture", "ethnicity")


class CultureHistoryInlineAdmin(EntityTabularInline):
    model = CultureHistory
    extra = 0
    show_change_link = True
    ordering = (
        "culture",
        "date",
    )
    autocomplete_fields = (
        "join_era",
        "discover_innovations",
    )
    exclude = ("raw_data",)

    def get_queryset(self, request):
        return (
            super().get_queryset(request).select_related("culture", "join_era").prefetch_related("discover_innovations")
        )


@admin.register(Culture)
class CultureAdmin(BaseAdmin):
    fieldsets = (
        (
            "General",
            {
                "fields": (
                    "id",
                    "name",
                    "description",
                ),
                "classes": (),
            },
        ),
        (
            "Specific",
            {
                "fields": (
                    "ethos",
                    "heritage",
                    "language",
                    "martial_custom",
                    "name_list",
                    "traditions",
                ),
                "classes": (),
            },
        ),
        (
            "Internal",
            {
                "fields": (
                    "raw_data",
                    "exists",
                    "wip",
                ),
                "classes": ("collapse",),
            },
        ),
    )
    list_display = (
        "name",
        "ethos_link",
        "heritage_link",
        "language_link",
        "martial_custom_link",
        "exists",
        "wip",
    )
    search_fields = (
        "id",
        "name",
        "description",
        "ethos__id",
        "ethos__name",
        "heritage__id",
        "heritage__name",
        "language__id",
        "language__name",
        "martial_custom__id",
        "martial_custom__name",
    )
    autocomplete_fields = (
        "ethos",
        "heritage",
        "language",
        "martial_custom",
        "name_list",
        "traditions",
    )
    inlines = (
        CultureEthnicityInlineAdmin,
        CultureHistoryInlineAdmin,
    )

    @admin.display(description="ethos", ordering="ethos__name")
    def ethos_link(self, obj):
        if obj.ethos:
            url = reverse("admin:database_ethos_change", args=(obj.ethos.pk,))
            return mark_safe(f'<a href="{url}">{obj.ethos}</a>')

    @admin.display(description="heritage", ordering="heritage__name")
    def heritage_link(self, obj):
        if obj.heritage:
            url = reverse("admin:database_heritage_change", args=(obj.heritage.pk,))
            return mark_safe(f'<a href="{url}">{obj.heritage}</a>')

    @admin.display(description="language", ordering="language__name")
    def language_link(self, obj):
        if obj.language:
            url = reverse("admin:database_language_change", args=(obj.language.pk,))
            return mark_safe(f'<a href="{url}">{obj.language}</a>')

    @admin.display(description="martial custom", ordering="martial_custom__name")
    def martial_custom_link(self, obj):
        if obj.martial_custom:
            url = reverse("admin:database_martialcustom_change", args=(obj.martial_custom.pk,))
            return mark_safe(f'<a href="{url}">{obj.martial_custom}</a>')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("ethos", "heritage", "language", "martial_custom")


@admin.register(CultureEthnicity)
class CultureEthnicityAdmin(EntityAdmin):
    list_display = (
        "culture_link",
        "ethnicity_link",
        "chance",
    )
    list_editable = ("chance",)
    search_fields = (
        "culture__id",
        "culture__name",
        "ethnicity__id",
        "ethnicity_name",
    )
    ordering = (
        "culture",
        "ethnicity",
    )
    autocomplete_fields = (
        "culture",
        "ethnicity",
    )

    @admin.display(description="culture", ordering="culture__name")
    def culture_link(self, obj):
        if obj.culture:
            url = reverse("admin:database_culture_change", args=(obj.culture.pk,))
            return mark_safe(f'<a href="{url}">{obj.culture}</a>')

    @admin.display(description="ethnicity", ordering="ethnicity__name")
    def ethnicity_link(self, obj):
        if obj.ethnicity:
            url = reverse("admin:database_ethnicity_change", args=(obj.ethnicity.pk,))
            return mark_safe(f'<a href="{url}">{obj.ethnicity}</a>')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("culture", "ethnicity")


@admin.register(CultureHistory)
class CultureHistoryAdmin(BaseAdmin):
    fieldsets = (
        (
            "General",
            {
                "fields": (
                    "culture",
                    "date",
                ),
                "classes": (),
            },
        ),
        (
            "Changes",
            {
                "fields": (
                    "join_era",
                    "discover_innovations",
                ),
                "classes": (),
            },
        ),
        (
            "Internal",
            {
                "fields": ("raw_data",),
                "classes": ("collapse",),
            },
        ),
    )
    list_display = (
        "culture_link",
        "date",
        "join_era_link",
    )
    list_filter = (
        "date",
        "current_user",
    )
    search_fields = (
        "culture__id",
        "culture__name",
        "join_era__id",
        "join_era__name",
    )
    ordering = (
        "culture",
        "date",
    )
    autocomplete_fields = (
        "culture",
        "join_era",
        "discover_innovations",
    )
    readonly_fields = ("culture",)

    @admin.display(description="culture", ordering="culture__name")
    def culture_link(self, obj):
        if obj.culture:
            url = reverse("admin:database_culture_change", args=(obj.culture.pk,))
            return mark_safe(f'<a href="{url}">{obj.culture}</a>')

    @admin.display(description="join_era", ordering="join_era__name")
    def join_era_link(self, obj):
        if obj.join_era:
            url = reverse("admin:database_era_change", args=(obj.join_era.pk,))
            return mark_safe(f'<a href="{url}">{obj.join_era}</a>')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("culture", "join_era")


@admin.register(Trait)
class TraitAdmin(BaseAdmin):
    fieldsets = (
        (
            "General",
            {
                "fields": (
                    "id",
                    "name",
                    "description",
                    "can_be_taken",
                    "cost",
                    "level",
                    "minimum_age",
                    "maximum_age",
                    "group",
                    "category",
                    "opposites",
                ),
                "classes": (),
            },
        ),
        (
            "Flags",
            {
                "fields": (
                    "has_tracks",
                    "is_group",
                    "is_good",
                    "is_genetic",
                    "is_physical",
                    "is_health",
                    "is_fame",
                    "is_incapacitating",
                    "is_immortal",
                    "can_inbred",
                    "can_have_children",
                    "can_inherit",
                    "can_not_marry",
                    "inherit_chance",
                ),
                "classes": (),
            },
        ),
        (
            "Statistics",
            {
                "fields": (
                    "diplomacy",
                    "martial",
                    "stewardship",
                    "intrigue",
                    "learning",
                    "prowess",
                    "health",
                    "fertility",
                ),
                "classes": (),
            },
        ),
        (
            "Prestige and piety",
            {
                "fields": (
                    "monthly_prestige",
                    "monthly_prestige_mult",
                    "monthly_piety",
                    "monthly_piety_mult",
                ),
                "classes": (),
            },
        ),
        (
            "Opinion",
            {
                "fields": (
                    "same_opinion",
                    "opposite_opinion",
                    "general_opinion",
                    "attraction_opinion",
                    "vassal_opinion",
                    "liege_opinion",
                    "clergy_opinion",
                    "same_faith_opinion",
                    "same_culture_opinion",
                    "dynasty_opinion",
                    "house_opinion",
                ),
                "classes": (),
            },
        ),
        (
            "AI Personalities",
            {
                "fields": (
                    "ai_energy",
                    "ai_boldness",
                    "ai_compassion",
                    "ai_greed",
                    "ai_honor",
                    "ai_rationality",
                    "ai_sociability",
                    "ai_vengefulness",
                    "ai_zeal",
                ),
                "classes": (),
            },
        ),
        (
            "Internal",
            {
                "fields": (
                    "raw_data",
                    "exists",
                    "wip",
                ),
                "classes": ("collapse",),
            },
        ),
    )
    list_display = (
        "name",
        "group_link",
        "cost",
        "exists",
        "wip",
    )
    list_filter = (
        "exists",
        "wip",
        "category",
        "has_tracks",
        "is_group",
        "is_good",
        "is_genetic",
        "is_physical",
        "is_health",
        "is_fame",
        "is_incapacitating",
        "is_immortal",
        "can_inbred",
        "can_have_children",
        "can_inherit",
        "can_not_marry",
        "current_user",
    )
    search_fields = (
        "id",
        "name",
        "description",
        "group__id",
        "group__name",
        "category",
    )
    autocomplete_fields = (
        "group",
        "opposites",
    )

    @admin.display(description="group", ordering="group__name")
    def group_link(self, obj):
        if obj.group:
            url = reverse("admin:database_trait_change", args=(obj.group.pk,))
            return mark_safe(f'<a href="{url}">{obj.group}</a>')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("group")


@admin.register(Building)
class BuildingAdmin(BaseAdmin):
    fieldsets = (
        (
            "General",
            {
                "fields": (
                    "id",
                    "name",
                    "description",
                    "type",
                ),
                "classes": (),
            },
        ),
        (
            "Specific",
            {
                "fields": (
                    "next_building",
                    "construction_time",
                    "cost_gold",
                    "cost_prestige",
                    "levy",
                    "max_garrison",
                    "garrison_reinforcement_factor",
                ),
                "classes": (),
            },
        ),
        (
            "Internal",
            {
                "fields": (
                    "raw_data",
                    "exists",
                    "wip",
                ),
                "classes": ("collapse",),
            },
        ),
    )
    list_display = (
        "name",
        "type",
        "next_building_link",
        "construction_time",
        "cost_gold",
        "exists",
        "wip",
    )
    list_filter = (
        "exists",
        "wip",
        "type",
        "current_user",
    )
    search_fields = (
        "id",
        "name",
        "description",
        "next_building__id",
        "next_building__name",
    )
    autocomplete_fields = ("next_building",)

    @admin.display(description="next building", ordering="next_building__name")
    def next_building_link(self, obj):
        if obj.next_building:
            url = reverse("admin:database_building_change", args=(obj.next_building.pk,))
            return mark_safe(f'<a href="{url}">{obj.next_building}</a>')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("next_building")


@admin.register(Holding)
class HoldingAdmin(BaseAdmin):
    fieldsets = (
        (
            "General",
            {
                "fields": (
                    "id",
                    "name",
                    "description",
                ),
                "classes": (),
            },
        ),
        (
            "Specific",
            {
                "fields": (
                    "primary_building",
                    "buildings",
                ),
                "classes": (),
            },
        ),
        (
            "Internal",
            {
                "fields": (
                    "raw_data",
                    "exists",
                    "wip",
                ),
                "classes": ("collapse",),
            },
        ),
    )
    list_display = (
        "name",
        "primary_building",
        "exists",
        "wip",
    )
    search_fields = (
        "id",
        "name",
        "description",
        "primary_building__id",
        "primary_building__name",
    )
    autocomplete_fields = (
        "primary_building",
        "buildings",
    )

    @admin.display(description="primary building", ordering="primary_building__name")
    def primary_building_link(self, obj):
        if obj.primary_building:
            url = reverse("admin:database_building_change", args=(obj.primary_building.pk,))
            return mark_safe(f'<a href="{url}">{obj.primary_building}</a>')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("primary_building")


@admin.register(Terrain)
class TerrainAdmin(BaseAdmin):
    fieldsets = (
        (
            "General",
            {
                "fields": (
                    "id",
                    "name",
                    "description",
                    "color",
                ),
                "classes": (),
            },
        ),
        (
            "Statistics",
            {
                "fields": (
                    "movement_speed",
                    "combat_width",
                    "audio_parameter",
                    "supply_limit",
                    "development_growth",
                    "attacker_hard_casualty",
                    "attacker_retreat_losses",
                    "defender_hard_casualty",
                    "defender_retreat_losses",
                    "defender_advantage",
                ),
                "classes": (),
            },
        ),
        (
            "Internal",
            {
                "fields": (
                    "raw_data",
                    "exists",
                    "wip",
                ),
                "classes": ("collapse",),
            },
        ),
    )


class TerrainModifierInlineAdmin(EntityTabularInline):
    model = TerrainModifier
    extra = 0
    show_change_link = True
    ordering = (
        "men_at_arms",
        "terrain",
    )
    autocomplete_fields = ("terrain",)
    exclude = ("raw_data",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("men_at_arms", "terrain")


class CounterInlineAdmin(EntityTabularInline):
    model = Counter
    extra = 0
    show_change_link = True
    ordering = (
        "men_at_arms",
        "type",
    )
    exclude = ("raw_data",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("men_at_arms")


@admin.register(MenAtArms)
class MenAtArmsAdmin(BaseAdmin):
    fieldsets = (
        (
            "General",
            {
                "fields": (
                    "id",
                    "name",
                    "description",
                    "type",
                    "buy_cost",
                    "low_maintenance_cost",
                    "high_maintenance_cost",
                ),
                "classes": (),
            },
        ),
        (
            "Statistics",
            {
                "fields": (
                    "stack",
                    "damage",
                    "toughness",
                    "pursuit",
                    "screen",
                    "siege_tier",
                    "siege_value",
                ),
                "classes": (),
            },
        ),
        (
            "Internal",
            {
                "fields": (
                    "raw_data",
                    "exists",
                    "wip",
                ),
                "classes": ("collapse",),
            },
        ),
    )
    list_display = (
        "name",
        "type",
        "buy_cost",
        "stack",
        "exists",
        "wip",
    )
    list_filter = (
        "exists",
        "wip",
        "type",
        "current_user",
    )
    search_fields = (
        "id",
        "name",
        "description",
        "type",
    )
    inlines = (TerrainModifierInlineAdmin, CounterInlineAdmin)


@admin.register(TerrainModifier)
class TerrainModifierAdmin(EntityAdmin):
    list_display = (
        "men_at_arms_link",
        "terrain_link",
        "damage",
        "toughness",
        "pursuit",
        "screen",
    )
    list_editable = (
        "damage",
        "toughness",
        "pursuit",
        "screen",
    )
    search_fields = (
        "men_at_arms__id",
        "men_at_arms__name",
        "terrain__id",
        "terrain__name",
    )
    ordering = (
        "men_at_arms",
        "terrain",
    )
    autocomplete_fields = (
        "men_at_arms",
        "terrain",
    )

    @admin.display(description="men at arms", ordering="men_at_arms__name")
    def men_at_arms_link(self, obj):
        if obj.men_at_arms:
            url = reverse("admin:database_menatarms_change", args=(obj.men_at_arms.pk,))
            return mark_safe(f'<a href="{url}">{obj.men_at_arms}</a>')

    @admin.display(description="terrain", ordering="terrain__name")
    def terrain_link(self, obj):
        if obj.terrain:
            url = reverse("admin:database_terrain_change", args=(obj.terrain.pk,))
            return mark_safe(f'<a href="{url}">{obj.terrain}</a>')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("men_at_arms", "terrain")


@admin.register(Counter)
class CounterAdmin(EntityAdmin):
    list_display = (
        "men_at_arms_link",
        "type",
        "factor",
    )
    list_editable = (
        "type",
        "factor",
    )
    search_fields = (
        "men_at_arms__id",
        "men_at_arms__name",
        "type",
    )
    ordering = (
        "men_at_arms",
        "type",
    )
    autocomplete_fields = ("men_at_arms",)

    @admin.display(description="men at arms", ordering="men_at_arms__name")
    def men_at_arms_link(self, obj):
        if obj.men_at_arms:
            url = reverse("admin:database_menatarms_change", args=(obj.men_at_arms.pk,))
            return mark_safe(f'<a href="{url}">{obj.men_at_arms}</a>')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("men_at_arms")


class DoctrineTraitInlineAdmin(EntityTabularInline):
    model = DoctrineTrait
    extra = 0
    show_change_link = True
    ordering = (
        "doctrine",
        "trait",
    )
    autocomplete_fields = ("trait",)
    exclude = ("raw_data",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("doctrine", "trait")


@admin.register(Doctrine)
class DoctrineAdmin(BaseAdmin):
    fieldsets = (
        (
            "General",
            {
                "fields": (
                    "id",
                    "name",
                    "description",
                ),
                "classes": (),
            },
        ),
        (
            "Specific",
            {
                "fields": (
                    "group",
                    "multiple",
                ),
                "classes": (),
            },
        ),
        (
            "Internal",
            {
                "fields": (
                    "raw_data",
                    "exists",
                    "wip",
                ),
                "classes": ("collapse",),
            },
        ),
    )
    list_display = (
        "name",
        "group",
        "multiple",
        "exists",
        "wip",
    )
    list_filter = (
        "exists",
        "wip",
        "current_user",
    )
    search_fields = (
        "id",
        "name",
        "description",
        "group",
    )
    inlines = (DoctrineTraitInlineAdmin,)


@admin.register(DoctrineTrait)
class DoctrineTraitAdmin(EntityAdmin):
    list_display = (
        "doctrine_link",
        "trait_link",
        "is_virtue",
        "piety",
    )
    list_editable = (
        "is_virtue",
        "piety",
    )
    search_fields = (
        "doctrine__id",
        "doctrine__name",
        "trait__id",
        "trait__name",
    )
    ordering = (
        "doctrine",
        "trait",
    )
    autocomplete_fields = (
        "doctrine",
        "trait",
    )

    @admin.display(description="doctrine", ordering="doctrine__name")
    def doctrine_link(self, obj):
        if obj.doctrine:
            url = reverse("admin:database_doctrine_change", args=(obj.doctrine.pk,))
            return mark_safe(f'<a href="{url}">{obj.doctrine}</a>')

    @admin.display(description="trait", ordering="trait__name")
    def trait_link(self, obj):
        if obj.trait:
            url = reverse("admin:database_trait_change", args=(obj.trait.pk,))
            return mark_safe(f'<a href="{url}">{obj.trait}</a>')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("doctrine", "trait")


class ReligionTraitInlineAdmin(EntityTabularInline):
    model = ReligionTrait
    extra = 0
    show_change_link = True
    ordering = (
        "religion",
        "trait",
    )
    autocomplete_fields = ("trait",)
    exclude = ("raw_data",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("religion", "trait")


@admin.register(Religion)
class ReligionAdmin(BaseAdmin):
    fieldsets = (
        (
            "General",
            {
                "fields": (
                    "id",
                    "name",
                    "description",
                    "color",
                    "group",
                ),
                "classes": (),
            },
        ),
        (
            "Specific",
            {
                "fields": (
                    "religious_head",
                    "holy_sites",
                    "doctrines",
                    "men_at_arms",
                ),
                "classes": (),
            },
        ),
        (
            "Internal",
            {
                "fields": (
                    "raw_data",
                    "exists",
                    "wip",
                ),
                "classes": ("collapse",),
            },
        ),
    )
    list_display = (
        "name",
        "group",
        "religious_head_link",
        "exists",
        "wip",
    )
    search_fields = (
        "id",
        "name",
        "description",
        "group",
        "religious_head__id",
        "religious_head__name",
    )
    autocomplete_fields = (
        "religious_head",
        "holy_sites",
        "doctrines",
        "men_at_arms",
    )
    inlines = (ReligionTraitInlineAdmin,)

    @admin.display(description="religious head", ordering="religious_head__name")
    def religious_head_link(self, obj):
        if obj.religious_head:
            url = reverse("admin:database_title_change", args=(obj.religious_head.pk,))
            return mark_safe(f'<a href="{url}">{obj.religious_head}</a>')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("religious_head")


@admin.register(ReligionTrait)
class ReligionTraitAdmin(EntityAdmin):
    list_display = (
        "religion_link",
        "trait_link",
        "is_virtue",
        "piety",
    )
    list_editable = (
        "is_virtue",
        "piety",
    )
    search_fields = (
        "religion__id",
        "religion__name",
        "trait__id",
        "trait__name",
    )
    ordering = (
        "religion",
        "trait",
    )
    autocomplete_fields = (
        "religion",
        "trait",
    )

    @admin.display(description="religion", ordering="religion__name")
    def religion_link(self, obj):
        if obj.religion:
            url = reverse("admin:database_religion_change", args=(obj.religion.pk,))
            return mark_safe(f'<a href="{url}">{obj.religion}</a>')

    @admin.display(description="trait", ordering="trait__name")
    def trait_link(self, obj):
        if obj.trait:
            url = reverse("admin:database_trait_change", args=(obj.trait.pk,))
            return mark_safe(f'<a href="{url}">{obj.trait}</a>')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("religion", "trait")


class ProvinceHistoryInlineAdmin(EntityStackedInline):
    model = ProvinceHistory
    fk_name = "province"
    extra = 0
    show_change_link = True
    fieldsets = (
        (
            None,
            {
                "fields": ("date",),
                "classes": (),
            },
        ),
        (
            "Changes",
            {
                "fields": (
                    "culture",
                    "religion",
                    "holding",
                    "buildings",
                ),
                "classes": ("collapse",),
            },
        ),
    )
    ordering = (
        "province",
        "date",
    )
    autocomplete_fields = (
        "culture",
        "religion",
        "holding",
        "buildings",
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "province",
                "culture",
                "religion",
                "holding",
            )
            .prefetch_related("buildings")
        )


@admin.register(Province)
class ProvinceAdmin(BaseAdmin):
    fieldsets = (
        (
            "General",
            {
                "fields": (
                    "id",
                    "name",
                    "description",
                ),
                "classes": (),
            },
        ),
        (
            "Specific",
            {
                "fields": (
                    "culture",
                    "religion",
                    "holding",
                    "terrain",
                    "special_building_slot",
                    "special_building",
                    "winter_severity_bias",
                ),
                "classes": (),
            },
        ),
        (
            "Internal",
            {
                "fields": (
                    "raw_data",
                    "exists",
                    "wip",
                ),
                "classes": ("collapse",),
            },
        ),
    )
    list_display = (
        "name",
        "terrain_link",
        "holding_link",
        "culture_link",
        "religion_link",
        "exists",
        "wip",
    )
    list_filter = (
        "exists",
        "wip",
        "holding",
        "current_user",
    )
    search_fields = (
        "id",
        "name",
        "description",
        "terrain__id",
        "terrain__name",
        "holding__id",
        "holding__name",
        "culture__id",
        "culture__name",
        "religion__id",
        "religion__name",
    )
    autocomplete_fields = (
        "terrain",
        "culture",
        "religion",
        "holding",
    )
    inlines = (ProvinceHistoryInlineAdmin,)

    @admin.display(description="terrain", ordering="terrain__name")
    def terrain_link(self, obj):
        if obj.terrain:
            url = reverse("admin:database_terrain_change", args=(obj.terrain.pk,))
            return mark_safe(f'<a href="{url}">{obj.terrain}</a>')

    @admin.display(description="holding", ordering="holding__name")
    def holding_link(self, obj):
        if obj.holding:
            url = reverse("admin:database_holding_change", args=(obj.holding.pk,))
            return mark_safe(f'<a href="{url}">{obj.holding}</a>')

    @admin.display(description="culture", ordering="culture__name")
    def culture_link(self, obj):
        if obj.culture:
            url = reverse("admin:database_culture_change", args=(obj.culture.pk,))
            return mark_safe(f'<a href="{url}">{obj.culture}</a>')

    @admin.display(description="religion", ordering="religion__name")
    def religion_link(self, obj):
        if obj.religion:
            url = reverse("admin:database_religion_change", args=(obj.religion.pk,))
            return mark_safe(f'<a href="{url}">{obj.religion}</a>')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("terrain", "holding", "culture", "religion")


@admin.register(ProvinceHistory)
class ProvinceHistoryAdmin(EntityAdmin):
    fieldsets = (
        (
            "General",
            {
                "fields": (
                    "province",
                    "date",
                ),
                "classes": (),
            },
        ),
        (
            "Changes",
            {
                "fields": (
                    "culture",
                    "religion",
                    "holding",
                    "buildings",
                ),
                "classes": (),
            },
        ),
        (
            "Internal",
            {
                "fields": ("raw_data",),
                "classes": ("collapse",),
            },
        ),
    )
    list_display = (
        "province_link",
        "date",
    )
    list_filter = (
        "date",
        "current_user",
    )
    search_fields = (
        "province__id",
        "province__name",
        "holding__id",
        "holding__name",
        "culture__id",
        "culture__name",
        "religion__id",
        "religion__name",
    )
    ordering = (
        "province",
        "date",
    )
    autocomplete_fields = (
        "province",
        "culture",
        "religion",
        "holding",
        "buildings",
    )
    readonly_fields = ("province",)

    @admin.display(description="province", ordering="province__name")
    def province_link(self, obj):
        if obj.province:
            url = reverse("admin:database_province_change", args=(obj.province.pk,))
            return mark_safe(f'<a href="{url}">{obj.province}</a>')

    @admin.display(description="holding", ordering="holding__name")
    def holding_link(self, obj):
        if obj.holding:
            url = reverse("admin:database_holding_change", args=(obj.holding.pk,))
            return mark_safe(f'<a href="{url}">{obj.holding}</a>')

    @admin.display(description="culture", ordering="culture__name")
    def culture_link(self, obj):
        if obj.culture:
            url = reverse("admin:database_culture_change", args=(obj.culture.pk,))
            return mark_safe(f'<a href="{url}">{obj.culture}</a>')

    @admin.display(description="religion", ordering="religion__name")
    def religion_link(self, obj):
        if obj.religion:
            url = reverse("admin:database_religion_change", args=(obj.religion.pk,))
            return mark_safe(f'<a href="{url}">{obj.religion}</a>')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("province", "holding", "culture", "religion")


class TitleHistoryInlineAdmin(EntityStackedInline):
    model = TitleHistory
    fk_name = "title"
    extra = 0
    show_change_link = True
    fieldsets = (
        (
            None,
            {
                "fields": ("date",),
                "classes": (),
            },
        ),
        (
            "Changes",
            {
                "fields": (
                    "holder",
                    "de_jure_liege",
                    "liege",
                    "is_independent",
                    "is_destroyed",
                    "development_level",
                    "succession_laws",
                ),
                "classes": ("collapse",),
            },
        ),
    )
    ordering = (
        "title",
        "date",
    )
    autocomplete_fields = (
        "de_jure_liege",
        "liege",
        "holder",
        "succession_laws",
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "title",
                "de_jure_liege",
                "liege",
                "holder",
            )
            .prefetch_related("succession_laws")
        )


@admin.register(Title)
class TitleAdmin(BaseAdmin):
    fieldsets = (
        (
            "General",
            {
                "fields": (
                    "id",
                    "prefix",
                    "name",
                    "description",
                ),
                "classes": (),
            },
        ),
        (
            "Specific",
            {
                "fields": (
                    "tier",
                    "color",
                    "province",
                    "de_jure_liege",
                    "capital",
                ),
                "classes": (),
            },
        ),
        (
            "Internal",
            {
                "fields": (
                    "raw_data",
                    "exists",
                    "wip",
                ),
                "classes": ("collapse",),
            },
        ),
    )
    list_display = (
        "full_name",
        "tier",
        "de_jure_liege_link",
        "capital_link",
        "exists",
        "wip",
    )
    list_filter = (
        "exists",
        "wip",
        "tier",
        "current_user",
    )
    search_fields = (
        "id",
        "name",
        "description",
        "de_jure_liege__id",
        "de_jure_liege__name",
        "capital__id",
        "capital__name",
    )
    autocomplete_fields = (
        "province",
        "de_jure_liege",
        "capital",
    )
    inlines = (TitleHistoryInlineAdmin,)

    @admin.display(description="full name", ordering="name")
    def full_name(self, obj):
        if obj.prefix and obj.name:
            return f"{obj.prefix}{obj.name}"
        return obj.name

    @admin.display(description="de jure liege", ordering="de_jure_liege__name")
    def de_jure_liege_link(self, obj):
        if obj.de_jure_liege:
            url = reverse("admin:database_title_change", args=(obj.de_jure_liege.pk,))
            return mark_safe(f'<a href="{url}">{obj.de_jure_liege}</a>')

    @admin.display(description="capital", ordering="capital__name")
    def capital_link(self, obj):
        if obj.capital:
            url = reverse("admin:database_title_change", args=(obj.capital.pk,))
            return mark_safe(f'<a href="{url}">{obj.capital}</a>')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("de_jure_liege", "capital")


@admin.register(TitleHistory)
class TitleHistoryAdmin(EntityAdmin):
    fieldsets = (
        (
            "General",
            {
                "fields": (
                    "title",
                    "date",
                ),
                "classes": (),
            },
        ),
        (
            "Changes",
            {
                "fields": (
                    "holder",
                    "de_jure_liege",
                    "liege",
                    "is_independent",
                    "is_destroyed",
                    "development_level",
                    "succession_laws",
                ),
                "classes": (),
            },
        ),
        (
            "Internal",
            {
                "fields": ("raw_data",),
                "classes": ("collapse",),
            },
        ),
    )
    list_display = (
        "title_link",
        "date",
        "holder_link",
    )
    list_filter = (
        "date",
        "current_user",
    )
    search_fields = (
        "title__id",
        "title__name",
        "holder__id",
        "holder__name",
    )
    ordering = (
        "title",
        "date",
    )
    autocomplete_fields = (
        "de_jure_liege",
        "liege",
        "holder",
        "succession_laws",
    )
    readonly_fields = ("title",)

    @admin.display(description="title", ordering="title__name")
    def title_link(self, obj):
        if obj.title:
            url = reverse("admin:database_title_change", args=(obj.title.pk,))
            return mark_safe(f'<a href="{url}">{obj.title}</a>')

    @admin.display(description="holder", ordering="holder__name")
    def holder_link(self, obj):
        if obj.holder:
            url = reverse("admin:database_character_change", args=(obj.holder.pk,))
            return mark_safe(f'<a href="{url}">{obj.holder}</a>')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("title", "holder")


@admin.register(HolySite)
class HolySiteAdmin(BaseAdmin):
    fieldsets = (
        (
            "General",
            {
                "fields": (
                    "id",
                    "name",
                    "description",
                ),
                "classes": (),
            },
        ),
        (
            "Specific",
            {
                "fields": (
                    "county",
                    "barony",
                ),
                "classes": (),
            },
        ),
        (
            "Internal",
            {
                "fields": (
                    "raw_data",
                    "exists",
                    "wip",
                ),
                "classes": ("collapse",),
            },
        ),
    )
    list_display = (
        "name",
        "county_link",
        "barony_link",
        "exists",
        "wip",
    )
    list_filter = (
        "exists",
        "wip",
        "current_user",
    )
    search_fields = (
        "id",
        "name",
        "description",
        "county__id",
        "county__name",
        "barony__id",
        "barony__name",
    )
    autocomplete_fields = (
        "county",
        "barony",
    )

    @admin.display(description="county", ordering="county__name")
    def county_link(self, obj):
        if obj.county:
            url = reverse("admin:database_title_change", args=(obj.county.pk,))
            return mark_safe(f'<a href="{url}">{obj.county}</a>')

    @admin.display(description="barony", ordering="barony__name")
    def barony_link(self, obj):
        if obj.barony:
            url = reverse("admin:database_title_change", args=(obj.barony.pk,))
            return mark_safe(f'<a href="{url}">{obj.barony}</a>')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("county", "barony")


@admin.register(Nickname)
class NicknameAdmin(BaseAdmin):
    fieldsets = (
        (
            "General",
            {
                "fields": (
                    "id",
                    "name",
                    "description",
                ),
                "classes": (),
            },
        ),
        (
            "Specific",
            {
                "fields": (
                    "is_bad",
                    "is_prefix",
                ),
                "classes": (),
            },
        ),
        (
            "Internal",
            {
                "fields": (
                    "raw_data",
                    "exists",
                    "wip",
                ),
                "classes": ("collapse",),
            },
        ),
    )
    list_display = (
        "name",
        "is_bad",
        "is_prefix",
        "exists",
        "wip",
    )
    list_filter = (
        "exists",
        "wip",
        "is_bad",
        "is_prefix",
        "current_user",
    )


@admin.register(DeathReason)
class DeathReasonAdmin(BaseAdmin):
    fieldsets = (
        (
            "General",
            {
                "fields": (
                    "id",
                    "name",
                    "description",
                ),
                "classes": (),
            },
        ),
        (
            "Specific",
            {
                "fields": (
                    "is_default",
                    "is_natural",
                    "is_public_knowledge",
                ),
                "classes": (),
            },
        ),
        (
            "Internal",
            {
                "fields": (
                    "raw_data",
                    "exists",
                    "wip",
                ),
                "classes": ("collapse",),
            },
        ),
    )
    list_display = (
        "name",
        "is_default",
        "is_natural",
        "is_public_knowledge",
        "exists",
        "wip",
    )
    list_filter = (
        "exists",
        "wip",
        "is_default",
        "is_natural",
        "is_public_knowledge",
        "current_user",
    )


@admin.register(Dynasty)
class DynastyAdmin(BaseAdmin):
    fieldsets = (
        (
            "General",
            {
                "fields": (
                    "id",
                    "prefix",
                    "name",
                    "description",
                ),
                "classes": (),
            },
        ),
        (
            "Specific",
            {
                "fields": (
                    "culture",
                    "coa_text",
                ),
                "classes": (),
            },
        ),
        (
            "Internal",
            {
                "fields": (
                    "coa_data",
                    "raw_data",
                    "exists",
                    "wip",
                ),
                "classes": ("collapse",),
            },
        ),
    )
    list_display = (
        "full_name",
        "culture_link",
        "exists",
        "wip",
    )
    list_filter = (
        "exists",
        "wip",
        "current_user",
    )
    search_fields = (
        "id",
        "name",
        "description",
        "culture__id",
        "culture__name",
    )
    autocomplete_fields = ("culture",)
    readonly_fields = ("coa_data",)

    @admin.display(description="full name", ordering="name")
    def full_name(self, obj):
        if obj.prefix and obj.name:
            return f"{obj.prefix}{obj.name}"
        return obj.name

    @admin.display(description="culture", ordering="culture__name")
    def culture_link(self, obj):
        if obj.culture:
            url = reverse("admin:database_culture_change", args=(obj.culture.pk,))
            return mark_safe(f'<a href="{url}">{obj.culture}</a>')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("culture")


@admin.register(House)
class HouseAdmin(BaseAdmin):
    fieldsets = (
        (
            "General",
            {
                "fields": (
                    "id",
                    "prefix",
                    "name",
                    "description",
                ),
                "classes": (),
            },
        ),
        (
            "Specific",
            {
                "fields": (
                    "dynasty",
                    "coa_text",
                ),
                "classes": (),
            },
        ),
        (
            "Internal",
            {
                "fields": (
                    "coa_data",
                    "raw_data",
                    "exists",
                    "wip",
                ),
                "classes": ("collapse",),
            },
        ),
    )
    list_display = (
        "full_name",
        "dynasty_link",
        "exists",
        "wip",
    )
    list_filter = (
        "exists",
        "wip",
        "current_user",
    )
    search_fields = (
        "id",
        "name",
        "description",
        "dynasty__id",
        "dynasty__name",
    )
    autocomplete_fields = ("dynasty",)
    readonly_fields = ("coa_data",)

    @admin.display(description="full name", ordering="name")
    def full_name(self, obj):
        if obj.prefix and obj.name:
            return f"{obj.prefix}{obj.name}"
        return obj.name

    @admin.display(description="dynasty", ordering="dynasty__name")
    def dynasty_link(self, obj):
        if obj.dynasty:
            url = reverse("admin:database_dynasty_change", args=(obj.dynasty.pk,))
            return mark_safe(f'<a href="{url}">{obj.dynasty}</a>')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("dynasty")


class CharacterHistoryInlineAdmin(EntityStackedInline):
    model = CharacterHistory
    fk_name = "character"
    extra = 0
    show_change_link = True
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "date",
                    "event",
                ),
                "classes": (),
            },
        ),
        (
            "Family",
            {
                "fields": (
                    "dynasty",
                    "house",
                    "add_spouse",
                    "add_matrilineal_spouse",
                    "remove_spouse",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Relations",
            {
                "fields": (
                    "is_unemployed",
                    "employer",
                    "add_lovers",
                    "remove_lovers",
                    "add_soulmate",
                    "remove_soulmate",
                    "add_potential_friends",
                    "remove_potential_friends",
                    "add_friends",
                    "remove_friends",
                    "add_best_friend",
                    "remove_best_friend",
                    "add_potential_rivals",
                    "remove_potential_rivals",
                    "add_rivals",
                    "remove_rivals",
                    "add_nemesis",
                    "remove_nemesis",
                    "add_guardian",
                    "remove_guardian",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Others",
            {
                "fields": (
                    "nickname",
                    "culture",
                    "religion",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Statistics & traits",
            {
                "fields": (
                    "diplomacy",
                    "martial",
                    "stewardship",
                    "intrigue",
                    "learning",
                    "prowess",
                    "traits_added",
                    "traits_removed",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Resources",
            {
                "fields": (
                    "gold",
                    "prestige",
                    "piety",
                ),
                "classes": ("collapse",),
            },
        ),
    )
    ordering = (
        "character",
        "date",
    )
    autocomplete_fields = (
        "nickname",
        "culture",
        "religion",
        "dynasty",
        "house",
        "add_spouse",
        "add_matrilineal_spouse",
        "remove_spouse",
        "employer",
        "add_lovers",
        "remove_lovers",
        "add_soulmate",
        "remove_soulmate",
        "add_potential_friends",
        "remove_potential_friends",
        "add_friends",
        "remove_friends",
        "add_best_friend",
        "remove_best_friend",
        "add_potential_rivals",
        "remove_potential_rivals",
        "add_rivals",
        "remove_rivals",
        "add_nemesis",
        "remove_nemesis",
        "add_guardian",
        "remove_guardian",
        "traits_added",
        "traits_removed",
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "character",
                "nickname",
                "culture",
                "religion",
                "dynasty",
                "house",
                "add_spouse",
                "add_matrilineal_spouse",
                "remove_spouse",
                "employer",
                "add_soulmate",
                "remove_soulmate",
                "add_best_friend",
                "remove_best_friend",
                "add_nemesis",
                "remove_nemesis",
                "add_guardian",
                "remove_guardian",
            )
            .prefetch_related(
                "add_lovers",
                "remove_lovers",
                "add_potential_friends",
                "remove_potential_friends",
                "add_friends",
                "remove_friends",
                "add_potential_rivals",
                "remove_potential_rivals",
                "add_rivals",
                "remove_rivals",
                "traits_added",
                "traits_removed",
            )
        )


@admin.action(description="Generate selected characters data in Paradox format")
def generate_character_data(modeladmin, request, queryset):
    all_data = {}
    for item in queryset:
        all_data.update(item.revert_data())
    text = revert(all_data)
    return HttpResponse(text.encode("utf_8_sig"), content_type="text/plain")


@admin.register(Character)
class CharacterAdmin(BaseAdmin):
    fieldsets = (
        (
            "General",
            {
                "fields": (
                    "id",
                    "name",
                    "description",
                ),
                "classes": (),
            },
        ),
        (
            "Character",
            {
                "fields": (
                    "gender",
                    "sexuality",
                    "birth_date",
                    "death_date",
                    "death_reason",
                    "killer",
                    "nickname",
                    "dna_text",
                ),
                "classes": (),
            },
        ),
        (
            "Family",
            {
                "fields": (
                    "culture",
                    "religion",
                    "dynasty",
                    "house",
                    "father",
                    "mother",
                ),
                "classes": (),
            },
        ),
        (
            "Statistics & traits",
            {
                "fields": (
                    "diplomacy",
                    "martial",
                    "stewardship",
                    "intrigue",
                    "learning",
                    "prowess",
                    "traits",
                    "random_traits",
                ),
                "classes": (),
            },
        ),
        (
            "Resources",
            {
                "fields": (
                    "gold",
                    "prestige",
                    "piety",
                ),
                "classes": (),
            },
        ),
        (
            "Internal",
            {
                "fields": (
                    "dna_data",
                    "raw_data",
                    "exists",
                    "wip",
                ),
                "classes": ("collapse",),
            },
        ),
    )
    list_display = (
        "name",
        "house_link",
        "dynasty_link",
        "birth_date",
        "death_date",
        "father_link",
        "mother_link",
        "exists",
        "wip",
    )
    list_filter = (
        "exists",
        "wip",
        "gender",
        "sexuality",
        "current_user",
    )
    search_fields = (
        "id",
        "name",
        "description",
        "house__id",
        "house__name",
        "dynasty__id",
        "dynasty__name",
        "father__id",
        "father__name",
        "mother__id",
        "mother__name",
    )
    autocomplete_fields = (
        "death_reason",
        "killer",
        "nickname",
        "culture",
        "religion",
        "dynasty",
        "house",
        "father",
        "mother",
        "traits",
    )
    readonly_fields = ("dna_data",)
    inlines = (CharacterHistoryInlineAdmin,)
    actions = BaseAdmin.actions + [
        generate_character_data,
    ]

    @admin.display(description="house", ordering="house__name")
    def house_link(self, obj):
        if obj.house:
            url = reverse("admin:database_house_change", args=(obj.house.pk,))
            return mark_safe(f'<a href="{url}">{obj.house}</a>')

    @admin.display(description="dynasty", ordering="dynasty__name")
    def dynasty_link(self, obj):
        if obj.dynasty:
            url = reverse("admin:database_dynasty_change", args=(obj.dynasty.pk,))
            return mark_safe(f'<a href="{url}">{obj.dynasty}</a>')

    @admin.display(description="father", ordering="father__name")
    def father_link(self, obj):
        if obj.father:
            url = reverse("admin:database_character_change", args=(obj.father.pk,))
            return mark_safe(f'<a href="{url}">{obj.father}</a>')

    @admin.display(description="mother", ordering="mother__name")
    def mother_link(self, obj):
        if obj.mother:
            url = reverse("admin:database_character_change", args=(obj.mother.pk,))
            return mark_safe(f'<a href="{url}">{obj.mother}</a>')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("house", "dynasty", "father", "mother")


@admin.register(CharacterHistory)
class CharacterHistoryAdmin(EntityAdmin):
    fieldsets = (
        (
            "General",
            {
                "fields": (
                    "character",
                    "date",
                    "event",
                ),
                "classes": (),
            },
        ),
        (
            "Family",
            {
                "fields": (
                    "dynasty",
                    "house",
                    "add_spouse",
                    "add_matrilineal_spouse",
                    "remove_spouse",
                ),
                "classes": (),
            },
        ),
        (
            "Relations",
            {
                "fields": (
                    "is_unemployed",
                    "employer",
                    "add_lovers",
                    "remove_lovers",
                    "add_soulmate",
                    "remove_soulmate",
                    "add_potential_friends",
                    "remove_potential_friends",
                    "add_friends",
                    "remove_friends",
                    "add_best_friend",
                    "remove_best_friend",
                    "add_potential_rivals",
                    "remove_potential_rivals",
                    "add_rivals",
                    "remove_rivals",
                    "add_nemesis",
                    "remove_nemesis",
                    "add_guardian",
                    "remove_guardian",
                ),
                "classes": (),
            },
        ),
        (
            "Others",
            {
                "fields": (
                    "nickname",
                    "culture",
                    "religion",
                ),
                "classes": (),
            },
        ),
        (
            "Statistics & traits",
            {
                "fields": (
                    "diplomacy",
                    "martial",
                    "stewardship",
                    "intrigue",
                    "learning",
                    "prowess",
                    "traits_added",
                    "traits_removed",
                ),
                "classes": (),
            },
        ),
        (
            "Resources",
            {
                "fields": (
                    "gold",
                    "prestige",
                    "piety",
                ),
                "classes": (),
            },
        ),
        (
            "Internal",
            {
                "fields": ("raw_data",),
                "classes": ("collapse",),
            },
        ),
    )
    list_display = (
        "character_link",
        "date",
        "event",
    )
    list_filter = (
        "event",
        "date",
        "current_user",
    )
    search_fields = (
        "character__id",
        "character__name",
    )
    ordering = (
        "character",
        "date",
    )
    autocomplete_fields = (
        "nickname",
        "culture",
        "religion",
        "dynasty",
        "house",
        "add_spouse",
        "add_matrilineal_spouse",
        "remove_spouse",
        "employer",
        "add_lovers",
        "remove_lovers",
        "add_soulmate",
        "remove_soulmate",
        "add_potential_friends",
        "remove_potential_friends",
        "add_friends",
        "remove_friends",
        "add_best_friend",
        "remove_best_friend",
        "add_potential_rivals",
        "remove_potential_rivals",
        "add_rivals",
        "remove_rivals",
        "add_nemesis",
        "remove_nemesis",
        "add_guardian",
        "remove_guardian",
        "traits_added",
        "traits_removed",
    )
    readonly_fields = ("character",)

    @admin.display(description="character", ordering="character__name")
    def character_link(self, obj):
        if obj.character:
            url = reverse("admin:database_character_change", args=(obj.character.pk,))
            return mark_safe(f'<a href="{url}">{obj.character}</a>')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("character")


@admin.register(Law)
class LawAdmin(BaseAdmin):
    fieldsets = (
        (
            "General",
            {
                "fields": (
                    "id",
                    "name",
                    "description",
                ),
                "classes": (),
            },
        ),
        (
            "Specific",
            {
                "fields": ("group",),
                "classes": (),
            },
        ),
        (
            "Internal",
            {
                "fields": (
                    "raw_data",
                    "exists",
                    "wip",
                ),
                "classes": ("collapse",),
            },
        ),
    )
    list_display = (
        "name",
        "group",
        "exists",
        "wip",
    )
    list_filter = (
        "exists",
        "wip",
        "group",
        "current_user",
    )


@admin.register(Localization)
class LocalizationAdmin(EntityAdmin):
    list_display = (
        "text",
        "language",
        "wip",
    )
    list_filter = ("wip",)
    search_fields = (
        "key",
        "text",
    )
    ordering = ("key",)


@admin.register(CasusBelliGroup)
class CasusBelliGroup(BaseAdmin):
    pass


@admin.register(CasusBelli)
class CasusBelli(BaseAdmin):
    fieldsets = (
        (
            "General",
            {
                "fields": (
                    "id",
                    "name",
                    "description",
                ),
                "classes": (),
            },
        ),
        (
            "Specific",
            {
                "fields": (
                    "group",
                    "target_titles",
                    "target_title_tier",
                ),
                "classes": (),
            },
        ),
        (
            "Internal",
            {
                "fields": (
                    "raw_data",
                    "exists",
                    "wip",
                ),
                "classes": ("collapse",),
            },
        ),
    )
    list_display = (
        "name",
        "group_link",
        "target_titles",
        "target_title_tier",
        "exists",
        "wip",
    )
    list_filter = (
        "exists",
        "wip",
        "group",
        "target_titles",
        "target_title_tier",
        "current_user",
    )
    autocomplete_fields = ("group",)

    @admin.display(description="group", ordering="group__name")
    def group_link(self, obj):
        if obj.group:
            url = reverse("admin:database_casusbelligroup_change", args=(obj.group.pk,))
            return mark_safe(f'<a href="{url}">{obj.group}</a>')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("group")


@admin.register(War)
class WarAdmin(BaseAdmin):
    fieldsets = (
        (
            "General",
            {
                "fields": (
                    "id",
                    "name",
                    "description",
                ),
                "classes": (),
            },
        ),
        (
            "Specific",
            {
                "fields": (
                    "start_date",
                    "end_date",
                    "casus_belli",
                    "targeted_titles",
                    "attackers",
                    "defenders",
                    "claimant",
                ),
                "classes": (),
            },
        ),
        (
            "Internal",
            {
                "fields": (
                    "raw_data",
                    "exists",
                    "wip",
                ),
                "classes": ("collapse",),
            },
        ),
    )
    list_display = (
        "name",
        "start_date",
        "end_date",
        "casus_belli_link",
        "claimant_link",
        "exists",
        "wip",
    )
    list_filter = (
        "exists",
        "wip",
        "current_user",
    )
    search_fields = (
        "casus_belli__id",
        "casus_belli__name",
        "claimant__id",
        "claimant__name",
    )
    ordering = (
        "start_date",
        "end_date",
    )
    autocomplete_fields = (
        "casus_belli",
        "targeted_titles",
        "attackers",
        "defenders",
        "claimant",
    )

    @admin.display(description="casus belli", ordering="casus_belli__name")
    def casus_belli_link(self, obj):
        if obj.casus_belli:
            url = reverse("admin:database_casusbelli_change", args=(obj.casus_belli.pk,))
            return mark_safe(f'<a href="{url}">{obj.casus_belli}</a>')

    @admin.display(description="claimant", ordering="claimant__name")
    def claimant_link(self, obj):
        if obj.claimant:
            url = reverse("admin:database_character_change", args=(obj.claimant.pk,))
            return mark_safe(f'<a href="{url}">{obj.claimant}</a>')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("casus_belli", "claimant")
