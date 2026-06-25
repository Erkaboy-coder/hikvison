import os
from django.core.management.base import BaseCommand
import requests
from events.models import EventLog
from django.conf import settings
import logging

logger = logging.getLogger('hikvision')

class Command(BaseCommand):
    help = 'Unsynced loglarni Laravel loyihasiga yuborish'

    def handle(self, *args, **kwargs):
        self.stdout.write("Laravelga loglarni sinxronlash o'chirilgan (Disabled).")
        return

        unsynced_events = EventLog.objects.filter(is_synced=False).order_by('date_time')
        
        count = unsynced_events.count()
        if count == 0:
            self.stdout.write(self.style.SUCCESS("Barcha loglar allaqachon Laravel bilan sinxronlangan."))
            return

        self.stdout.write(f"{count} ta sinxronlanmagan log topildi. Yuborilmoqda...")

        success_count = 0
        error_count = 0

        headers = {
            "Authorization": f"Bearer {laravel_token}",
            "Content-Type": "application/json"
        }

        for event in unsynced_events:
            payload = {
                "event_type": event.event_type,
                "date_time": event.date_time.isoformat(),
                "card_number": event.card_number,
                "name": event.name,
                "direction": event.direction,
                "raw_data": event.raw_data if isinstance(event.raw_data, dict) else {"raw": str(event.raw_data)}
            }

            try:
                response = requests.post(endpoint, json=payload, headers=headers, timeout=10)
                
                # Laravel 200 yoki 201 qaytaradi deb hisoblaymiz
                if response.status_code in [200, 201]:
                    event.is_synced = True
                    event.save(update_fields=['is_synced'])
                    success_count += 1
                else:
                    self.stderr.write(self.style.WARNING(f"Xatolik (ID: {event.id}): HTTP {response.status_code} - {response.text}"))
                    error_count += 1
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Tarmoq xatosi (ID: {event.id}): {e}"))
                error_count += 1

        self.stdout.write(self.style.SUCCESS(f"Tugallandi! {success_count} yuborildi, {error_count} xatolik."))
