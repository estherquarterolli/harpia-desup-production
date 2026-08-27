import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

class ComplexPasswordValidator:
    def validate(self, password, user=None):
        if not re.search(r'[A-Z]', password):
            raise ValidationError(
                _("A senha deve conter pelo menos uma letra maiúscula."),
                code='password_no_upper',
            )
        if not re.search(r'[0-9]', password):
            raise ValidationError(
                _("A senha deve conter pelo menos um número."),
                code='password_no_digit',
            )
        if not re.search(r'[^a-zA-Z0-9]', password):
            raise ValidationError(
                _("A senha deve conter pelo menos um caractere especial (ex: @, #, $, %, etc.)."),
                code='password_no_special',
            )

    def get_help_text(self):
        return _(
            "Sua senha deve conter pelo menos uma letra maiúscula, um número e um caractere especial."
        )
