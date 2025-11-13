import json
import re
import requests
import urllib3
from requests.auth import HTTPDigestAuth
from django.utils import timezone
from events.models import EventLog

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Hikvision konfiguratsiyasi
URL = "http://10.234.0.8/ISAPI/Event/notification/alertStream"
USER = "admin"
PASS = "Z12345678r"

def handle_event(evt: dict):
    """
    Faqat foydalanuvchi ismi yoki kartasi mavjud eventlarni ko‘rsatadi.
    """
    etype = evt.get("eventType", "")
    ace = evt.get("AccessControllerEvent") or evt.get("accessControllerEvent") or {}
    desc = evt.get("eventDescription", "")
    name = ace.get("name", "-")
    card = ace.get("cardNo") or ace.get("employeeNoString") or "-"

    # 🔹 Faqat ism yoki karta raqami mavjud bo‘lgan eventlarni chiqaramiz
    if not name or name == "-" or not card or card == "-":
        return  # foydasiz eventlarni tashlaymiz

    now = timezone.localtime(timezone.now())
    print(f"🟢 {name} ({card}) IN | {desc} | ⏰ {now.strftime('%Y-%m-%d %H:%M:%S')}")



def stream_events():
    """
    Hikvision alertStream dan jonli eventlarni olish.
    """
    print("📡 Hikvision event stream ishga tushdi. To‘xtatish uchun Ctrl+C bosing.")
    print(f"🔌 Kamera stream ulanmoqda: {URL}")

    try:
        with requests.get(URL, auth=HTTPDigestAuth(USER, PASS), stream=True, verify=False, timeout=10) as r:
            r.raise_for_status()
            print("✅ IN kamera ulandi. Jonli eventlar kelyapti...\n")

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
                        print("🔚 Stream tugadi")
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
                        handle_event(evt)
                    except Exception as e:
                        print(f"❌ Parse error: {e}")

    except KeyboardInterrupt:
        print("🛑 Stream foydalanuvchi tomonidan to‘xtatildi.")
    except Exception as e:
        print(f"🚫 Kamera bilan aloqa xatosi: {e}")
