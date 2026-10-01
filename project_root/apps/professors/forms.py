from django import forms
from .models import Professor
from apps.courses.models import Course


_INPUT_CSS = 'w-full px-3 py-2.5 border border-slate-200 rounded-lg text-sm focus:border-[#1e4e8c] outline-none transition bg-white'
_SELECT_CSS = 'w-full px-3 py-2.5 border border-slate-200 rounded-lg text-sm bg-slate-50 focus:bg-white focus:border-[#1e4e8c] outline-none transition'


class ProfessorForm(forms.ModelForm):
    class Meta:
        model = Professor
        fields = [
            'id_funcional',
            'rh_matricula',
            'rh_nome',
            'tipo_contrato',
            'unidades',
            'cursos',
            'status',
        ]
        widgets = {
            'id_funcional': forms.TextInput(attrs={'class': _INPUT_CSS, 'placeholder': 'Ex: 1234567'}),
            'rh_matricula': forms.TextInput(attrs={'class': _INPUT_CSS, 'placeholder': 'Matrícula RH'}),
            'rh_nome': forms.TextInput(attrs={'class': _INPUT_CSS, 'placeholder': 'Nome completo'}),
            'tipo_contrato': forms.Select(attrs={'class': _SELECT_CSS}),
            'unidades': forms.CheckboxSelectMultiple(attrs={
                'hx-get': '/professores/htmx/cursos-unidade/',
                'hx-target': '#cursos-container',
                'hx-swap': 'innerHTML',
                'hx-trigger': 'change',
                'hx-include': '[name="unidades"],[name="cursos"]',
            }),
            'cursos': forms.CheckboxSelectMultiple(),
            'status': forms.Select(attrs={'class': _SELECT_CSS}),
        }
        labels = {
            'id_funcional': 'ID',
            'rh_matricula': 'Matrícula RH',
            'rh_nome': 'Nome',
            'tipo_contrato': 'Regime / Tipo de Contrato',
            'unidades': 'Unidades',
            'cursos': 'Cursos (Checklist)',
            'status': 'Status',
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        is_gestor_unidade = False
        if self.user:
            is_gestor_unidade = (
                self.user.perfil == 'COORDENADOR_UNIDADE'
                and not self.user.is_superuser
            )
            if is_gestor_unidade:
                # O coordenador pode consultar todos os docentes, mas não altera os
                # vínculos institucionais definidos pela DESUP.
                self.fields['unidades'].disabled = True

        unidades_iniciais = list(self.instance.unidades.values_list('pk', flat=True)) if self.instance.pk else []
        if not unidades_iniciais and self.instance.pk and self.instance.unidade_principal_id:
            unidades_iniciais = [self.instance.unidade_principal_id]
        if unidades_iniciais:
            self.fields['unidades'].initial = unidades_iniciais

        # Cursos oferecidos em qualquer uma das unidades selecionadas.
        unidade_ids = []
        if is_gestor_unidade:
            unidade_ids = unidades_iniciais
        elif 'unidades' in self.data:
            unidade_ids = [int(pk) for pk in self.data.getlist('unidades') if str(pk).isdigit()]
        else:
            unidade_ids = unidades_iniciais

        if unidade_ids:
            self.fields['cursos'].queryset = Course.objects.filter(
                course_units__unidade_id__in=unidade_ids,
                course_units__ativo=True,
            ).order_by('nome').distinct()
        else:
            self.fields['cursos'].queryset = Course.objects.none()

    def save(self, commit=True):
        professor = super().save(commit=False)
        unidades = self.cleaned_data.get('unidades')
        # Compatibilidade temporária com módulos e relatórios legados que ainda
        # consultam a unidade principal: usa a primeira unidade selecionada.
        professor.unidade_principal = unidades.order_by('nome').first() if unidades else None
        if commit:
            professor.save()
            self.save_m2m()
        return professor
