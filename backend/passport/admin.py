from django.contrib import admin
from django.db.models import QuerySet
from modeltranslation.admin import TranslationAdmin

from passport.forms import CountryForm
from passport.models import Country, Passport, PassportFile


class PassportInline(admin.TabularInline):
    model = Passport
    fields = ["name", "price", "quantity"]
    readonly_fields = ["quantity"]
    extra = 0


@admin.register(Country)
class CountryAdmin(TranslationAdmin):
    form = CountryForm
    list_display = ["flag", "name", "code"]
    search_fields = ["name", "code"]


class PassportFileInline(admin.TabularInline):
    model = PassportFile
    fields = ["file_path", "status"]
    readonly_fields = ["status"]
    extra = 0

    def has_delete_permission(self, request, obj=None):
        if isinstance(obj, PassportFile) and obj.status != PassportFile.PassportFileStatus.IN_STOCK:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(Passport)
class PassportAdmin(TranslationAdmin):
    list_display = ["name", "price", "quantity", "reserved", "sold", "country"]
    list_filter = ["country"]
    search_fields = ["name"]
    readonly_fields = ["quantity", "reserved", "sold"]
    inlines = [PassportFileInline]

    @admin.display(description="In Stock")
    def quantity(self, obj):
        return obj.files.filter(status=PassportFile.PassportFileStatus.IN_STOCK).count()

    @admin.display(description="Reserved")
    def reserved(self, obj):
        return obj.files.filter(status=PassportFile.PassportFileStatus.RESERVED).count()

    @admin.display(description="Sold")
    def sold(self, obj):
        return obj.files.filter(status=PassportFile.PassportFileStatus.SOLD).count()


class HasSoldErrorFilter(admin.SimpleListFilter):
    title = "Ошибка при продаже"
    parameter_name = "has_sold_error"

    def lookups(self, request, model_admin):
        return [
            ("has_sold_error", "Есть ошибки"),
        ]

    def queryset(self, request, queryset: QuerySet[PassportFile]):
        if self.value() == "has_sold_error":
            return queryset.filter(
                status=PassportFile.PassportFileStatus.SOLD,
                downloadlink__isnull=True,
            )

        return queryset


@admin.register(PassportFile)
class PassportFileAdmin(admin.ModelAdmin):
    list_display = ["id", "passport", "file_path", "status"]
    list_filter = [HasSoldErrorFilter, "status", "passport__country"]
    search_fields = ["passport__name", "file_path"]
    list_select_related = ["passport"]
    readonly_fields = ["status"]

    def has_delete_permission(self, request, obj=None):
        if obj and obj.status != PassportFile.PassportFileStatus.IN_STOCK:
            return False
        return super().has_delete_permission(request, obj)
