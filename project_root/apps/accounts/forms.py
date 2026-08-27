from django import forms

from .models import DEFAULT_USER_PASSWORD, User


class CustomUserCreationForm(forms.ModelForm):
    """
    Form used in the admin to create users with the default system password.
    """

    class Meta:
        model = User
        fields = ("email", "perfil", "unidade", "forcar_troca_senha")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(DEFAULT_USER_PASSWORD)
        if commit:
            user.save()
        return user


class CustomUserChangeForm(forms.ModelForm):
    """
    Form used in the admin to update users.
    """

    class Meta:
        model = User
        fields = (
            "email",
            "perfil",
            "unidade",
            "is_active",
            "is_staff",
            "is_superuser",
            "forcar_troca_senha",
        )
