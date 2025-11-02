from django.test import TestCase
from datetime import datetime, timedelta, timezone
from .hos_utils import plan_day_schedule

class HosUtilsTests(TestCase):
    def test_short_trip(self):
        start = datetime.now(timezone.utc).replace(hour=6, minute=0, second=0, microsecond=0)
        result = plan_day_schedule(start, total_drive_minutes=120, cycle_hours_used=0.0)
        self.assertTrue(len(result["activities"]) >= 3) 
