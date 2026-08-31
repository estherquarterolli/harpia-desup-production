# pyrefly: ignore [missing-import]
from django import forms
from django.forms import inlineformset_factory

from .models import ClassGroup, Course, CourseUnit, CurriculumMatrix, MatrixComponent, CurricularComponent
from apps.core.models import Unidade


# ── Classe base de widget para campo de texto/select padrão ──────────────────
_FIELD_CSS = 'form-field'        # definido em dashboard.css
_TEXTAREA_CSS = 'form-field compact'

# ── Opções de Período/Semestre ───────────────────────────────────────────────
PERIODO_COMPONENTE_CHOICES = [('', 'Selecione')] + [(f"{i}º Semestre", f"{i}º Semestre") for i in range(1, 9)]


class CurriculumMatrixForm(forms.ModelForm):
    duplicar_de = forms.ModelChoiceField(
        queryset=CurriculumMatrix.objects.select_related('curso').order_by('curso__nome', 'nome'),
        required=False,
        empty_label="Não duplicar (criar em branco)",
        label="Duplicar a partir de outra Matriz",
        widget=forms.Select(attrs={'class': _FIELD_CSS})
    )

    class Meta:
        model = CurriculumMatrix
        fields = ['curso', 'unidades', 'nome']
        widgets = {
            'curso': forms.Select(attrs={'class': _FIELD_CSS}),
            'unidades': forms.CheckboxSelectMultiple(),
            'nome': forms.TextInput(attrs={
                'class': _FIELD_CSS,
                'placeholder': 'Ex: MC-ADS-2026',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['nome'].label = "Código da Matriz"
        self.fields['curso'].queryset = Course.objects.all().order_by('nome')
        self.fields['curso'].required = False
        self.fields['unidades'].queryset = Unidade.objects.filter(status=True).order_by('nome')
        self.fields['unidades'].required = False


class MatrixComponentForm(forms.ModelForm):
    class Meta:
        model = MatrixComponent
        fields = [
            'componente_curricular',
            'periodo',
            'codigo',
            'carga_horaria',
            'creditos',
            'carga_horaria_semanal',
            'docente',
            'compartilhado',
            'curso_compartilhado',
            'status',
            'observacoes',
        ]
        widgets = {
            'componente_curricular': forms.Select(attrs={
                'class': _FIELD_CSS,
            }),
            'codigo': forms.TextInput(attrs={'class': _FIELD_CSS}),
            'periodo': forms.Select(
                choices=PERIODO_COMPONENTE_CHOICES,
                attrs={'class': _FIELD_CSS}
            ),
            'carga_horaria': forms.NumberInput(attrs={
                'class': _FIELD_CSS,
                'min': 0,
            }),
            'creditos': forms.NumberInput(attrs={
                'class': _FIELD_CSS,
                'min': 0,
            }),
            'carga_horaria_semanal': forms.NumberInput(attrs={
                'class': _FIELD_CSS,
                'step': '0.5',
                'min': 0,
            }),
            'docente': forms.HiddenInput(),
            'compartilhado': forms.CheckboxInput(attrs={'class': 'rounded text-[#1e4e8c]'}),
            'curso_compartilhado': forms.Select(attrs={'class': _FIELD_CSS}),
            'status': forms.HiddenInput(),
            'observacoes': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['codigo'].required = False
        self.fields['carga_horaria'].required = False
        self.fields['creditos'].required = False
        self.fields['carga_horaria_semanal'].required = False
        self.fields['componente_curricular'].queryset = CurricularComponent.objects.all().order_by('nome')
        # CORR-007: na matriz, o usuário só escolhe a **Disciplina** e o **Período**.
        # Todo o resto ('Código', 'CH Total', 'Créditos', 'CH Sem.') deriva da
        # disciplina e NÃO pode ser alterado pela DESUP — só via Django admin
        # (super admin/dev). disabled=True bloqueia a edição na UI e faz o Django
        # ignorar qualquer valor vindo no POST (à prova de adulteração); o valor
        # correto é recalculado no clean() a partir da disciplina.
        self.fields['codigo'].disabled = True
        self.fields['carga_horaria'].disabled = True
        self.fields['creditos'].disabled = True
        self.fields['carga_horaria_semanal'].disabled = True

    def clean(self):
        cleaned_data = super().clean()
        cc = cleaned_data.get('componente_curricular')
        if cc is not None:
            # Código sempre espelha o da disciplina selecionada.
            cleaned_data['codigo'] = cc.codigo or ''
            # CH Total: como o campo é `disabled`, o valor nunca vem do POST — só do
            # instance ou da disciplina. Preservar o gravado só faz sentido enquanto a
            # linha continua na MESMA disciplina (matriz legada pode ter CH diferente
            # do padrão, e isso é legítimo). Trocando a disciplina, o valor herdado é
            # o da disciplina ANTIGA: aí a CH tem de ser re-derivada do padrão da nova,
            # senão a linha fica com o código de uma e a carga horária de outra.
            ch = cleaned_data.get('carga_horaria')
            trocou_disciplina = self.instance.componente_curricular_id != cc.pk
            if ch is None or trocou_disciplina:
                ch = cc.carga_horaria_padrao
            cleaned_data['carga_horaria'] = ch
            if ch is None:
                # `MatrixComponent.carga_horaria` é NOT NULL sem default: sem este
                # guard o save estouraria com IntegrityError sem explicar a causa.
                # Só acontece com disciplina de dados inconsistentes no banco.
                raise forms.ValidationError(
                    'A disciplina selecionada está sem carga horária padrão. '
                    'Cadastre a carga horária da disciplina antes de usá-la na matriz.'
                )
            # Créditos e CH semanal derivam da CH total, mesma regra de
            # CurricularComponentForm.clean() e de MatrixComponent.save().
            cleaned_data['creditos'] = ch // 20
            cleaned_data['carga_horaria_semanal'] = round(ch / 20, 2)
        return cleaned_data


MatrixComponentFormSet = inlineformset_factory(
    CurriculumMatrix,
    MatrixComponent,
    form=MatrixComponentForm,
    fields=MatrixComponentForm.Meta.fields,
    extra=3,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


class ClassGroupForm(forms.ModelForm):
    class Meta:
        model = ClassGroup
        fields = ['matriz_curricular', 'matriz_componente', 'ano_semestre', 'identificador']
        widgets = {
            'matriz_curricular': forms.Select(attrs={'class': _FIELD_CSS}),
            'matriz_componente': forms.Select(attrs={'class': _FIELD_CSS}),
            'ano_semestre': forms.TextInput(attrs={
                'class': _FIELD_CSS,
                'placeholder': 'Ex: 2024.1',
            }),
            'identificador': forms.TextInput(attrs={
                'class': _FIELD_CSS,
                'placeholder': 'Ex: T01',
            }),
        }


class CurricularComponentForm(forms.ModelForm):
    """Form para criação/edição de Componente Curricular pela DESUP."""

    class Meta:
        model = CurricularComponent
        fields = ['nome', 'codigo', 'carga_horaria_padrao', 'creditos', 'obrigatoria', 'pre_requisitos', 'ementa']
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': _FIELD_CSS,
                'placeholder': 'Ex: Programação Orientada a Objetos',
            }),
            'codigo': forms.TextInput(attrs={
                'class': _FIELD_CSS,
                'placeholder': 'Ex: INF0001 (opcional)',
            }),
            'carga_horaria_padrao': forms.NumberInput(attrs={
                'class': _FIELD_CSS,
                'min': 1,
            }),
            'creditos': forms.NumberInput(attrs={
                'class': _FIELD_CSS,
                'min': 0,
                'readonly': 'readonly',
            }),
            'obrigatoria': forms.CheckboxInput(attrs={'class': 'rounded text-[#1e4e8c]'}),
            'pre_requisitos': forms.SelectMultiple(attrs={'class': 'hidden', 'id': 'id_pre_requisitos'}),
            'ementa': forms.Textarea(attrs={
                'class': _FIELD_CSS + ' compact',
                'rows': 4,
                'placeholder': 'Descrição das competências e conteúdos do componente...',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # prefetch_related (mesmo sem uso) evita que o ModelChoiceIterator
        # use QuerySet.iterator() com cursor nomeado do Postgres, que quebra
        # atrás do pooler do Supabase.
        qs = CurricularComponent.objects.all().order_by('nome').prefetch_related('pre_requisitos')
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        self.fields['pre_requisitos'].queryset = qs
        self.fields['pre_requisitos'].required = False

    def clean_carga_horaria_padrao(self):
        ch = self.cleaned_data.get('carga_horaria_padrao')
        if ch is None or ch < 1:
            raise forms.ValidationError('A carga horária deve ser de pelo menos 1 hora.')
        return ch

    def clean(self):
        cleaned_data = super().clean()
        ch = cleaned_data.get('carga_horaria_padrao')
        if ch:
            cleaned_data['creditos'] = ch // 20
        return cleaned_data
