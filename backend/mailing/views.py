from django import views
from django.core import signing
from django.shortcuts import render

from .models import Unsubscribe
from .services import read_unsubscribe_token


class UnsubscribeView(views.View):
    """Public one-click unsubscribe landing page."""

    def get(self, request, token: str):
        try:
            email = read_unsubscribe_token(token)
        except signing.BadSignature:
            return render(request, "mailing/unsubscribe.html", {"error": True}, status=400)

        Unsubscribe.objects.get_or_create(email=email)
        return render(request, "mailing/unsubscribe.html", {"email": email})
