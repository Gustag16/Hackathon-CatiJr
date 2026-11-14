from django.urls import path

from . import views

urlpatterns = [
    path("config", views.config, name="config"),
    path("auctions", views.auctions, name="auctions"),
    path("auctions/<str:auction_id>", views.auction_detail_view, name="auction-detail"),
]
