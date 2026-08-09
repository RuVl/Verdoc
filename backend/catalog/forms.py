import pycountry
from django import forms

from catalog.models import Country


def get_country_choices():
    """Build choices list from pycountry (ISO alpha_2 -> flag + name)."""
    choices = [("-", "-")]
    for country in sorted(pycountry.countries, key=lambda x: x.name):
        if hasattr(country, "alpha_2"):
            flag = Country.code2flag(country.alpha_2)
            # noinspection PyUnresolvedReferences
            label = f"{flag} {country.name}"
            choices.append((country.alpha_2.lower(), label))
    return choices


class CountryForm(forms.ModelForm):
    code = forms.ChoiceField(
        choices=get_country_choices(),
        label="Flag / Country",
    )

    class Meta:
        model = Country
        fields = "__all__"
