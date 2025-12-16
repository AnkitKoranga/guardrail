from django.urls import path
from .views import GenerateView, StatusView

urlpatterns = [
    path('generate/', GenerateView.as_view(), name='generate'),
    path('status/<uuid:request_id>/', StatusView.as_view(), name='status'),
]
