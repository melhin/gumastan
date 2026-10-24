from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health_check, name="health_check"),
    path("extract/<str:task>/", views.extract, name="extract"),
    path("status/<int:job_id>/", views.job_status, name="job_status"),
]
