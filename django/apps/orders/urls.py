from django.conf.urls import url
from orders import views


urlpatterns = [
    url(r"^place$", views.PlaceOrderView.as_view(), name="place"),
    url(r"^commit$", views.CommitOrderView.as_view(), name="commit"),
    url('^(?P<page>\d+)$', views.UserOrdersView.as_view(), name="info"),
    url('^comment/(?P<order_id>\d+)$', views.CommentView.as_view(), name="comment"),
    url('^pay$', views.PayView.as_view(), name="pay"),
    url('^check_pay$', views.CheckPayStatusView.as_view(), name="check_pay"),
]