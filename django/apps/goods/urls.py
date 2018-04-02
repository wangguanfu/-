from django.conf.urls import url

from goods import views

urlpatterns = [
    url(r"^index$", views.IndexView.as_view(), name="index"),
    url(r"^detail/(?P<sku_id>\d+)$", views.DetailView.as_view(), name="detail"),
    url(r"^list/(?P<category_id>\d+)/(?P<page>\d+)$", views.ListView.as_view(), name="list"),
]