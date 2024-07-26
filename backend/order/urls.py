from django.urls import path

from .views import OrderCreateView, PlisioCallbackView, DownloadLinksView

urlpatterns = [
    path('order/', OrderCreateView.as_view(), name='order-create'),
    path('order/status/', PlisioCallbackView.as_view(), name='plisio-callback'),
    path('order/file/<str:email>/<str:uuid>/', DownloadLinksView.as_view(), name='download-file')
]
