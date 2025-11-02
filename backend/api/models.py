from django.db import models


class Driver(models.Model):
    name = models.CharField(max_length=100)
    license_number = models.CharField(max_length=50)
    hours_worked = models.FloatField(default=0)
    home_terminal = models.CharField(max_length=200, blank=True, null=True)
    carrier_name = models.CharField(max_length=200, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Vehicle(models.Model):
    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, related_name='vehicles')
    truck_number = models.CharField(max_length=50)
    trailer_number = models.CharField(max_length=50, blank=True, null=True)
    license_plate = models.CharField(max_length=20)
    state = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"{self.truck_number} ({self.license_plate})"


class Trip(models.Model):
    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, related_name='trips')
    origin = models.CharField(max_length=200)
    destination = models.CharField(max_length=200)
    start_date = models.DateField()
    total_miles = models.FloatField(default=0)
    total_days = models.IntegerField(default=1)
    fuel_stops = models.IntegerField(default=0)
    route_data = models.JSONField(blank=True, null=True)  
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.origin} → {self.destination} ({self.driver.name})"


class DailyLog(models.Model):
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='daily_logs')
    date = models.DateField()
    total_driving_hours = models.FloatField(default=0)
    total_on_duty_hours = models.FloatField(default=0)
    total_off_duty_hours = models.FloatField(default=0)
    total_sleeper_hours = models.FloatField(default=0)
    fuel_stops = models.IntegerField(default=0)
    remarks = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.trip.driver.name} - {self.date}"

class Activity(models.Model):
    STATUS_CHOICES = [
        ('OFF_DUTY', 'Off Duty'),
        ('SLEEPER', 'Sleeper Berth'),
        ('DRIVING', 'Driving'),
        ('ON_DUTY', 'On Duty (Not Driving)'),
    ]

    daily_log = models.ForeignKey(DailyLog, on_delete=models.CASCADE, related_name='activities')
    start_time = models.TimeField()
    end_time = models.TimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    location = models.CharField(max_length=200, blank=True, null=True)
    note = models.CharField(max_length=300, blank=True, null=True)

    def __str__(self):
        return f"{self.status} from {self.start_time} to {self.end_time}"

class Stop(models.Model):
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='stops')
    stop_type = models.CharField(
        max_length=20,
        choices=[('FUEL', 'Fuel Stop'), ('BREAK', 'Break'), ('PICKUP', 'Pickup'), ('DROPOFF', 'Drop-off')]
    )
    latitude = models.FloatField()
    longitude = models.FloatField()
    timestamp = models.DateTimeField()
    note = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.stop_type} @ ({self.latitude:.2f}, {self.longitude:.2f})"
