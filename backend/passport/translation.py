from modeltranslation.translator import register, TranslationOptions

from passport.models import Country, Passport


@register(Country)
class CountryTranslationOptions(TranslationOptions):
    fields = ('name',)


@register(Passport)
class PassportTranslationOptions(TranslationOptions):
    fields = ('name',)
