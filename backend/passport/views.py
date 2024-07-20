from django.db.models import Count, Q
from django.utils import translation
from djmoney.contrib.exchange.models import Rate
from rest_framework import viewsets, views
from rest_framework.response import Response

from passport.models import Country
from passport.serializers import CountrySerializer


class CountryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CountrySerializer

    def get_queryset(self):
        return Country.objects.annotate(
            num_passports=Count('passports', filter=Q(passports__quantity__gt=0))
        ).filter(num_passports__gt=0)

    def list(self, request, *args, **kwargs):
        language = request.GET.get('lang')
        translation.activate(language)
        response = super().list(request, *args, **kwargs)
        translation.deactivate()
        return response


class ExchangeRatesView(views.APIView):
    def get(self, request):

        rates = {rate.currency: rate.value for rate in Rate.objects.all()}
        return Response(rates)

