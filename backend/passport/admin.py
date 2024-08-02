from django.contrib import admin
from modeltranslation.admin import TranslationAdmin

from passport.models import Passport, PassportFile, Country


class PassportInline(admin.TabularInline):
    model = Passport
    fields = ['name', 'price', 'quantity']
    readonly_fields = ['quantity']
    extra = 0


@admin.register(Country)
class CountryAdmin(TranslationAdmin):
    list_display = ['name', 'code']
    search_fields = ['name', 'code']
    inlines = [PassportInline]


class PassportFileInline(admin.TabularInline):
    model = PassportFile
    fields = ['file_path', 'status']
    readonly_fields = ['status']
    extra = 0

    def has_delete_permission(self, request, obj=None):
        if isinstance(obj, PassportFile) and obj.status != PassportFile.PassportFileStatus.IN_STOCK:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(Passport)
class PassportAdmin(TranslationAdmin):
    list_display = ['name', 'price', 'quantity', 'reserved', 'sold', 'country']
    list_filter = ['country']
    search_fields = ['name']
    readonly_fields = ['quantity', 'reserved', 'sold']
    inlines = [PassportFileInline]

    def quantity(self, obj):
        return obj.files.filter(status=PassportFile.PassportFileStatus.IN_STOCK).count()

    quantity.short_description = 'Quantity in Stock'

    def reserved(self, obj):
        return obj.files.filter(status=PassportFile.PassportFileStatus.RESERVED).count()

    reserved.short_description = 'Quantity reserved'

    def sold(self, obj):
        return obj.files.filter(status=PassportFile.PassportFileStatus.SOLD).count()

    sold.short_description = 'Quantity sold'


@admin.register(PassportFile)
class PassportFileAdmin(admin.ModelAdmin):
    list_display = ['passport', 'file_path', 'status']
    list_filter = ['status', 'passport__country']
    search_fields = ['passport__name', 'file_path']
    list_select_related = ['passport']
    readonly_fields = ['status']

    def has_delete_permission(self, request, obj=None):
        if obj and obj.status != PassportFile.PassportFileStatus.IN_STOCK:
            return False
        return super().has_delete_permission(request, obj)
