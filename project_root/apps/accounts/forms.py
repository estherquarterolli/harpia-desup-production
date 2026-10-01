import secrets

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


class DesupUserCreateForm(forms.ModelForm):
    """Criação operacional segura: DESUP ou coordenador, nunca superusuário."""

    perfil = forms.ChoiceField(
        label="Tipo de usuário",
        choices=(
            (User.Perfil.DESUP, "Administrador DESUP"),
            (User.Perfil.COORDENADOR_UNIDADE, "Coordenador de Unidade"),
        ),
    )

    class Meta:
        model = User
        fields = ("first_name", "email", "perfil", "unidade")
        labels = {
            "first_name": "Nome",
            "email": "E-mail",
            "unidade": "Unidade",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        field_css = (
            "w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm "
            "outline-none focus:border-[#025c9f] focus:ring-2 focus:ring-blue-100"
        )
        for field in self.fields.values():
            field.widget.attrs["class"] = field_css
        self.fields["first_name"].required = True
        self.fields["first_name"].widget.attrs.update({
            "autocomplete": "name",
            "placeholder": "Nome do usuário",
        })
        self.fields["email"].widget.attrs.update({
            "autocomplete": "email",
            "placeholder": "usuario@exemplo.com",
        })
        self.fields["unidade"].required = False
        self.fields["unidade"].empty_label = "Selecione a unidade"
        self.fields["unidade"].queryset = self.fields["unidade"].queryset.filter(
            status=True
        ).order_by("nome")

    def clean_email(self):
        email = User.objects.normalize_email(self.cleaned_data["email"]).lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Já existe um usuário com este e-mail.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        perfil = cleaned_data.get("perfil")
        unidade = cleaned_data.get("unidade")
        if perfil == User.Perfil.COORDENADOR_UNIDADE and not unidade:
            self.add_error("unidade", "Selecione a unidade do coordenador.")
        elif perfil == User.Perfil.DESUP:
            cleaned_data["unidade"] = None
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        # A senha aleatória não é exibida nem enviada. O usuário recebe um link
        # individual para definir a própria senha antes do primeiro acesso.
        user.set_password(secrets.token_urlsafe(48))
        user.is_active = True
        user.is_staff = False
        user.is_superuser = False
        user.forcar_troca_senha = True
        if commit:
            user.save()
        return user
