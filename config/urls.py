from django.contrib.auth import views as auth_views
from django.urls import path

from accounts import views as access
from audit import views as audit
from core import views as core
from inventory import views as inventory
from masters import views as masters
from purchasing import views as purchasing

urlpatterns = [
    path("healthz", core.healthz, name="healthz"),
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", inventory.stock_overview, name="stock-overview"),
    path("inwards/", inventory.inward_list, name="inward-list"),
    path("inwards/new/<slug:stock_mode>/", inventory.inward_new, name="inward-new"),
    path("inwards/<int:pk>/", inventory.inward_detail, name="inward-detail"),
    path("inwards/<int:pk>/edit/", inventory.inward_edit, name="inward-edit"),
    path("inwards/<int:pk>/receive/", inventory.inward_confirm, name="inward-confirm"),
    path("supplier-invoices/", purchasing.invoice_list, name="invoice-list"),
    path("supplier-invoices/new/", purchasing.invoice_new, name="invoice-new"),
    path("supplier-invoices/<int:pk>/", purchasing.invoice_detail, name="invoice-detail"),
    path("supplier-invoices/lines/<int:line_pk>/link/", purchasing.match_pick, name="invoice-match"),
    path("supplier-invoices/links/<int:match_pk>/remove/", purchasing.match_remove, name="invoice-match-remove"),
    path("masters/", masters.masters_index, name="masters-index"),
    path("masters/<slug:slug>/", masters.master_list, name="master-list"),
    path("masters/<slug:slug>/new/", masters.master_edit, name="master-new"),
    path("masters/<slug:slug>/<int:pk>/", masters.master_edit, name="master-edit"),
    path("history/", audit.audit_list, name="audit-list"),
    path("access/", access.access_index, name="access-index"),
    path("access/roles/new/", access.role_edit, name="role-new"),
    path("access/roles/<int:pk>/", access.role_edit, name="role-edit"),
    path("access/users/new/", access.user_edit, name="user-new"),
    path("access/users/<int:pk>/", access.user_edit, name="user-edit"),
]
