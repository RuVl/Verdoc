from django.urls import path, include
from rest_framework.routers import DefaultRouter

from passport.views import CountryViewSet, ExchangeRatesView

router = DefaultRouter()
router.register(r'countries', CountryViewSet, basename='countries')

urlpatterns = [
    path('', include(router.urls)),
    path('exchange-rates/', ExchangeRatesView.as_view(), name='exchange-rates'),
]
