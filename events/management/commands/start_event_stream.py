import threading
import time
from django.core.management.base import BaseCommand
from django.conf import settings
from events.services.hikvision import stream_events

class Command(BaseCommand):
    help = "Hikvision alertStream dan jonli eventlarni o‘qish (barcha kameralar uchun parallel)"

    def handle(self, *args, **options):
        threads = []
        cameras = getattr(settings, "CAMERAS", [])
        
        if not cameras:
            self.stdout.write(self.style.ERROR("❌ settings.CAMERAS ro'yxati bo'sh!"))
            return

        self.stdout.write("📡 Barcha kameralardan alertStream boshlanmoqda...")

        for cam in cameras:
            url = cam.get("url")
            direction = cam.get("direction", "in")
            if not url:
                self.stdout.write(self.style.WARNING(f"⚠️ {direction} kamerasining URL manzili sozlanmagan, tashlab ketildi."))
                continue

            t = threading.Thread(
                target=stream_events,
                args=(url, direction),
                name=f"stream-{direction}",
                daemon=True
            )
            t.start()
            threads.append(t)
            self.stdout.write(f"🚀 {direction.upper()} kamera oqimi ishga tushirildi: {url}")

        try:
            # Asosiy oqimni ushlab turish
            while True:
                alive_threads = [t for t in threads if t.is_alive()]
                if not alive_threads:
                    self.stdout.write(self.style.WARNING("🛑 Barcha oqimlar to'xtadi."))
                    break
                time.sleep(1)
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("🛑 Foydalanuvchi tomonidan to‘xtatildi."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Xatolik: {e}"))
