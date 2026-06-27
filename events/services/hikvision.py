import json
import re
import os
import requests
import urllib3
from requests.auth import HTTPDigestAuth
from django.utils import timezone
from events.models import EventLog
from dateutil import parser
from datetime import datetime
from zoneinfo import ZoneInfo

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TZ = ZoneInfo("Asia/Tashkent")

def parse_and_correct_datetime(date_time_str: str, now: datetime) -> datetime:
    """
    Parses and corrects the camera datetime to Asia/Tashkent timezone.
    Handles two cases of camera misconfiguration:
    1. Camera clock is set to UTC/other timezone, but the offset is sent correctly.
       In this case, converting the timezone-aware datetime to Asia/Tashkent gives the correct time.
    2. Camera clock digits are set to Tashkent time, but the offset is incorrect (e.g. +08:00).
       In this case, replacing the timezone with Asia/Tashkent directly gives the correct time.
    We compare both results with the current server time `now`. Whichever is closer is chosen.
    """
    if not date_time_str:
        return now

    try:
        dt = parser.isoparse(date_time_str)
    except Exception:
        try:
            dt = datetime.fromisoformat(date_time_str)
        except Exception:
            return now

    # If the parsed datetime is naive (no timezone offset), force Asia/Tashkent
    if dt.tzinfo is None or dt.utcoffset() is None:
        return dt.replace(tzinfo=TZ)

    # Strategy A: Convert timezone normally (assume camera offset is correct)
    dt_aware = dt.astimezone(TZ)

    # Strategy B: Force timezone (assume clock digits are Tashkent time but offset is wrong)
    dt_forced = dt.replace(tzinfo=TZ)

    # If the timezone is already correct, dt_aware and dt_forced are identical.
    # Return it directly.
    if dt_aware == dt_forced:
        return dt_aware

    # Calculate absolute differences from the current server time (now)
    diff_aware = abs((now - dt_aware).total_seconds())
    diff_forced = abs((now - dt_forced).total_seconds())

    # Whichever is closer to current server time is chosen
    if diff_aware < diff_forced:
        return dt_aware
    else:
        return dt_forced

