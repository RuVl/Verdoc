from modeltranslation.translator import translator
from modeltranslation.utils import get_translation_fields
from rest_framework import serializers

from catalog.models import Country, Product


# noinspection PyUnresolvedReferences
class TranslationFieldsMixin:
    """Mixin for serializers that have translatable fields."""

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


class ProductSerializer(TranslationFieldsMixin, serializers.ModelSerializer):
    """
    Product serializer for sending product info.

    Keeps the `quantity` key the storefront already speaks; behind it is the derived stock count,
    so the queryset has to be annotated with `with_available()`. The key is renamed in R2 together
    with the frontend.
    """

    quantity = serializers.IntegerField(source="available", read_only=True)

    class Meta:
        model = Product
        fields = (
            "id",
            "name",
            "quantity",
            "price",
            "price_currency",
        )  # price_currency - dynamic field from MoneyField


class CountrySerializer(TranslationFieldsMixin, serializers.ModelSerializer):
    """Country serializer for sending all country's products."""

    passports = serializers.SerializerMethodField()

    class Meta:
        model = Country
        fields = ("id", "name", "code", "passports")

    def get_passports(self, obj):
        products = obj.products.with_available().filter(available__gt=0)
        return ProductSerializer(products, many=True).data
