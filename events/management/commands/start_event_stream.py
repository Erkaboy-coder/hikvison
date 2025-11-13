from django.core.management.base import BaseCommand
from events.services.hikvision import stream_events

class Command(BaseCommand):
    help = "Hikvision alertStream dan jonli eventlarni o‘qish"

    def handle(self, *args, **options):
        try:
            stream_events()
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("🛑 Foydalanuvchi tomonidan to‘xtatildi."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Xatolik: {e}"))
