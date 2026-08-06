import logging

from django.core import signing
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from customer.models import Customer

from .services import read_unsubscribe_token

logger = logging.getLogger(__name__)


class UnsubscribeView(APIView):
    """
    Opt a customer out of broadcasts, by the signed token from the e-mail footer.

    POST rather than GET on purpose: link scanners at Gmail and Outlook pre-fetch every URL in a
    message, and on GET that would opt people out without them ever clicking. The page behind
    `/unsubscribe/:token` calls this once it is actually open in a browser.
    """

    def post(self, request, token: str, *args, **kwargs):
        try:
            email = read_unsubscribe_token(token)
        except signing.BadSignature:
            return Response({"detail": "This unsubscribe link is not valid."}, status=status.HTTP_400_BAD_REQUEST)

        customer = Customer.objects.filter(email=email).first()
        if customer is None:
            # The token is ours, so the address is genuine - it just has no row anymore. Nothing to
            # do, and nothing worth telling apart from success.
            logger.info(f"Unsubscribe for an unknown address {email}")
            return Response({"email": email}, status=status.HTTP_200_OK)

        customer.unsubscribe()

        return Response({"email": customer.email}, status=status.HTTP_200_OK)
