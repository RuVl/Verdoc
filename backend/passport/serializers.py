from modeltranslation.translator import translator
from modeltranslation.utils import get_translation_fields
from rest_framework import serializers

from passport.models import Passport, Country


# noinspection PyUnresolvedReferences
class TranslationFieldsMixin:
    """ Mixin for serializers that have translatable fields. """

    def get_fields(self):
        opts = self.Meta
        orig_fields = opts.fields
        new_fields = []
        trans_opts = translator.get_options_for_model(opts.model)

        for field_name in orig_fields:
            if field_name in trans_opts.fields:
                new_fields.extend(get_translation_fields(field_name))
            else:
                new_fields.append(field_name)
        self.Meta.fields = tuple(new_fields)
        return super().get_fields()


class PassportSerializer(TranslationFieldsMixin, serializers.ModelSerializer):
    """ Passport serializer for sending product info. """

    class Meta:
        model = Passport
        # noinspection PyUnresolvedReferences
        fields = ('id', 'name', 'quantity', 'price', 'price_currency')  # price_currency - dynamic field from MoneyField


class CountrySerializer(TranslationFieldsMixin, serializers.ModelSerializer):
    """ Country serializer for sending all country's passports. """

    passports = serializers.SerializerMethodField()

    class Meta:
        model = Country
        fields = ('id', 'name', 'code', 'passports')

    def get_passports(self, obj):
        passports = obj.passports.filter(quantity__gt=0)
        return PassportSerializer(passports, many=True).data
