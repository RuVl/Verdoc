import logging

from django.utils import translation
from djmoney.contrib.exchange.models import Rate
from rest_framework import views, viewsets
from rest_framework.response import Response

from catalog.models import Country, Product
from catalog.serializers import CountrySerializer

logger = logging.getLogger(__name__)


class CountryViewSet(viewsets.ReadOnlyModelViewSet):
    """Send all countries with nested products"""

    serializer_class = CountrySerializer

    def get_queryset(self):
        in_stock = Product.objects.with_available().filter(available__gt=0).values("pk")
        return Country.objects.filter(products__pk__in=in_stock).distinct()

    def list(self, request, *args, **kwargs):
        lang = request.GET.get("lang")
        with translation.override(lang):
            response = super().list(request, *args, **kwargs)
        return response


class ExchangeRatesView(views.APIView):
    """Send exchange rates"""

    def get(self, request):
        rates = {rate.currency: rate.value for rate in Rate.objects.all()}
        return Response(rates)
