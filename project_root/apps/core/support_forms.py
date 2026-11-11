from django import forms
from django.core.exceptions import ValidationError

from .forms import _INPUT_CSS


TIPOS_SUPORTE = (
    ('DUVIDA', 'Dúvida sobre utilização do sistema'),
    ('ERRO', 'Erro ou falha no funcionamento'),
    ('DADOS', 'Inconsistência nos dados'),
    ('SUGESTAO', 'Sugestão de melhoria'),
    ('OUTROS', 'Outros'),
)


class SuporteForm(forms.Form):
    tipo = forms.ChoiceField(label='Tipo de solicitação', choices=(('', 'Selecione o tipo'),) + TIPOS_SUPORTE)
    assunto = forms.CharField(label='Assunto', max_length=150)
    descricao = forms.CharField(
        label='Descrição', max_length=5000,
        widget=forms.Textarea(attrs={'rows': 7}),
        help_text='Até 5.000 caracteres. Descreva o que aconteceu e como reproduzir o problema.',
    )
    contexto = forms.CharField(max_length=1500, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if not field.widget.is_hidden:
                field.widget.attrs.update({'class': _INPUT_CSS, 'aria-describedby': f'{name}-ajuda {name}-erros'})

    def clean_assunto(self):
        assunto = self.cleaned_data['assunto']
        if any(ord(char) < 32 or ord(char) == 127 for char in assunto):
            raise ValidationError('O assunto deve ter apenas uma linha, sem caracteres de controle.')
        return assunto
