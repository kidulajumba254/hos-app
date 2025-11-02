from django.urls import path
from .views import PlanRouteView, GenerateLogPDFView

urlpatterns = [
    path("plan-route/", PlanRouteView.as_view(), name="plan-route"),
    path("generate-log-pdf/", GenerateLogPDFView.as_view(), name="generate-log-pdf"),
]
