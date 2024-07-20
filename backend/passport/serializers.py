from djmoney.money import Money
from modeltranslation.translator import translator
from modeltranslation.utils import get_translation_fields
from rest_framework import serializers

from passport.models import Passport, Country


class MoneyFieldSerializer(serializers.Field):
    def to_representation(self, value):
        return {"amount": float(value.amount), "currency": str(value.currency)}

    def to_internal_value(self, data):
        try:
            amount = data.get("amount")
            currency = data.get("currency")
            return Money(amount, currency)
        except (ValueError, TypeError):
            raise serializers.ValidationError("Invalid money value")


# noinspection PyUnresolvedReferences
class TranslationFieldsMixin:
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
    price = MoneyFieldSerializer()

    class Meta:
        model = Passport
        fields = ('id', 'name', 'quantity', 'price')


class CountrySerializer(TranslationFieldsMixin, serializers.ModelSerializer):
    passports = serializers.SerializerMethodField()

    class Meta:
        model = Country
        fields = ('id', 'name', 'code', 'passports')

    def get_passports(self, obj):
        passports = obj.passports.filter(quantity__gt=0)
        return PassportSerializer(passports, many=True).data
