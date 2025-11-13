from django.contrib import admin
from .models import EventLog

@admin.register(EventLog)
class EventLogAdmin(admin.ModelAdmin):
    list_display = ("name", "card_number", "event_type", "direction", "date_time")
    list_filter = ("direction", "event_type")
    search_fields = ("name", "card_number")
