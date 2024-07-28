from django.contrib import admin

from passport.models import Passport, PassportFile, Country


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ['name', 'code']
    search_fields = ['name', 'code']


class PassportFileInline(admin.TabularInline):
    model = PassportFile
    fields = ['file_path', 'status']
    readonly_fields = ['status']
    extra = 0


@admin.register(Passport)
class PassportAdmin(admin.ModelAdmin):
    list_display = ['name', 'price', 'quantity', 'country']
    list_filter = ['country']
    search_fields = ['name']
    readonly_fields = ['quantity']
    inlines = [PassportFileInline]

    def quantity(self, obj):
        return obj.files.filter(status='IN_STOCK').count()

    quantity.short_description = 'Quantity in Stock'


@admin.register(PassportFile)
class PassportFileAdmin(admin.ModelAdmin):
    list_display = ['passport', 'file_path', 'status']
    list_filter = ['status', 'passport__country']
    search_fields = ['passport__name', 'file_path']
    list_select_related = ['passport']
    readonly_fields = ['status']

    def has_delete_permission(self, request, obj=None):
        if obj and obj.status != 'IN_STOCK':
            return False
        return super().has_delete_permission(request, obj)
