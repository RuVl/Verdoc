from modeltranslation.translator import TranslationOptions, register

from passport.models import Country, Passport


@register(Country)
class CountryTranslationOptions(TranslationOptions):
    fields = ("name",)


@register(Passport)
class PassportTranslationOptions(TranslationOptions):
    fields = ("name",)
