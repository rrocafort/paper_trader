from django.contrib import admin
from .models import Portfolio, Trade, Holding

# Admin Site - Registration
admin.site.register(Portfolio)
admin.site.register(Trade)
admin.site.register(Holding)