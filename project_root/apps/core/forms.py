from django import forms
from .models import JanelaEntrega

class JanelaEntregaForm(forms.ModelForm):
    class Meta:
        model = JanelaEntrega
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter choices to remove REABERTO
        self.fields['status'].choices = [
            (choice[0], choice[1])
            for choice in JanelaEntrega.StatusChoices.choices
            if choice[0] != JanelaEntrega.StatusChoices.REABERTO
        ]
        # Se o status atual for REABERTO, exibe como ABERTO no seletor
        if self.instance and self.instance.status == JanelaEntrega.StatusChoices.REABERTO:
            self.initial['status'] = JanelaEntrega.StatusChoices.ABERTO

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Ao editar a janela de entrega o status ficará automaticamente como "Reaberto",
        # ao colocar a opção "Aberto" no seletor na edição da janela de entrega, a ideia é reutilizar a lógica do "Reaberto"
        if self.instance.pk and instance.status == JanelaEntrega.StatusChoices.ABERTO:
            instance.status = JanelaEntrega.StatusChoices.REABERTO
        
        if commit:
            instance.save()
        return instance
