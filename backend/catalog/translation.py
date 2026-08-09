from modeltranslation.translator import TranslationOptions, register

from catalog.models import Country, Product


@register(Country)
class CountryTranslationOptions(TranslationOptions):
    fields = ("name",)


@register(Product)
class ProductTranslationOptions(TranslationOptions):
    fields = ("name",)
