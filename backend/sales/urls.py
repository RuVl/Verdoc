from django.urls import path

from .views import (
    DownloadFileView,
    OrderCreateView,
    PlisioCallbackView,
    PurchasesView,
    RefreshAllAllocationsView,
    RefreshAllocationView,
    SendDownloadLinksView,
)

urlpatterns = [
    path("order/", OrderCreateView.as_view(), name="order-create"),
    # No trailing slash: this is the URL registered with Plisio, and it is not ours to change.
    path("order/status", PlisioCallbackView.as_view(), name="plisio-callback"),
    path("send-links/", SendDownloadLinksView.as_view(), name="send-links"),
    path("files/<uuid:uuid>/", DownloadFileView.as_view(), name="download-file"),
    # Purchases page. The token in the path is the whole authentication, see ADR-0004.
    path("purchases/<uuid:token>/", PurchasesView.as_view(), name="purchases"),
    path(
        "purchases/<uuid:token>/refresh/<int:allocation_id>/",
        RefreshAllocationView.as_view(),
        name="purchases-refresh",
    ),
    path(
        "purchases/<uuid:token>/refresh-all/",
        RefreshAllAllocationsView.as_view(),
        name="purchases-refresh-all",
    ),
]
