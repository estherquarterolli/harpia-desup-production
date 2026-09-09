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
                # CORR: esconder o widget NÃO protege o campo — o valor do POST continuava
                # sendo aceito e o coordenador conseguia empurrar o docente para outra
                # unidade. Com `disabled=True` o Django ignora o que vier no POST e usa
                # sempre o valor inicial (o da instância na edição), fechando a escrita
                # cruzada.
                self.fields['unidade_principal'].widget = forms.HiddenInput()
                self.fields['unidade_principal'].disabled = True
                if self.user.unidade:
                    self.fields['unidade_principal'].initial = self.user.unidade

        # Configurar queryset de cursos baseado na unidade selecionada (para edição ou erro de form)
        unidade_id = None
        if is_gestor_unidade:
            # Mesmo motivo do `disabled` acima: para o gestor de unidade a unidade nunca
            # vem do POST. Se viesse, um `unidade_principal` adulterado liberaria os cursos
            # da outra unidade na checklist e o vínculo cruzado entraria pelos `cursos`.
            if self.instance.pk and self.instance.unidade_principal_id:
                unidade_id = self.instance.unidade_principal_id
            elif self.user.unidade:
                unidade_id = self.user.unidade.id
        elif 'unidade_principal' in self.data:
            try:
                unidade_id = int(self.data.get('unidade_principal'))
            except (ValueError, TypeError):
                pass
        elif self.instance.pk and self.instance.unidade_principal:
            unidade_id = self.instance.unidade_principal.id

        if unidade_id:
            self.fields['cursos'].queryset = Course.objects.filter(
                course_units__unidade_id=unidade_id,
                course_units__ativo=True,
            ).order_by('nome').distinct()
        else:
            self.fields['cursos'].queryset = Course.objects.none()
