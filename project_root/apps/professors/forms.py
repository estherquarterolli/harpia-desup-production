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
            'unidade_principal',
            'materia',
            'cursos',
            'status',
            'limite_horas_extra',
        ]
        widgets = {
            'id_funcional': forms.TextInput(attrs={'class': _INPUT_CSS, 'placeholder': 'Ex: 1234567'}),
            'rh_matricula': forms.TextInput(attrs={'class': _INPUT_CSS, 'placeholder': 'Matrícula RH'}),
            'rh_nome': forms.TextInput(attrs={'class': _INPUT_CSS, 'placeholder': 'Nome completo'}),
            'tipo_contrato': forms.Select(attrs={'class': _SELECT_CSS}),
            'unidade_principal': forms.Select(attrs={
                'class': _SELECT_CSS,
                'hx-get': '/professores/htmx/cursos-unidade/',
                'hx-target': '#cursos-container',
                'hx-swap': 'innerHTML'
            }),
            'materia': forms.Select(attrs={'class': _SELECT_CSS}),
            'cursos': forms.CheckboxSelectMultiple(),
            'status': forms.Select(attrs={'class': _SELECT_CSS}),
            'limite_horas_extra': forms.NumberInput(attrs={
                'class': _INPUT_CSS,
                'placeholder': 'Ex: 20 (vazio = usa limite do contrato)',
                'min': '0',
                'step': '0.5',
            }),
        }
        labels = {
            'id_funcional': 'ID',
            'rh_matricula': 'Matrícula RH',
            'rh_nome': 'Nome',
            'tipo_contrato': 'Regime / Tipo de Contrato',
            'unidade_principal': 'Unidade',
            'materia': 'Eixo',
            'cursos': 'Cursos (Checklist)',
            'status': 'Status',
            'limite_horas_extra': 'Limite de Horas Extracurriculares',
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if self.user:
            is_gestor_unidade = (
                self.user.perfil == 'COORDENADOR_UNIDADE'
                and not self.user.is_superuser
            )
            if is_gestor_unidade:
                self.fields['unidade_principal'].widget = forms.HiddenInput()
                if self.user.unidade:
                    self.fields['unidade_principal'].initial = self.user.unidade
                self.fields['limite_horas_extra'].widget = forms.HiddenInput()
                self.fields['limite_horas_extra'].required = False

        # Configurar queryset de cursos baseado na unidade selecionada (para edição ou erro de form)
        unidade_id = None
        if 'unidade_principal' in self.data:
            try:
                unidade_id = int(self.data.get('unidade_principal'))
            except (ValueError, TypeError):
                pass
        elif self.instance.pk and self.instance.unidade_principal:
            unidade_id = self.instance.unidade_principal.id
        elif self.user and not self.user.is_superuser and self.user.perfil == 'COORDENADOR_UNIDADE':
            unidade_id = self.user.unidade.id if self.user.unidade else None

        if unidade_id:
            self.fields['cursos'].queryset = Course.objects.filter(
                course_units__unidade_id=unidade_id,
                course_units__ativo=True,
            ).order_by('nome').distinct()
        else:
            self.fields['cursos'].queryset = Course.objects.none()
