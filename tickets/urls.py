from django.urls import path, include
from rest_framework_nested import routers
from companies.views import CompanyViewSet
from .views import TicketViewSet, CommentViewSet

router = routers.DefaultRouter()
router.register(r'companies', CompanyViewSet, basename='companies')

companies_router = routers.NestedSimpleRouter(router, r'companies', lookup='company')
companies_router.register(r'tickets', TicketViewSet, basename='company-tickets')

tickets_router = routers.NestedSimpleRouter(companies_router, r'tickets', lookup='ticket')
tickets_router.register(r'comments', CommentViewSet, basename='ticket-comments')

urlpatterns = [
    path('', include(router.urls)),
    path('', include(companies_router.urls)),
    path('', include(tickets_router.urls)),
]