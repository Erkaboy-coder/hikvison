import time
import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from urllib.parse import urlparse
from django.core.management.base import BaseCommand
from django.conf import settings
from requests.auth import HTTPDigestAuth
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ⏱ So'rov yuborish oralig'i (sekundlarda)
INTERVAL = 10

# 🧠 Oxirgi event vaqtlari (har bir kamera uchun alohida)
last_event_times = {}


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


def fetch_logs(camera_url: str, direction: str):
    """
    Kameradan bugungi eventlarni olib keladi
    """
    global last_event_times

    parsed_url = urlparse(camera_url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    log_search_url = f"{base_url}/ISAPI/ContentMgmt/logSearch"

    user = os.getenv("HIKVISION_USER", "admin")
    password = os.getenv("HIKVISION_PASS", "Z12345678r")

    today = datetime.now()
    start_time = today.replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:%S+05:00")
    end_time = (today + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:%S+05:00")

    body = build_xml_body(start_time, end_time)

    try:
        response = requests.post(
            log_search_url,
            data=body,
            auth=HTTPDigestAuth(user, password),
            headers={"Content-Type": "application/xml"},
            verify=False,
            timeout=10,
        )
        if response.status_code != 200:
            print(f"⚠️ [{direction.upper()}] HTTP {response.status_code}: {response.text[:100]}")
            return

        events = parse_events(response.text)
        events.sort(key=lambda e: e["dateTime"])

        last_time = last_event_times.get(camera_url)

        for evt in events:
            evt_time = evt["dateTime"]
            if not evt_time:
                continue

            # ⏩ Eski eventlarni tashlaymiz
            if last_time and evt_time <= last_time:
                continue

            name = evt.get("name") or "-"
            card = evt.get("cardNo") or "-"
            desc = evt.get("desc") or evt.get("subEvent") or evt.get("eventType") or "-"
            print(f"🟢 [{direction.upper()}] {name} ({card}) | {desc} | ⏰ {evt_time}")

            last_time = evt_time

        last_event_times[camera_url] = last_time

    except Exception as e:
        print(f"❌ [{direction.upper()}] So‘rovda xatolik: {e}")


class Command(BaseCommand):
    help = "Hikvision log polling — bugungi Access Control eventlarni kuzatadi (barcha kameralar uchun)."

    def handle(self, *args, **options):
        self.stdout.write("Hikvision log polling o'chirilgan (Disabled).")
        return
        
        cameras = getattr(settings, "CAMERAS", [])
        if not cameras:
            self.stdout.write(self.style.ERROR("❌ settings.CAMERAS ro'yxati bo'sh!"))
            return

        while True:
            for cam in cameras:
                url = cam.get("url")
                direction = cam.get("direction", "in")
                if not url:
                    continue
                fetch_logs(url, direction)
            time.sleep(INTERVAL)
