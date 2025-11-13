from django.db import models

class EventLog(models.Model):
    DIRECTION_CHOICES = [
        ('in', 'Kirish'),
        ('out', 'Chiqish'),
    ]

    event_type = models.CharField(max_length=100)
    date_time = models.DateTimeField()
    card_number = models.CharField(max_length=100, blank=True, null=True)
    name = models.CharField(max_length=200, blank=True, null=True)
    direction = models.CharField(max_length=5, choices=DIRECTION_CHOICES)
    raw_data = models.JSONField()

    def __str__(self):
        return f"{self.name} ({self.get_direction_display()}) - {self.date_time}"
