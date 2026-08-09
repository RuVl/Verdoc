from django.urls import include, path
from rest_framework.routers import DefaultRouter

from catalog.views import CountryViewSet, ExchangeRatesView

router = DefaultRouter()
router.register(r"countries", CountryViewSet, basename="countries")

urlpatterns = [
    path("", include(router.urls)),
    path("exchange-rates/", ExchangeRatesView.as_view(), name="exchange-rates"),
]
