import requests
from requests.auth import HTTPDigestAuth
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from django.core.management.base import BaseCommand
from events.models import EventLog
from events.services.hikvision import parse_and_correct_datetime

class Command(BaseCommand):
    help = 'Kameradan tushib qolgan loglarni to\'g\'ridan-to\'g\'ri tortib olish'

    def add_arguments(self, parser):
        parser.add_argument('--ip', type=str, default='10.234.0.8', help='Kamera IP manzili')
        parser.add_argument('--direction', type=str, default='in', help='in yoki out')

    def handle(self, *args, **options):
        ip = options['ip']
        direction = options['direction']
        
        tz = ZoneInfo("Asia/Tashkent")
        now = datetime.now(tz)
        
        # Bugungi kun boshlanishi va oxiri
        start_time = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        end_time = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        
        payload = {
            "AcsEventCond": {
                "searchID": "1",
                "searchResultPosition": 0,
                "maxResults": 1000,
                "major": 5,
                "minor": 75,
                "startTime": start_time,
                "endTime": end_time
            }
        }
        
        url = f"http://{ip}/ISAPI/AccessControl/AcsEvent?format=json"
        
        try:
            r = requests.post(url, auth=HTTPDigestAuth('admin', 'Z12345678r'), json=payload, timeout=15)
            if r.status_code != 200:
                self.stderr.write(f"Xatolik: Kamera {r.status_code} qaytardi.")
                return
                
            data = r.json()
            events = data.get("AcsEvent", {}).get("InfoList", [])
            
            if not events:
                self.stdout.write("Hech qanday ma'lumot topilmadi.")
                return
                
            self.stdout.write(f"{len(events)} ta event topildi. Bazaga yozilmoqda...")
            
            added = 0
            
            for evt in events:
                person_id = evt.get("employeeNoString")
                if not person_id:
                    continue
                    
                name = evt.get("name", "Noma'lum")
                time_str = evt.get("time")
                
                dt = parse_and_correct_datetime(time_str, now)
                
                # Faqat joriy kunga tegishli eventlarni qabul qilish (kechagi loglarni inkor qilish)
                if dt.date() != now.date():
                    continue
                    
                # Bazada bormi yo'qmi tekshiramiz
                if not EventLog.objects.filter(card_number=person_id, date_time=dt).exists():
                    EventLog.objects.create(
                        event_type="Door Unlocked",
                        date_time=dt,
                        card_number=person_id,
                        name=name,
                        direction=direction,
                        raw_data=evt,
                        is_synced=False # Bu muhim, sync_to_laravel orqali jo'natiladi
                    )
                    added += 1
            
            self.stdout.write(self.style.SUCCESS(f"Bajarildi! {added} ta yangi log saqlandi."))
            self.stdout.write("Endi 'python manage.py sync_to_laravel' komandasini ishlating!")
            
        except Exception as e:
            self.stderr.write(f"Xatolik yuz berdi: {e}")
