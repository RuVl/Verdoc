from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import PassportFile


@receiver(post_save, sender=PassportFile, dispatch_uid='passport_file_save')
@receiver(post_delete, sender=PassportFile, dispatch_uid='passport_file_delete')
def update_passport_quantity(sender, instance, **kwargs):
    passport = instance.passport
    passport.quantity = passport.files.count()
    passport.save()
