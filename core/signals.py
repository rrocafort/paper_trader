from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver
from .models import Portfolio

@receiver(post_save, sender=User)
def create_portfolio(sender, instance, created, **kwargs):
    if created:
        Portfolio.objects.create(User=instance)