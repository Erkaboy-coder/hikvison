import json
from datetime import datetime, timedelta
from unittest.mock import patch
from django.test import TestCase, Client
from django.utils import timezone
from django.urls import reverse
from rest_framework import status
from .models import EventLog

class WeeklyActivityViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse('weekly-activity')
        
        # O'tgan 45 kundagi event
        self.old_event = EventLog.objects.create(
            event_type="Door Unlocked",
            date_time=timezone.now() - timedelta(days=45),
            card_number="CARD001",
            name="Eski Talaba",
            direction="in",
            raw_data={}
        )
        
        # Bugungi eventlar
        tz = timezone.get_current_timezone()
        now = datetime.now(tz)
        
        # 09:15 dagi event
        self.time_event = EventLog.objects.create(
            event_type="Door Unlocked",
            date_time=now.replace(hour=9, minute=15, second=0, microsecond=0),
            card_number="CARD002",
            name="Kobil Egamberdiyev",
            direction="in",
            raw_data={}
        )

    def test_default_one_month_limit(self):
        # Parametrsiz chaqirilganda faqat 30 kunlik loglarni qaytarishi kerak (old_event tushishi kerak)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        logs = list(response.context['logs'].object_list)
        self.assertNotIn(self.old_event, logs)
        self.assertIn(self.time_event, logs)

    def test_filter_date_bypasses_one_month_limit(self):
        # Maxsus sana kiritilganda 1 oylik cheklov chetlab o'tilishi kerak
        filter_date_str = (timezone.now() - timedelta(days=45)).strftime("%Y-%m-%d")
        response = self.client.get(self.url, {'filter_date': filter_date_str})
        self.assertEqual(response.status_code, 200)
        logs = list(response.context['logs'].object_list)
        self.assertIn(self.old_event, logs)

    def test_time_filtering_logic(self):
        # start_time = "08:30" va end_time = "10:00" kiritilganda, 09:15 dagi event chiqishi kerak
        # Eski noto'g'ri kodda bu event filtrlangan bo'lardi (chunki 15 < 30)
        response = self.client.get(self.url, {
            'start_time': '08:30',
            'end_time': '10:00'
        })
        self.assertEqual(response.status_code, 200)
        logs = list(response.context['logs'].object_list)
        self.assertIn(self.time_event, logs)


class DoorEventAPIViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse('door-event')

    def test_unauthorized_ip_rejected(self):
        # Ruxsat berilmagan IP dan so'rovlar rad etilishi kerak
        response = self.client.post(self.url, data={'event_log': '{}'}, REMOTE_ADDR="192.168.1.100")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Faqat live IP dan qabul qilinadi", response.data['message'])

    @patch('requests.post')
    def test_successful_sync_saves_locally(self, mock_post):
        # Laravelga muvaffaqiyatli yuborilganda, local bazaga is_synced=True bilan saqlanishi kerak
        mock_post.return_value.status_code = 201
        
        event_payload = {
            "AccessControllerEvent": {
                "employeeNoString": "CARD999",
                "name": "Sinov Foydalanuvchi",
                "statusValue": 1
            },
            "dateTime": timezone.now().isoformat()
        }
        
        response = self.client.post(
            self.url,
            data=json.dumps({"event_log": json.dumps(event_payload)}),
            content_type="application/json",
            REMOTE_ADDR="127.0.0.1"
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(EventLog.objects.filter(card_number="CARD999", name="Sinov Foydalanuvchi", is_synced=True).exists())

    @patch('requests.post')
    def test_failed_sync_saves_locally(self, mock_post):
        # Laravelga yuborishda xatolik bo'lsa, local bazaga is_synced=False bo'lib saqlanishi kerak
        mock_post.return_value.status_code = 500
        
        event_payload = {
            "AccessControllerEvent": {
                "employeeNoString": "CARD888",
                "name": "Xato Foydalanuvchi",
                "statusValue": 1
            },
            "dateTime": timezone.now().isoformat()
        }
        
        response = self.client.post(
            self.url,
            data=json.dumps({"event_log": json.dumps(event_payload)}),
            content_type="application/json",
            REMOTE_ADDR="127.0.0.1"
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(EventLog.objects.filter(card_number="CARD888", name="Xato Foydalanuvchi", is_synced=False).exists())

    @patch('requests.post')
    def test_case_sensitivity_camelcase_key(self, mock_post):
        # accessControllerEvent (kichik harflar bilan) kelganda ham to'g'ri ishlashi kerak
        mock_post.return_value.status_code = 201
        
        event_payload = {
            "accessControllerEvent": {
                "employeeNoString": "CARD777",
                "name": "CamelCase Foydalanuvchi",
                "statusValue": 1
            },
            "dateTime": timezone.now().isoformat()
        }
        
        response = self.client.post(
            self.url,
            data=json.dumps({"event_log": json.dumps(event_payload)}),
            content_type="application/json",
            REMOTE_ADDR="127.0.0.1"
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(EventLog.objects.filter(card_number="CARD777", name="CamelCase Foydalanuvchi").exists())
