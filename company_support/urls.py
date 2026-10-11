from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    
    path('api-auth/', include('rest_framework.urls')),
    
    path('api/users/', include('users.urls')),
    path('api/companies/', include('companies.urls')),
    path('api/tickets/', include('tickets.urls')),
    path('api/reports/', include('reports.urls')),
]