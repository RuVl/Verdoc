import logging

from django.utils import translation
from djmoney.contrib.exchange.models import Rate
from rest_framework import viewsets, views
from rest_framework.response import Response

from passport.models import Country
from passport.serializers import CountrySerializer

logger = logging.getLogger(__name__)


class CountryViewSet(viewsets.ReadOnlyModelViewSet):
	""" Send all countries with nested passports """

	serializer_class = CountrySerializer

	def get_queryset(self):
		return Country.objects.filter(passports__quantity__gt=0).distinct()

	def list(self, request, *args, **kwargs):
		lang = request.GET.get('lang')
		with translation.override(lang):
			response = super().list(request, *args, **kwargs)
		return response


class ExchangeRatesView(views.APIView):
	""" Send exchange rates """

	def get(self, request):
		rates = {rate.currency: rate.value for rate in Rate.objects.all()}
		return Response(rates)
