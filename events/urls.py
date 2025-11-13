from django.urls import path
from .views import EventLogListAPIView, WeeklyActivityView, DoorEventAPIView

urlpatterns = [
    path('events/', EventLogListAPIView.as_view(), name='event-list'),
    path('weekly-activity/', WeeklyActivityView.as_view(), name='weekly-activity'),
    path('door-event/', DoorEventAPIView.as_view(), name='door-event'),  # Yagona endpoint
]
