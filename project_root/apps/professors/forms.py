from decimal import Decimal

from django import forms
from django.db.models import Q
from django.utils import timezone
from .models import ContractType, Professor
from apps.courses.models import Course


_INPUT_CSS = 'w-full px-3 py-2.5 border border-slate-200 rounded-lg text-sm focus:border-[#1e4e8c] outline-none transition bg-white'
_SELECT_CSS = 'w-full px-3 py-2.5 border border-slate-200 rounded-lg text-sm bg-slate-50 focus:bg-white focus:border-[#1e4e8c] outline-none transition'

JUSTIFICATIVA_PADRAO_RAT_CADASTRO = (
    'Professor cadastrado pela DESUP já em Regime Adicional de Trabalho (RAT).'
)
JUSTIFICATIVA_PADRAO_RAT_EDICAO = (
    'RAT definido pela DESUP na edição do professor.'
)
# Campos de RAT administrados pela DESUP no cadastro e na edição.
CAMPOS_RAT = (
    'vem_com_rat', 'rat_unidade', 'rat_horas_adicionais',
    'rat_data_inicio', 'rat_data_fim', 'rat_justificativa',
)


class ProfessorForm(forms.ModelForm):
    # --- RAT administrado pela DESUP ----------------------------------------
    vem_com_rat = forms.BooleanField(
        label='Professor já vem como RAT', required=False,
        widget=forms.CheckboxInput(attrs={'class': 'w-4 h-4'}),
    )
    rat_unidade = forms.ModelChoiceField(
        label='Unidade do RAT', queryset=None, required=False,
        empty_label='Selecione a unidade',
        widget=forms.Select(attrs={'class': _SELECT_CSS}),
    )
    rat_horas_adicionais = forms.DecimalField(
        label='Horas semanais do RAT', required=False,
        max_digits=7, decimal_places=2, min_value=Decimal('0.01'),
        widget=forms.NumberInput(attrs={'class': _INPUT_CSS, 'min': '0.01', 'step': '0.01', 'placeholder': 'Ex: 4'}),
    )
    rat_data_inicio = forms.DateField(
        label='Início da vigência', required=False,
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': _INPUT_CSS}),
    )
    rat_data_fim = forms.DateField(
        label='Fim da vigência (opcional)', required=False,
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': _INPUT_CSS}),
    )
    rat_justificativa = forms.CharField(
        label='Observação do RAT (opcional)', required=False,
        widget=forms.Textarea(attrs={
            'class': _INPUT_CSS, 'rows': 2,
            'placeholder': JUSTIFICATIVA_PADRAO_RAT_CADASTRO,
        }),
    )

    class Meta:
        model = Professor
        fields = [
            'id_funcional',
            'rh_matricula',
            'rh_nome',
            'tipo_contrato',
            'vinculo_empregaticio',
            'setor_origem',
            'carga_diferenciada',
            'carga_horaria_personalizada',
            'unidades',
            'cursos',
            'status',
            'nivel_ensino_origem',
            'area_atuacao',
        ]
        widgets = {
            'id_funcional': forms.TextInput(attrs={'class': _INPUT_CSS, 'placeholder': 'Ex: 1234567'}),
            'rh_matricula': forms.TextInput(attrs={'class': _INPUT_CSS, 'placeholder': 'Matrícula RH (se houver)'}),
            'rh_nome': forms.TextInput(attrs={'class': _INPUT_CSS, 'placeholder': 'Nome completo'}),
            'tipo_contrato': forms.Select(attrs={'class': _SELECT_CSS}),
            'vinculo_empregaticio': forms.Select(attrs={'class': _SELECT_CSS}),
            'setor_origem': forms.TextInput(attrs={'class': _INPUT_CSS, 'maxlength': 255}),
            'unidades': forms.CheckboxSelectMultiple(attrs={
                'hx-get': '/professores/htmx/cursos-unidade/',
                'hx-target': '#cursos-container',
                'hx-swap': 'innerHTML',
                'hx-trigger': 'change',
                'hx-include': '[name="unidades"],[name="cursos"]',
            }),
            'cursos': forms.CheckboxSelectMultiple(),
            'status': forms.Select(attrs={'class': _SELECT_CSS}),
            'nivel_ensino_origem': forms.Select(attrs={'class': _SELECT_CSS}),
            'area_atuacao': forms.TextInput(attrs={'class': _INPUT_CSS, 'placeholder': 'Ex: Matemática', 'maxlength': 150}),
            'carga_diferenciada': forms.CheckboxInput(attrs={'class': 'w-4 h-4'}),
            'carga_horaria_personalizada': forms.NumberInput(attrs={'class': _INPUT_CSS, 'min': 1, 'max': 60, 'placeholder': 'Ex: 30'}),
        }
        labels = {
            'id_funcional': 'ID',
            'rh_matricula': 'Matrícula RH (opcional)',
            'rh_nome': 'Nome',
            'tipo_contrato': 'Cargo',
            'vinculo_empregaticio': 'Vínculo empregatício',
            'setor_origem': 'Setor de origem',
            'unidades': 'Unidades',
            'cursos': 'Cursos (Checklist)',
            'status': 'Status',
            'nivel_ensino_origem': 'Nível de ensino de origem',
            'area_atuacao': 'Área de atuação',
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if not self.is_bound and self.initial.get('rh_nome'):
            self.initial['rh_nome'] = " ".join(self.initial['rh_nome'].split()).upper()
        self.fields['tipo_contrato'].queryset = ContractType.objects.permitidos().order_by('nome')
        pode_editar_rat = bool(self.user and (
            self.user.is_superuser or self.user.perfil == 'DESUP'
        ))
        self.rat_registro = (
            self._buscar_rat_vigente()
            if self.instance.pk and pode_editar_rat
            else None
        )
        # A DESUP administra o RAT na aba Contrato, no cadastro e na edição, de
        # qualquer professor. O RAT de ingresso externo (carga integral) é o caso
        # particular do professor oriundo do Ensino Médio.
        if self.instance.pk and not pode_editar_rat:
            for campo in CAMPOS_RAT:
                self.fields.pop(campo, None)
        else:
            self.fields['rat_unidade'].queryset = self.fields['unidades'].queryset.order_by('nome')
            if not self.is_bound:
                hoje = timezone.localdate()
                self.fields['rat_data_inicio'].initial = hoje
                if self.rat_registro:
                    self.initial.update({
                        'vem_com_rat': True,
                        'rat_unidade': self.rat_registro.unidade_id,
                        'rat_horas_adicionais': self.rat_registro.horas_adicionais,
                        'rat_data_inicio': self.rat_registro.data_inicio,
                        'rat_data_fim': self.rat_registro.data_fim,
                        'rat_justificativa': self.rat_registro.justificativa,
                    })
        # Cadastros e integrações anteriores a este campo podem omiti-lo. O
        # valor institucional seguro nesses casos é "Não informado".
        self.fields['nivel_ensino_origem'].required = False

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
                self.fields['nivel_ensino_origem'].disabled = True

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
        elif self.initial.get('unidades'):
            valores_iniciais = self.initial['unidades']
            if not isinstance(valores_iniciais, (list, tuple)):
                valores_iniciais = [valores_iniciais]
            unidade_ids = [int(pk) for pk in valores_iniciais if str(pk).isdigit()]
        else:
            unidade_ids = unidades_iniciais

        if unidade_ids:
            self.fields['cursos'].queryset = Course.objects.filter(
                course_units__unidade_id__in=unidade_ids,
                course_units__ativo=True,
            ).order_by('nome').distinct()
        else:
            self.fields['cursos'].queryset = Course.objects.none()

    def _buscar_rat_vigente(self):
        from apps.core.models import ExcecaoCargaUnidade

        hoje = timezone.localdate()
        return (
            ExcecaoCargaUnidade.objects.filter(
                professor=self.instance,
                status=ExcecaoCargaUnidade.StatusChoices.APROVADA,
            )
            .filter(Q(data_fim__isnull=True) | Q(data_fim__gte=hoje))
            .select_related('unidade')
            .order_by('-ingresso_externo', '-data_inicio', '-criado_em')
            .first()
        )

    def clean_nivel_ensino_origem(self):
        return (
            self.cleaned_data.get('nivel_ensino_origem')
            or Professor.NivelEnsinoOrigemChoices.NAO_INFORMADO
        )

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('vem_com_rat'):
            return cleaned

        if not (cleaned.get('id_funcional') or '').strip():
            self.add_error('id_funcional', 'Informe o ID funcional para salvar o professor como RAT.')

        unidades = list(cleaned.get('unidades') or [])
        unidade_rat = cleaned.get('rat_unidade')
        if not unidade_rat and len(unidades) == 1:
            unidade_rat = cleaned['rat_unidade'] = unidades[0]
        if not unidade_rat:
            self.add_error('rat_unidade', 'Informe em qual unidade o professor vem como RAT.')
        elif unidade_rat not in unidades:
            self.add_error('rat_unidade', 'A unidade do RAT precisa estar entre as unidades marcadas do professor.')

        if not cleaned.get('rat_horas_adicionais'):
            self.add_error('rat_horas_adicionais', 'Informe as horas semanais do RAT.')

        inicio, fim = cleaned.get('rat_data_inicio'), cleaned.get('rat_data_fim')
        if not inicio:
            self.add_error('rat_data_inicio', 'Informe o início da vigência do RAT.')
        elif fim and fim < inicio:
            self.add_error('rat_data_fim', 'O fim da vigência não pode ser anterior ao início.')

        cleaned['rat_justificativa'] = (
            (cleaned.get('rat_justificativa') or '').strip()
            or (
                JUSTIFICATIVA_PADRAO_RAT_EDICAO
                if self.instance.pk
                else JUSTIFICATIVA_PADRAO_RAT_CADASTRO
            )
        )
        return cleaned

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


class SolicitacaoCessaoProfessorForm(forms.Form):
    """Pedido do coordenador à DESUP para usar um professor de outra unidade."""

    professor = forms.ModelChoiceField(
        label='Professor de outra unidade', queryset=Professor.objects.none(),
        widget=forms.Select(attrs={'class': _SELECT_CSS}),
    )
    justificativa = forms.CharField(
        label='Justificativa',
        widget=forms.Textarea(attrs={
            'class': _INPUT_CSS, 'rows': 4,
            'placeholder': 'Ex.: Professor necessário para a disciplina X no semestre.',
        }),
    )

    def __init__(self, *args, unidade=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = Professor.objects.filter(status=Professor.StatusChoices.ATIVO)
        if unidade is not None:
            qs = qs.exclude(unidades=unidade).exclude(unidade_principal=unidade)
        self.fields['professor'].queryset = qs.distinct().order_by('desup_nome', 'rh_nome')
        self.fields['professor'].label_from_instance = lambda p: p.nome


class SolicitacaoCadastroProfessorForm(forms.Form):
    """Pedido do coordenador de unidade à DESUP para cadastrar um professor."""

    nome = forms.CharField(
        label='Nome do professor', max_length=255,
        widget=forms.TextInput(attrs={
            'class': _INPUT_CSS,
            'placeholder': 'Ex.: Maria da Silva',
        }),
    )
    id_funcional = forms.CharField(
        label='ID Funcional', max_length=50, required=False,
        widget=forms.TextInput(attrs={
            'class': _INPUT_CSS,
            'placeholder': 'Ex.: 12345678',
        }),
    )
    rh_matricula = forms.CharField(
        label='Matrícula RH (opcional)', max_length=50, required=False,
        widget=forms.TextInput(attrs={
            'class': _INPUT_CSS,
            'placeholder': 'Ex.: 00/123456',
        }),
    )
    tipo_contrato = forms.ModelChoiceField(
        label='Tipo de contrato', queryset=ContractType.objects.none(), required=False,
        empty_label='Não sei informar',
        widget=forms.Select(attrs={'class': _SELECT_CSS}),
    )
    observacao = forms.CharField(
        label='Observações', required=False,
        widget=forms.Textarea(attrs={
            'class': _INPUT_CSS, 'rows': 4,
            'placeholder': (
                'Ex.: Atua no curso de Administração, na disciplina de Gestão de Pessoas.'
            ),
        }),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tipo_contrato'].queryset = ContractType.objects.permitidos().order_by('nome')
