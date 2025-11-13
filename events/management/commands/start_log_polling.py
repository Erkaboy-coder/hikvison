import time
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from requests.auth import HTTPDigestAuth
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 🔧 Kamera ma'lumotlari
URL = "http://10.234.0.8/ISAPI/ContentMgmt/logSearch"
USER = "admin"
PASS = "Z12345678r"

# ⏱ So'rov yuborish oralig'i (sekundlarda)
INTERVAL = 10

# 🧠 Oxirgi event vaqti (faqat yangi eventlar chiqadi)
last_event_time = None


def build_xml_body(start_time: str, end_time: str) -> str:
    """
    Hikvision logSearch uchun XML so‘rov (ver10 + FaceRecognition)
    """
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<CMSearchDescription version="1.0" xmlns="http://www.hikvision.com/ver10/XMLSchema">
  <searchID>1</searchID>
  <trackIDList>
    <trackID>101</trackID>
  </trackIDList>
  <timeSpanList>
    <timeSpan>
      <startTime>{start_time}</startTime>
      <endTime>{end_time}</endTime>
    </timeSpan>
  </timeSpanList>
  <maxResults>40</maxResults>
  <searchResultPosition>0</searchResultPosition>
  <metadataList>
    <metadataDescriptor>//recordType.meta.std-cgi.com/LogInfo/FaceRecognition</metadataDescriptor>
  </metadataList>
</CMSearchDescription>"""




def parse_events(xml_data: str):
    """
    XML javobdan eventlarni ajratadi
    """
    events = []
    try:
        root = ET.fromstring(xml_data)
        ns = {"ns": "http://www.hikvision.com/ver10/XMLSchema"}

        for item in root.findall(".//ns:searchMatchItem", ns):
            event = {
                "dateTime": item.findtext(".//ns:dateTime", default="", namespaces=ns),
                "eventType": item.findtext(".//ns:majorEventType", default="", namespaces=ns),
                "subEvent": item.findtext(".//ns:minorEventType", default="", namespaces=ns),
                "name": item.findtext(".//ns:name", default="", namespaces=ns),
                "cardNo": item.findtext(".//ns:cardNo", default="", namespaces=ns),
                "desc": item.findtext(".//ns:description", default="", namespaces=ns),
            }
            events.append(event)
    except Exception as e:
        print(f"❌ XML parse xatosi: {e}")
    return events


def fetch_logs():
    """
    Bugungi eventlarni olib keladi
    """
    global last_event_time

    today = datetime.now()
    start_time = today.replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:%S+05:00")
    end_time = (today + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:%S+05:00")

    body = build_xml_body(start_time, end_time)

    try:
        response = requests.post(
            URL,
            data=body,
            auth=HTTPDigestAuth(USER, PASS),
            headers={"Content-Type": "application/xml"},
            verify=False,
            timeout=10,
        )
        if response.status_code != 200:
            print(f"⚠️ HTTP {response.status_code}: {response.text[:100]}")
            return

        events = parse_events(response.text)
        events.sort(key=lambda e: e["dateTime"])

        for evt in events:
            evt_time = evt["dateTime"]
            if not evt_time:
                continue

            # ⏩ Eski eventlarni tashlaymiz
            if last_event_time and evt_time <= last_event_time:
                continue

            name = evt.get("name") or "-"
            card = evt.get("cardNo") or "-"
            desc = evt.get("desc") or evt.get("subEvent") or evt.get("eventType") or "-"
            print(f"🟢 {name} ({card}) | {desc} | ⏰ {evt_time}")

            last_event_time = evt_time

    except Exception as e:
        print(f"❌ So‘rovda xatolik: {e}")


class Command(BaseCommand):
    help = "Hikvision log polling — bugungi Access Control eventlarni kuzatadi."

    def handle(self, *args, **options):
        print("📡 Hikvision log polling ishga tushdi. To‘xtatish uchun Ctrl+C bosing.\n")
        while True:
            fetch_logs()
            time.sleep(INTERVAL)
