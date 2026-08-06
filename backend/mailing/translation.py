from modeltranslation.translator import TranslationOptions, register

from mailing.models import Broadcast


@register(Broadcast)
class BroadcastTranslationOptions(TranslationOptions):
    """
    One broadcast, written once per language.

    The alternative - a language field plus a recipient filter - means writing the same news
    twice and remembering to do it; here a missing translation just falls back.
    """

    fields = ("subject", "body")
