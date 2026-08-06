from django.urls import path

from .views import UnsubscribeView

urlpatterns = [
    path("unsubscribe/<str:token>/", UnsubscribeView.as_view(), name="unsubscribe"),
]
