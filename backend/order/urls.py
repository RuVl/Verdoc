from django.urls import path

from .views import OrderCreateView, PlisioCallbackView, DownloadLinksView, SendDownloadLinksView

urlpatterns = [
    path('order/', OrderCreateView.as_view(), name='order-create'),
    path('order/status', PlisioCallbackView.as_view(), name='plisio-callback'),  # be aware that path does not end with a slash
    path('send-links/', SendDownloadLinksView.as_view(), name='send-links'),
    path('order/file/<str:email>/<str:uuid>/', DownloadLinksView.as_view(), name='download-file')
]
