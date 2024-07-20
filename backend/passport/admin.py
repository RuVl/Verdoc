from django.contrib import admin

from passport.models import Passport, PassportFile, Country


@admin.register(Passport)
class PassportAdmin(admin.ModelAdmin):
    list_display = ['name', 'price', 'quantity', 'country']
    list_filter = ('country',)

    def quantity(self, obj):
        return obj.quantity

    quantity.short_description = 'Quantity'


admin.site.register(Country)
admin.site.register(PassportFile)
