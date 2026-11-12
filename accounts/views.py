"""Users and roles. Grants are data and every change is recorded."""

from django import forms
from django.contrib import messages
from django.contrib.auth.password_validation import validate_password
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from audit import services as audit
from core.web import capability_required, forbidden

from .models import Capability, Role, User

CAPABILITY = "access.manage"


class RoleForm(forms.ModelForm):
    capabilities = forms.ModelMultipleChoiceField(
        queryset=Capability.objects.all(), required=False, widget=forms.CheckboxSelectMultiple
    )

    class Meta:
        model = Role
        fields = ["name", "description", "is_demo", "capabilities"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["capabilities"].label_from_instance = lambda cap: f"{cap.key}: {cap.description}"


class UserForm(forms.ModelForm):
    roles = forms.ModelMultipleChoiceField(
        queryset=Role.objects.all(), required=False, widget=forms.CheckboxSelectMultiple
    )
    new_password = forms.CharField(
        label="Password", required=False, widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="At least 10 characters. Leave empty to keep the current password.",
    )

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "is_active", "roles"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk is None:
            self.fields["new_password"].required = True
            self.fields["new_password"].help_text = "At least 10 characters."

    def clean_new_password(self):
        password = self.cleaned_data.get("new_password")
        if password:
            validate_password(password, self.instance)
        return password


def access_index(request):
    return render(
        request,
        "access/index.html",
        {
            "roles": Role.objects.prefetch_related("capabilities"),
            "users": User.objects.prefetch_related("roles").order_by("username"),
            "capabilities": Capability.objects.all(),
        },
    )


def _role_state(role: Role) -> dict:
    return {
        "name": role.name,
        "description": role.description,
        "is_demo": role.is_demo,
        "capabilities": sorted(role.capabilities.values_list("key", flat=True)),
    }


@capability_required(CAPABILITY)
@require_http_methods(["GET", "POST"])
def role_edit(request, pk: int | None = None):
    role = get_object_or_404(Role, pk=pk) if pk else None
    before = _role_state(role) if role else None
    form = RoleForm(request.POST or None, instance=role)
    if request.method == "POST" and form.is_valid():
        if not request.user.has_capability(CAPABILITY):
            return forbidden(request, CAPABILITY)
        saved = form.save()
        audit.record(
            actor=request.user,
            action="role.update" if role else "role.create",
            capability=CAPABILITY,
            target=saved,
            payload={"before": before, "after": _role_state(saved)},
        )
        messages.success(request, f"Role {saved} saved. The change applies to the very next action.")
        return redirect("access-index")
    return render(
        request, "access/role_form.html", {"form": form, "role": role},
        status=422 if request.method == "POST" else 200,
    )


def _user_state(user: User) -> dict:
    return {
        "username": user.username,
        "name": user.get_full_name(),
        "is_active": user.is_active,
        "roles": sorted(user.roles.values_list("name", flat=True)),
    }


@capability_required(CAPABILITY)
@require_http_methods(["GET", "POST"])
def user_edit(request, pk: int | None = None):
    user = get_object_or_404(User, pk=pk) if pk else None
    before = _user_state(user) if user else None
    form = UserForm(request.POST or None, instance=user)
    if request.method == "POST" and form.is_valid():
        if not request.user.has_capability(CAPABILITY):
            return forbidden(request, CAPABILITY)
        saved = form.save(commit=False)
        password = form.cleaned_data.get("new_password")
        if password:
            saved.set_password(password)
        saved.save()
        form.save_m2m()
        audit.record(
            actor=request.user,
            action="user.update" if user else "user.create",
            capability=CAPABILITY,
            target=saved,
            payload={"before": before, "after": _user_state(saved), "password_changed": bool(password)},
        )
        messages.success(request, f"User {saved.username} saved.")
        return redirect("access-index")
    return render(
        request, "access/user_form.html", {"form": form, "edited_user": user},
        status=422 if request.method == "POST" else 200,
    )