def handle_event(evt: dict, direction: str = "in"):
    """
    Faqat foydalanuvchi ismi yoki kartasi mavjud eventlarni ko‘rsatadi,
    mahalliy bazaga saqlaydi va Laravelga yuboradi.
    """
    ace = evt.get("AccessControllerEvent") or evt.get("accessControllerEvent") or {}
    person_id = ace.get("employeeNoString") or ace.get("verifyNo") or ace.get("cardNo") or evt.get("employeeNoString") or evt.get("cardNo")
    name = ace.get("netUser") or ace.get("name") or evt.get("name")

    # Faqat ism va karta raqami mavjud bo‘lgan eventlarni saqlaymiz
    if not name or name == "-" or not person_id or person_id == "-":
        return

    # Vaqtni parse qilish
    date_time_str = evt.get("dateTime") or evt.get("time")
    now = timezone.localtime(timezone.now()) # Hozirgi vaqtni local (Toshkent) vaqtiga o'tkazamiz
    try:
        date_time = parse_and_correct_datetime(date_time_str, now)
    except Exception as e:
        print(f"❌ Timezone correction failed: {e}")
        date_time = now
        
    # Faqat joriy kunga tegishli eventlarni qabul qilish (kechagi loglarni inkor qilish)
    if date_time.date() != now.date():
        return

    # Duplikatlarni oldini olish (svet o'chib yonganda eski ma'lumotlar qayta kelsa)
    if EventLog.objects.filter(card_number=person_id, date_time=date_time, direction=direction).exists():
        return

    # statusValue bo'yicha operatsiyani aniqlash
    status_value = ace.get("statusValue")
    try:
        status_value_int = int(status_value)
    except:
        status_value_int = 1
    operation = "Door Unlocked" if status_value_int else "Door Locked"

    print(f"🟢 {name} ({person_id}) {direction.upper()} | {operation} | ⏰ {date_time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Laravelga yuborish
    laravel_url = os.getenv("LARAVEL_URL", "https://data.jdu.uz")
    laravel_token = os.getenv("LARAVEL_TOKEN")
    endpoint = f"{laravel_url}/api/event-logs"

    payload = {
        "event_type": operation,
        "date_time": date_time.isoformat(),
        "card_number": person_id,
        "name": name,
        "direction": direction,
        "raw_data": evt
    }

    headers = {
        "Authorization": f"Bearer {laravel_token}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(endpoint, json=payload, headers=headers, timeout=10)
        if response.status_code in [200, 201]:
            # Muvaffaqiyatli yuborildi
            EventLog.objects.create(
                event_type=operation,
                date_time=date_time,
                card_number=person_id,
                name=name,
                direction=direction,
                raw_data=evt,
                is_synced=True
            )
        else:
            # Laravel xatolik qaytardi
            EventLog.objects.create(
                event_type=operation,
                date_time=date_time,
                card_number=person_id,
                name=name,
                direction=direction,
                raw_data=evt,
                is_synced=False
            )
    except Exception as e:
        # Tarmoq xatosi
        EventLog.objects.create(
            event_type=operation,
            date_time=date_time,
            card_number=person_id,
            name=name,
            direction=direction,
            raw_data=evt,
            is_synced=False
        )


def stream_events(camera_url: str, direction: str):
    """
    Hikvision alertStream dan jonli eventlarni olish.
    """
    print(f"📡 Hikvision event stream ({direction}) ishga tushdi.")
    print(f"🔌 Kamera stream ulanmoqda: {camera_url}")

    user = os.getenv("HIKVISION_USER", "admin")
    password = os.getenv("HIKVISION_PASS", "Z12345678r")

    try:
        with requests.get(camera_url, auth=HTTPDigestAuth(user, password), stream=True, verify=False, timeout=15) as r:
            r.raise_for_status()
            print(f"✅ {direction.upper()} kamera ulandi. Jonli eventlar kelyapti...\n")

            buffer = b""
            boundary = None

            for chunk in r.iter_content(chunk_size=4096):
                if not chunk:
                    continue

                buffer += chunk

                # Boundary aniqlash
                if boundary is None:
                    m = re.search(br"(\r?\n)?--([^\r\n]+)\r?\n", buffer)
                    if m:
                        boundary = b"--" + m.group(2)
                    else:
                        continue

                while True:
                    idx = buffer.find(boundary)
                    if idx == -1:
                        break

                    part_and_rest = buffer[idx + len(boundary):]

                    if part_and_rest.startswith(b"--"):
                        print(f"🔚 {direction.upper()} Stream tugadi")
                        return

                    buffer = part_and_rest
                    if buffer.startswith(b"\r\n"):
                        buffer = buffer[2:]

                    header_end = buffer.find(b"\r\n\r\n")
                    if header_end == -1:
                        break

                    headers_blob = buffer[:header_end].decode(errors="ignore")
                    body_start = header_end + 4

                    clen = None
                    for line in headers_blob.splitlines():
                        if line.lower().startswith("content-length:"):
                            try:
                                clen = int(line.split(":", 1)[1].strip())
                            except:
                                pass
                            break

                    if clen is not None:
                        if len(buffer) < body_start + clen:
                            break
                        body = buffer[body_start: body_start + clen]
                        buffer = buffer[body_start + clen:]
                    else:
                        start = buffer.find(b"{")
                        end = buffer.rfind(b"}")
                        if start == -1 or end == -1 or end <= start:
                            break
                        body = buffer[start:end + 1]
                        buffer = buffer[end + 1:]

                    try:
                        evt = json.loads(body.decode("utf-8", errors="ignore"))
                        handle_event(evt, direction)
                    except Exception as e:
                        print(f"❌ Parse error: {e}")

    except KeyboardInterrupt:
        print(f"🛑 {direction.upper()} Stream foydalanuvchi tomonidan to‘xtatildi.")
    except Exception as e:
        print(f"🚫 {direction.upper()} Kamera bilan aloqa xatosi: {e}")
