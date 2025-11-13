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
    """
    Hikvision POST API (Kirish va Chiqish)
    - Faqat live terminal eventlarini qabul qiladi
    - Eski yoki kelajakdagi eventlarni tashlaydi (>2 daqiqa)
    - Bazaga yozadi faqat person_id va name mavjud bo‘lsa
    """

    def post(self, request):
        if request.META.get('REMOTE_ADDR') not in LIVE_IPS:
            return Response({"message": "⚠️ Faqat live IP dan qabul qilinadi"}, status=status.HTTP_200_OK)

        event_log_str = request.POST.get('event_log')
        if not event_log_str:
            return Response({"message": "❌ event_log maydoni topilmadi"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            data = json.loads(event_log_str)
        except json.JSONDecodeError:
            return Response({"message": "❌ JSON parse xatolik"}, status=status.HTTP_400_BAD_REQUEST)

        ace = data.get("AccessControllerEvent", {})
        person_id = ace.get("employeeNoString") or ace.get("verifyNo") or ace.get("cardNo")
        name = ace.get("netUser") or ace.get("name") or "Noma'lum"
        status_value = ace.get("statusValue")
        date_time_str = data.get("dateTime")

        # 🔹 DEBUG log
        print(f"DEBUG: person_id={person_id}, name={name}, status_value={status_value}, type={type(status_value)}")

        # Agar event foydalanuvchi IDsi bo'lmasa, yozmaymiz
        if not person_id:
            return Response({"message": "⚠️ Bazaga yozilmadi, person_id mavjud emas"}, status=status.HTTP_200_OK)

        # Hozirgi vaqt
        now = datetime.now(TZ)

        # date_time ni aniqlash
        if date_time_str:
            try:
                date_time = parser.isoparse(date_time_str)
                if date_time.tzinfo is None:
                    date_time = TZ.localize(date_time)
                date_time = date_time.astimezone(TZ)
            except Exception as e:
                print(f"WARNING: date_time parse xatolik: {e}")
                date_time = now
        else:
            date_time = now

        # ⏳ Eski yoki kelajakdagi eventni cheklash (2 daqiqa)
        if abs((now - date_time).total_seconds()) > 120:
            return Response({"message": "⏳ Eski yoki kelajakdagi event e'tiborsiz qoldirildi"}, status=status.HTTP_200_OK)

        # 🔹 status_value ni int ga o'tkazish va fallback
        try:
            status_value_int = int(status_value)
        except Exception:
            status_value_int = 1  # default Kirish

        # Operatsiya va direction aniqlash
        if status_value_int == 0:
            operation = "Door Locked"
            direction = "out"   # Chiqish
        else:
            operation = "Door Unlocked"
            direction = "in"    # Kirish

        # Bazaga yozish
        EventLog.objects.create(
            event_type=operation,
            date_time=date_time,
            card_number=person_id,
            name=name,
            direction=direction,
            raw_data=data
        )

        return Response({
            "message": "✅ Event qabul qilindi va bazaga yozildi",
            "person_id": person_id,
            "name": name,
            "operation": operation,
            "direction": "Kirish" if direction == "in" else "Chiqish",
            "date_time": date_time.isoformat()
        }, status=status.HTTP_200_OK)


