# fayl: events/services/hikvision.py (eng pastga qo‘shing)
from events.models import EventLog
from django.utils import timezone
import pytz

def is_inside(card_number: str):
    """
    Talaba hozir ichkaridami yoki yo‘qmi — aniqlaydi.
    """
    tashkent_tz = pytz.timezone("Asia/Tashkent")
    today = timezone.now().astimezone(tashkent_tz).date()

    last_event = (
        EventLog.objects.filter(card_number=card_number, date_time__date=today)
        .order_by("-date_time")
        .first()
    )

    if not last_event:
        return None  # bugungi event yo‘q

    if last_event.direction == "in":
        return True  # hozir ichkarida
    elif last_event.direction == "out":
        return False
    return None
