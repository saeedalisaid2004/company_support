from django.urls import path
from .views import CompanyReportsView

urlpatterns = [
    path('companies/<int:company_pk>/tickets/reports/', CompanyReportsView.as_view(), name='company-reports'),
]