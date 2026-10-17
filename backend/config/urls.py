from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from bank import views

urlpatterns = [
    path('api/health/', views.Health.as_view()),
    path('api/auth/register/', views.Register.as_view()),
    path('api/auth/login/', views.Login.as_view()),
    path('api/auth/logout/', views.Logout.as_view()),
    path('api/bank/', views.Bank.as_view()),
    path('api/accounts/', views.Accounts.as_view()),
    path('api/topup/', views.TopUp.as_view()),
    path('api/transfers/', views.Transfers.as_view()),
    path('api/deposits/', views.Deposits.as_view()),
    path('api/deposits/topup/', views.DepositTopUp.as_view()),
    path('api/deposits/close/', views.DepositClose.as_view()),
    path('api/history/', views.History.as_view()),
    path('api/schema/', SpectacularAPIView.as_view(permission_classes=[], authentication_classes=[]), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema', permission_classes=[], authentication_classes=[])),
]
