from django.urls import path

from .views import (
    DownloadFileView,
    LegacyDownloadLinksView,
    OrderCreateView,
    PlisioCallbackView,
    PurchasesView,
    RefreshAllAllocationsView,
    RefreshAllocationView,
    SendDownloadLinksView,
)

urlpatterns = [
    path("order/", OrderCreateView.as_view(), name="order-create"),
    path("order/status", PlisioCallbackView.as_view(), name="plisio-callback"),
    # be aware that path does not end with a slash
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
    # Pre-R2 link, still in customers' inboxes. Drops out one release after R2.
    path(
        "order/file/<str:email>/<str:uuid>/",
        LegacyDownloadLinksView.as_view(),
        name="download-file-legacy",
    ),
]
