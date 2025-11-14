from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import render
from django.utils import timezone
from datetime import datetime, timedelta
import pytz, json
from dateutil import parser
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .models import EventLog
from .serializers import EventLogSerializer
import logging
logger = logging.getLogger("hikvision")

LIVE_IPS = ["10.234.0.9"]  # Faqat live terminal IPsi
TZ = pytz.timezone("Asia/Tashkent")


class WeeklyActivityView(APIView):
    def get(self, request):
        card_number = request.GET.get("card_number")

        now = timezone.now()
        one_month_ago = now - timedelta(days=30)  # faqat oxirgi 1 oy

        # Oxirgi 1 oy loglarini olish
        logs = EventLog.objects.filter(date_time__gte=one_month_ago).order_by('-date_time')
        if card_number:
            logs = logs.filter(card_number=card_number)

        # Paginator (har sahifada 10 ta log)
        page = request.GET.get('page', 1)
        paginator = Paginator(logs, 10)
        try:
            logs_page = paginator.page(page)
        except PageNotAnInteger:
            logs_page = paginator.page(1)
        except EmptyPage:
            logs_page = paginator.page(paginator.num_pages)

        # Sahifa raqamlarini tayyorlash
        current = logs_page.number
        total = paginator.num_pages
        page_numbers = []

        if total <= 10:
            page_numbers = list(range(1, total + 1))
        else:
            if current > 4:
                page_numbers.extend([1, 2, 3, '...'])
                start = current - 2
            else:
                start = 1
            if current < total - 3:
                end = current + 2
            else:
                end = total
            page_numbers.extend(range(start, end + 1))
            if end < total:
                page_numbers.append('...')
                page_numbers.append(total)

        # Oxirgi holat
        last_log = logs.first()
        status_str = "🚪 Tashqarida"
        if last_log:
            if last_log.direction == "in":
                status_str = f"🏢 Binoda ({last_log.event_type})"
            elif last_log.direction == "out":
                status_str = f"🚪 Tashqarida ({last_log.event_type})"

        context = {
            "card_number": card_number,
            "logs": logs_page,
            "status": status_str,
            "has_data": logs.exists(),
            "page_numbers": page_numbers,
        }

        return render(request, "weekly_activity.html", context)


# ---------------------- EventLogListAPIView ----------------------
class EventLogListAPIView(generics.ListCreateAPIView):
    """
    Barcha EventLoglarni ko‘rsatish va yaratish
    """
    queryset = EventLog.objects.all().order_by('-date_time')
    serializer_class = EventLogSerializer


# ---------------------- DoorEventAPIView ----------------------
class DoorEventAPIView(APIView):

    def post(self, request):
        client_ip = request.META.get('REMOTE_ADDR')

        logger.info(f"📥 NEW REQUEST: IP={client_ip}, DATA={request.POST.dict()}")

        if client_ip not in LIVE_IPS:
            logger.warning(f"❌ Ruxsat berilmagan IP urindi: {client_ip}")
            return Response({"message": "⚠️ Faqat live IP dan qabul qilinadi"}, status=status.HTTP_200_OK)

        event_log_str = request.POST.get('event_log')
        if not event_log_str:
            logger.error("❌ event_log maydoni topilmadi")
            return Response({"message": "❌ event_log maydoni topilmadi"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            data = json.loads(event_log_str)
            logger.info(f"📦 JSON qabul qilindi: {data}")
        except json.JSONDecodeError as e:
            logger.exception("❌ JSON decode error")
            return Response({"message": "❌ JSON parse xatolik"}, status=status.HTTP_400_BAD_REQUEST)

        ace = data.get("AccessControllerEvent", {})
        person_id = ace.get("employeeNoString") or ace.get("verifyNo") or ace.get("cardNo")
        name = ace.get("netUser") or ace.get("name") or "Noma'lum"
        status_value = ace.get("statusValue")
        date_time_str = data.get("dateTime")

        logger.info(f"🔍 Parsed fields: person_id={person_id}, name={name}, status_value={status_value}, date_time={date_time_str}")

        if not person_id:
            logger.warning("⚠️ person_id topilmadi, event DB ga yozilmaydi")
            return Response({"message": "⚠️ Bazaga yozilmadi, person_id mavjud emas"}, status=status.HTTP_200_OK)

        now = datetime.now(TZ)

        # TIME PARSE
        try:
            if date_time_str:
                date_time = parser.isoparse(date_time_str)
                if date_time.tzinfo is None:
                    date_time = TZ.localize(date_time)
                date_time = date_time.astimezone(TZ)
            else:
                date_time = now

            logger.info(f"🕒 Event time parsed: {date_time}")

        except Exception as e:
            logger.exception("❌ date_time parse xatolik")
            date_time = now

        # OLD or FUTURE EVENT
        diff = abs((now - date_time).total_seconds())
        if diff > 120:
            logger.warning(f"⏳ Eski yoki kelajakdagi event tashlandi. Farq={diff} sec")
            return Response({"message": "⏳ Eski yoki kelajakdagi event e'tiborsiz qoldirildi"}, status=status.HTTP_200_OK)

        # STATUS
        try:
            status_value_int = int(status_value)
            logger.info(f"status_value int ga o‘tdi: {status_value_int}")
        except:
            logger.error(f"status_value int ga o'tmadi: {status_value}")
            status_value_int = 1

        if status_value_int == 0:
            operation = "Door Locked"
            direction = "out"
        else:
            operation = "Door Unlocked"
            direction = "in"

        logger.info(f"📌 Operation={operation}, Direction={direction}")

        # DATABASE WRITE
        try:
            EventLog.objects.create(
                event_type=operation,
                date_time=date_time,
                card_number=person_id,
                name=name,
                direction=direction,
                raw_data=data
            )
            logger.info(f"💾 DB RECORD SAVED: {person_id} | {name} | {operation} | {direction}")

        except Exception as e:
            logger.exception("❌ DB yozishda xatolik")
            return Response({"message": "❌ DB yozishda xatolik"}, status=500)

        return Response({
            "message": "✅ Event qabul qilindi va bazaga yozildi",
            "person_id": person_id,
            "name": name,
            "operation": operation,
            "direction": "Kirish" if direction == "in" else "Chiqish",
            "date_time": date_time.isoformat()
        }, status=status.HTTP_200_OK)


