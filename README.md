# Weekly Attendance & Hikvision Integration

📅 Ushbu loyiha **xodimlar kirish-chiqishini nazorat qilish** va **Hikvision DS-K1T671M** terminallari orqali real-time eventlarni qabul qilish uchun Django asosida yaratilgan.  

## 📌 Asosiy xususiyatlar

- Xodimlar kirish/chiqish eventlarini **bazaga yozish** va ularni **weekly activity** ko‘rinishida ko‘rsatish.  
- Hikvision terminallari bilan **API integratsiyasi** (`DoorEventAPIView`).  
- Eventlar faqat **live terminal IPlar** dan qabul qilinadi.  
- Eski yoki kelajakdagi eventlar (>2 daqiqa) **e'tiborsiz qoldiriladi**.  
- Weekly activity jadvali va **pagination**.  
- Kirish/chiqish statuslari uchun **ikonalar** ishlatilgan (`🏢`, `🚪`).  
- Oldingi va keyingi sahifalarga **navigator**.  

## ⚙️ Texnologiyalar

- Python 3.12+  
- Django 5.x  
- Django REST Framework  
- PostgreSQL (yoki boshqa SQL)  
- Bootstrap 5.3 (frontend)  
- pytz, python-dateutil  

## 🚀 O‘rnatish

1. Loyiha klonlash:

```bash
git clone <repository_url>
cd <project_folder>
