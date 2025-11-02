from rest_framework import serializers

class RoutePlanRequestSerializer(serializers.Serializer):
    start_iso = serializers.DateTimeField()
    current_location = serializers.DictField()  # {lat, lng}
    pickup_location = serializers.DictField()
    dropoff_location = serializers.DictField()
    estimated_drive_minutes = serializers.IntegerField()
    distance_miles = serializers.FloatField(required=False)
    cycle_hours_used = serializers.FloatField(default=0.0)
    allow_restart = serializers.BooleanField(default=False)
    fuel_interval_miles = serializers.IntegerField(default=1000)
    route_polyline = serializers.CharField(required=False, allow_blank=True)
