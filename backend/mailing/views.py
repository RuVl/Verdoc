import logging

from django.core import signing
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from customer.models import Customer

from .services import read_unsubscribe_token

logger = logging.getLogger(__name__)

INVALID_TOKEN = "This unsubscribe link is not valid."


class UnsubscribeView(APIView):
    """
    The unsubscribe link from the e-mail footer, split across the two methods.

    GET only reads the token and says whose address it is, so the page can ask before doing
    anything. POST is what actually opts the customer out.

    The split is not decoration. Link scanners at Gmail and Outlook pre-fetch every URL in a
    message, so opting out on GET would unsubscribe people who never clicked - and a customer who
    opens the link out of curiosity should not lose the mailing list on the spot either.
    """

    def resolve(self, token: str) -> tuple[str, Customer | None] | None:
        """Return the address the token was signed for and its Customer row, if there is one."""
        try:
            email = read_unsubscribe_token(token)
        except signing.BadSignature:
            return None

        return email, Customer.objects.filter(email=email).first()

    def get(self, request, token: str, *args, **kwargs):
        resolved = self.resolve(token)
        if resolved is None:
            return Response({"detail": INVALID_TOKEN}, status=status.HTTP_400_BAD_REQUEST)

        email, customer = resolved

        # No row means nothing left to unsubscribe; the page treats it as already done.
        return Response(
            {"email": email, "is_subscribed": customer.is_subscribed if customer else False},
            status=status.HTTP_200_OK,
        )

    def post(self, request, token: str, *args, **kwargs):
        resolved = self.resolve(token)
        if resolved is None:
            return Response({"detail": INVALID_TOKEN}, status=status.HTTP_400_BAD_REQUEST)

        email, customer = resolved
        if customer is None:
            # The token is ours, so the address is genuine - it just has no row anymore. Nothing to
            # do, and nothing worth telling apart from success.
            logger.info(f"Unsubscribe for an unknown address {email}")
            return Response({"email": email, "is_subscribed": False}, status=status.HTTP_200_OK)

        customer.unsubscribe()

        return Response({"email": customer.email, "is_subscribed": False}, status=status.HTTP_200_OK)
