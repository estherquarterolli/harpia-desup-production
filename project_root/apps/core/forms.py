import re

from django import forms
from django.utils.functional import cached_property
from .models import (
    AtividadeEstagioSupervisao,
    ConfiguracaoCargoDiretivoUnidade,
    ExcecaoCargaUnidade,
    JanelaEntrega,
    LimiteCargaUnidade,
    OcupacaoEquipeDiretiva,
    ReadaptacaoProfessor,
    SolicitacaoProfessorExterno,
    TipoCargoDiretivo,
)

# Classe de input consistente com os demais campos das telas de janela.
_DATE_CSS = ('w-full px-3 py-2.5 border border-slate-200 rounded-lg text-sm '
             'bg-slate-50 focus:bg-white focus:border-[#025c9f] outline-none transition')
_INPUT_CSS = ('w-full px-3 py-2.5 border border-slate-200 rounded-lg text-sm '
              'bg-white focus:border-[#025c9f] focus:ring-2 focus:ring-blue-100 outline-none transition')
_SELECT_CSS = _INPUT_CSS

# O semestre é usado como chave lógica em alocações/matrizes e aparece cru na tela;
# sem formato fixo entrava qualquer string ("banana!!") e a janela virava órfã.
SEMESTRE_REGEX = re.compile(r'^\d{4}\.[12]$')


class JanelaEntregaValidacaoMixin:
    """
    Regras de integridade da JanelaEntrega compartilhadas pelos três forms
    (o do admin, em `forms.py`, e os de criar/editar da tela da DESUP, em
    `views.py`). Ficam aqui num lugar só porque validá-las em apenas um dos
    caminhos é o mesmo que não validar: o outro caminho grava o registro ruim.

    Cobre o que a auditoria pegou:
    - `data_fim < data_inicio`: a janela nunca é `is_ativa`, vira registro morto —
      e, quando expira, `fechar_janelas_expiradas` a marca como Fechado.
    - semestre livre: qualquer texto era aceito.
    - sobreposição de janelas no mesmo escopo (mesma unidade, ou duas globais):
      duas janelas valendo ao mesmo tempo tornam ambíguo qual prazo vale e é
      exatamente o cenário em que a janela futura mascarava a vigente.
    """

    def _validar_regras_da_janela(self, cleaned_data):
        inicio = cleaned_data.get('data_inicio')
        fim = cleaned_data.get('data_fim')
        semestre = (cleaned_data.get('semestre') or '').strip()
        unidade = cleaned_data.get('unidade')

        if semestre and not SEMESTRE_REGEX.match(semestre):
            self.add_error(
                'semestre',
                'Informe o semestre no formato AAAA.1 ou AAAA.2 (ex.: 2026.1).',
            )

        # inicio == fim é permitido (abertura/reabertura de 24h); só barra fim < inicio.
        if inicio and fim and fim < inicio:
            self.add_error('data_fim', 'A data de fim não pode ser anterior à data de início.')
            return cleaned_data

        if inicio and fim:
            # Intervalos [a,b] e [c,d] se sobrepõem quando a <= d e c <= b.
            conflitos = JanelaEntrega.objects.filter(
                unidade=unidade,
                data_inicio__lte=fim,
                data_fim__gte=inicio,
            )
            if self.instance and self.instance.pk:
                conflitos = conflitos.exclude(pk=self.instance.pk)
            if conflitos.exists():
                escopo = f'a unidade {unidade.sigla}' if unidade else 'todas as unidades'
                self.add_error(
                    None,
                    f'Já existe uma janela de entrega para {escopo} que se sobrepõe a este '
                    f'período. Edite a janela existente em vez de criar outra.',
                )

        return cleaned_data


class JanelaEntregaForm(JanelaEntregaValidacaoMixin, forms.ModelForm):
    class Meta:
        model = JanelaEntrega
        fields = '__all__'
        widgets = {
            # HTML5 date picker: exibe dd/mm/aaaa no locale pt-BR do navegador e
            # armazena/parseia em ISO (yyyy-mm-dd), evitando o formato US (mm/dd/aa)
            # do input de texto padrao do Django (LANGUAGE_CODE=en-us).
            'data_inicio': forms.DateInput(
                format='%Y-%m-%d',
                attrs={'type': 'date', 'class': _DATE_CSS},
            ),
            'data_fim': forms.DateInput(
                format='%Y-%m-%d',
                attrs={'type': 'date', 'class': _DATE_CSS},
            ),
        }

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

    def clean(self):
        # Este form é o do admin: não impõe "data não pode ser no passado" (o admin
        # precisa poder cadastrar/corrigir períodos históricos), mas as regras de
        # integridade valem igual às da tela da DESUP.
        return self._validar_regras_da_janela(super().clean())

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Ao editar a janela de entrega o status ficará automaticamente como "Reaberto",
        # ao colocar a opção "Aberto" no seletor na edição da janela de entrega, a ideia é reutilizar a lógica do "Reaberto"
        if self.instance.pk and instance.status == JanelaEntrega.StatusChoices.ABERTO:
            instance.status = JanelaEntrega.StatusChoices.REABERTO
        
        if commit:
            instance.save()
        return instance


class TipoCargoDiretivoForm(forms.ModelForm):
    class Meta:
        model = TipoCargoDiretivo
        fields = ["nome", "carga_reducao_horas", "exige_curso", "permite_multiplos", "ativo"]
        widgets = {
            "nome": forms.TextInput(attrs={"class": _INPUT_CSS}),
            "carga_reducao_horas": forms.NumberInput(attrs={"class": _INPUT_CSS, "min": "0", "max": "20", "step": "0.25"}),
            "exige_curso": forms.CheckboxInput(attrs={"class": "h-4 w-4 rounded"}),
            "permite_multiplos": forms.CheckboxInput(attrs={"class": "h-4 w-4 rounded"}),
            "ativo": forms.CheckboxInput(attrs={"class": "h-4 w-4 rounded"}),
        }


class TipoCargoDiretivoUpdateForm(TipoCargoDiretivoForm):
    """A edição do catálogo não recebe a redução específica da unidade."""

    class Meta(TipoCargoDiretivoForm.Meta):
        fields = ["nome", "exige_curso", "permite_multiplos", "ativo"]


class TipoCargoDiretivoUnidadeForm(TipoCargoDiretivoUpdateForm):
    # Nome diferente do campo global: o ModelForm só grava metadados no cargo.
    carga_reducao_unidade = ConfiguracaoCargoDiretivoUnidade._meta.get_field(
        'carga_reducao_horas',
    ).formfield(
        # Campo adicional ao ModelForm: precisa dos validadores do modelo local.
        validators=ConfiguracaoCargoDiretivoUnidade._meta.get_field('carga_reducao_horas').validators,
        widget=forms.NumberInput(attrs={
            'class': _INPUT_CSS, 'min': '0', 'max': '20', 'step': '0.25',
        }),
    )

    def __init__(self, *args, unidade, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['carga_reducao_unidade'].label = f'Redução semanal em {unidade.sigla}'
        self.fields['carga_reducao_unidade'].help_text = (
            'Esta redução vale somente para a unidade selecionada. '
            'Reduções individuais são preservadas.'
        )
        self.order_fields(['nome', 'carga_reducao_unidade', 'exige_curso', 'permite_multiplos', 'ativo'])


class OpcoesOcupacaoEquipeDiretiva:
    """Listas de seleção compartilhadas apenas durante uma requisição da unidade."""

    def __init__(self, unidade):
        self.unidade = unidade

    @cached_property
    def professores(self):
        from django.db.models import Q
        from apps.professors.models import Professor

        professores = Professor.objects.filter(
            Q(unidade_principal=self.unidade) | Q(unidades=self.unidade),
        ).only('pk', 'rh_nome', 'desup_nome', 'id_funcional', 'rh_matricula').distinct().order_by('rh_nome')
        return [(prof.pk, str(prof)) for prof in professores]

    @cached_property
    def cursos(self):
        from apps.courses.models import CourseUnit

        cursos = CourseUnit.objects.filter(unidade=self.unidade, ativo=True).select_related(
            'curso', 'unidade',
        ).order_by('curso__nome')
        return [(curso.pk, str(curso)) for curso in cursos]


class ConfiguracaoCargoDiretivoUnidadeForm(forms.ModelForm):
    class Meta:
        model = ConfiguracaoCargoDiretivoUnidade
        fields = ["carga_reducao_horas"]
        widgets = {
            "carga_reducao_horas": forms.NumberInput(attrs={
                "class": _INPUT_CSS, "min": "0", "max": "20", "step": "0.25",
            }),
        }


class OcupacaoEquipeDiretivaForm(forms.ModelForm):
    """Preenche um cargo da equipe diretiva de uma unidade já escolhida na tela."""

    class Meta:
        model = OcupacaoEquipeDiretiva
        fields = ["professor", "curso", "data_inicio", "data_fim", "observacoes"]
        widgets = {
            "professor": forms.Select(attrs={"class": _SELECT_CSS}),
            "curso": forms.Select(attrs={"class": _SELECT_CSS}),
            "data_inicio": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": _DATE_CSS}),
            "data_fim": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": _DATE_CSS}),
            "observacoes": forms.Textarea(attrs={"class": _INPUT_CSS, "rows": 3}),
        }

    def __init__(self, *args, unidade, cargo, opcoes=None, **kwargs):
        super().__init__(*args, **kwargs)
        from django.db.models import Q
        from apps.courses.models import CourseUnit
        from apps.professors.models import Professor

        # Atribuídos antes do full_clean para que o clean() do modelo valide
        # vínculo do servidor, curso da unidade e conflitos de vigência.
        self.instance.unidade = unidade
        self.fields["data_fim"].help_text = "A partir desta data a ocupacao deixa de estar vigente."
        self.instance.cargo = cargo
        self.fields["professor"].queryset = Professor.objects.filter(
            Q(unidade_principal=unidade) | Q(unidades=unidade)
        ).distinct().order_by("rh_nome")
        if opcoes is not None:
            self.fields['professor'].choices = [('', self.fields['professor'].empty_label), *opcoes.professores]
        if cargo.exige_curso:
            self.fields["curso"].required = True
            cursos_unidade = CourseUnit.objects.filter(
                unidade=unidade, ativo=True,
            ).select_related("curso", "unidade").order_by("curso__nome")
            self.fields["curso"].queryset = cursos_unidade
            if opcoes is not None:
                self.fields['curso'].choices = [('', self.fields['curso'].empty_label), *opcoes.cursos]
            self.fields["curso"].label = "Curso"
            self.fields["curso"].help_text = (
                "Selecione um curso ativo desta unidade."
                if (bool(opcoes.cursos) if opcoes is not None else cursos_unidade.exists())
                else "Nenhum curso ativo cadastrado nesta unidade. Cadastre ou ative um curso antes de preencher este cargo."
            )
        else:
            del self.fields["curso"]


class ReducaoOcupacaoEquipeDiretivaForm(forms.ModelForm):
    class Meta:
        model = OcupacaoEquipeDiretiva
        fields = ["carga_reducao_horas", "observacoes"]
        widgets = {
            "carga_reducao_horas": forms.NumberInput(attrs={"class": _INPUT_CSS, "min": "0", "max": "20", "step": "0.25"}),
            "observacoes": forms.Textarea(attrs={"class": _INPUT_CSS, "rows": 3}),
        }


class OcupacaoEquipeDiretivaUnidadeForm(forms.ModelForm):
    """
    Formulário de preenchimento e atualização de ocupante da equipe diretiva
    pelo Coordenador de Unidade. Não expõe `carga_reducao_horas`, que é
    definida exclusivamente pela DESUP.
    """

    class Meta:
        model = OcupacaoEquipeDiretiva
        fields = ["professor", "curso", "data_inicio", "data_fim", "observacoes"]
        widgets = {
            "professor": forms.Select(attrs={"class": _SELECT_CSS}),
            "curso": forms.Select(attrs={"class": _SELECT_CSS}),
            "data_inicio": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": _DATE_CSS}),
            "data_fim": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": _DATE_CSS}),
            "observacoes": forms.Textarea(attrs={"class": _INPUT_CSS, "rows": 3}),
        }

    def __init__(self, *args, unidade, cargo, opcoes=None, **kwargs):
        super().__init__(*args, **kwargs)
        from django.db.models import Q
        from apps.courses.models import CourseUnit
        from apps.professors.models import Professor

        self.instance.unidade = unidade
        self.fields["data_fim"].help_text = "A partir desta data a ocupacao deixa de estar vigente."
        self.instance.cargo = cargo
        self.fields["professor"].queryset = Professor.objects.filter(
            Q(unidade_principal=unidade) | Q(unidades=unidade)
        ).distinct().order_by("rh_nome")
        if opcoes is not None:
            self.fields['professor'].choices = [('', self.fields['professor'].empty_label), *opcoes.professores]
        if cargo.exige_curso:
            self.fields["curso"].required = True
            cursos_unidade = CourseUnit.objects.filter(
                unidade=unidade, ativo=True,
            ).select_related("curso", "unidade").order_by("curso__nome")
            self.fields["curso"].queryset = cursos_unidade
            if opcoes is not None:
                self.fields['curso'].choices = [('', self.fields['curso'].empty_label), *opcoes.cursos]
            self.fields["curso"].label = "Curso"
            self.fields["curso"].help_text = (
                "Selecione um curso ativo desta unidade."
                if (bool(opcoes.cursos) if opcoes is not None else cursos_unidade.exists())
                else "Nenhum curso ativo cadastrado nesta unidade. Cadastre ou ative um curso antes de preencher este cargo."
            )
        else:
            del self.fields["curso"]


class AtividadeEstagioSupervisaoUnidadeForm(forms.ModelForm):
    """
    Formulário da unidade para registro e atualização de atividades de estágio
    e supervisão. O campo `carga_reducao_horas` é exclusivo da DESUP e não é editável aqui.
    """

    class Meta:
        model = AtividadeEstagioSupervisao
        fields = [
            "tipo",
            "professor",
            "curso",
            "semestre",
            "num_estudantes",
            "carga_horaria_semanal",
            "data_inicio",
            "data_fim",
            "observacoes",
        ]
        widgets = {
            "tipo": forms.Select(attrs={"class": _SELECT_CSS}),
            "professor": forms.Select(attrs={"class": _SELECT_CSS}),
            "curso": forms.Select(attrs={"class": _SELECT_CSS}),
            "semestre": forms.TextInput(attrs={"class": _INPUT_CSS, "placeholder": "Ex.: 2026.1"}),
            "num_estudantes": forms.NumberInput(attrs={"class": _INPUT_CSS, "min": "1", "max": "200"}),
            "carga_horaria_semanal": forms.NumberInput(attrs={"class": _INPUT_CSS, "min": "0", "max": "40", "step": "0.5"}),
            "data_inicio": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": _DATE_CSS}),
            "data_fim": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": _DATE_CSS}),
            "observacoes": forms.Textarea(attrs={"class": _INPUT_CSS, "rows": 3}),
        }

    def __init__(self, *args, unidade, **kwargs):
        super().__init__(*args, **kwargs)
        from django.db.models import Q
        from apps.allocations.services import semestre_atual
        from apps.courses.models import CourseUnit
        from apps.professors.models import Professor

        self.instance.unidade = unidade
        # O semestre letivo não é uma escolha do usuário. Em novos registros,
        # ele acompanha automaticamente a data local (jan–jun = ano.1;
        # jul–dez = ano.2). Em edições, preservamos o semestre histórico do
        # registro. ``disabled`` também faz o Django ignorar eventual valor
        # adulterado no POST e usar o valor inicial definido pelo servidor.
        semestre_do_registro = (
            self.instance.semestre
            if self.instance.pk and self.instance.semestre
            else semestre_atual()
        )
        self.initial["semestre"] = semestre_do_registro
        self.fields["semestre"].disabled = True
        self.fields["semestre"].help_text = "Definido automaticamente conforme a data atual."
        self.fields["professor"].queryset = Professor.objects.filter(
            Q(unidade_principal=unidade) | Q(unidades=unidade)
        ).distinct().order_by("rh_nome")
        cursos_unidade = CourseUnit.objects.filter(
            unidade=unidade, ativo=True,
        ).select_related("curso", "unidade").order_by("curso__nome")
        self.fields["curso"].queryset = cursos_unidade
        self.fields["curso"].required = False
        self.fields["curso"].empty_label = "Todos os cursos / Não vinculado a curso específico"


class LimiteCargaUnidadeForm(forms.ModelForm):
    class Meta:
        model = LimiteCargaUnidade
        fields = ["unidade", "limite_horas_semanais", "data_inicio", "data_fim", "observacoes"]
        widgets = {
            "unidade": forms.Select(attrs={"class": _SELECT_CSS}),
            "limite_horas_semanais": forms.NumberInput(attrs={"class": _INPUT_CSS, "min": "0.01", "step": "0.25"}),
            "data_inicio": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": _DATE_CSS}),
            "data_fim": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": _DATE_CSS}),
            "observacoes": forms.Textarea(attrs={"class": _INPUT_CSS, "rows": 3}),
        }
        labels = {"limite_horas_semanais": "Teto semanal (horas-aula)"}
        help_texts = {
            "limite_horas_semanais": (
                "Soma máxima de horas-aula semanais que a unidade pode alocar, "
                "considerando todos os professores."
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["unidade"].queryset = self.fields["unidade"].queryset.filter(status=True).order_by("nome")


class ReadaptacaoProfessorForm(forms.ModelForm):
    class Meta:
        model = ReadaptacaoProfessor
        fields = ["professor", "data_inicio", "data_fim", "justificativa_administrativa"]
        widgets = {
            "professor": forms.Select(attrs={"class": _SELECT_CSS}),
            "data_inicio": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": _DATE_CSS}),
            "data_fim": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": _DATE_CSS}),
            "justificativa_administrativa": forms.Textarea(attrs={"class": _INPUT_CSS, "rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.professors.models import Professor

        self.fields["professor"].queryset = Professor.objects.order_by("rh_nome")


class ReadaptacaoProfessorEdicaoForm(forms.ModelForm):
    """Edição da vigência/justificativa sem trocar o professor da readaptação."""

    class Meta(ReadaptacaoProfessorForm.Meta):
        fields = ["data_inicio", "data_fim", "justificativa_administrativa"]


class DecisaoSolicitacaoProfessorForm(forms.Form):
    decisao = forms.ChoiceField(
        label="Decisão",
        choices=(
            (SolicitacaoProfessorExterno.StatusChoices.APROVADA, "Aprovar"),
            (SolicitacaoProfessorExterno.StatusChoices.RECUSADA, "Recusar"),
        ),
        widget=forms.Select(attrs={"class": _SELECT_CSS}),
    )
    motivo_decisao = forms.CharField(
        label="Motivo da decisão",
        widget=forms.Textarea(attrs={"class": _INPUT_CSS, "rows": 3}),
        required=False,
    )

    def clean(self):
        cleaned = super().clean()
        if (
            cleaned.get("decisao") == SolicitacaoProfessorExterno.StatusChoices.RECUSADA
            and not (cleaned.get("motivo_decisao") or "").strip()
        ):
            self.add_error("motivo_decisao", "Informe o motivo da recusa.")
        return cleaned


class SolicitacaoRatUnidadeForm(forms.ModelForm):
    class Meta:
        model = ExcecaoCargaUnidade
        fields = ['professor', 'horas_adicionais', 'data_inicio', 'data_fim', 'justificativa']
        labels = {'horas_adicionais': 'Horas adicionais semanais solicitadas'}
        widgets = {
            'professor': forms.Select(attrs={'class': _SELECT_CSS}),
            'horas_adicionais': forms.NumberInput(attrs={'class': _INPUT_CSS, 'min': '0.01', 'step': '0.01'}),
            'data_inicio': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': _DATE_CSS}),
            'data_fim': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': _DATE_CSS}),
            'justificativa': forms.Textarea(attrs={'class': _INPUT_CSS, 'rows': 3}),
        }

    def __init__(self, *args, unidade, **kwargs):
        from django.db.models import Q
        from apps.professors.models import Professor

        super().__init__(*args, **kwargs)
        self.instance.unidade = unidade
        self.fields['professor'].required = True
        self.fields['professor'].help_text = 'Selecione um professor vinculado à sua unidade.'
        self.fields['professor'].queryset = Professor.objects.filter(
            Q(unidade_principal=unidade) | Q(unidades=unidade),
        ).select_related('tipo_contrato').prefetch_related('ocupacoes_diretivas').distinct()

    def clean_professor(self):
        from apps.professors.services import (
            obter_cargas_rat, MENSAGEM_CARGA_RAT_INCOMPLETA, MENSAGEM_ID_RAT_OBRIGATORIO,
        )

        professor = self.cleaned_data['professor']
        if not (professor.id_funcional or '').strip():
            raise forms.ValidationError(MENSAGEM_ID_RAT_OBRIGATORIO)
        if not obter_cargas_rat([professor])[str(professor.pk)]['completa']:
            raise forms.ValidationError(MENSAGEM_CARGA_RAT_INCOMPLETA)
        return professor


class DecisaoExcecaoCargaForm(forms.Form):
    decisao = forms.ChoiceField(
        label="Decisão",
        choices=(
            (ExcecaoCargaUnidade.StatusChoices.APROVADA, "Aprovar"),
            (ExcecaoCargaUnidade.StatusChoices.RECUSADA, "Recusar"),
        ),
        widget=forms.Select(attrs={"class": _SELECT_CSS}),
    )
    motivo_decisao = forms.CharField(
        label="Motivo da decisão",
        widget=forms.Textarea(attrs={"class": _INPUT_CSS, "rows": 3}),
        required=False,
    )

    def clean(self):
        cleaned = super().clean()
        if (
            cleaned.get("decisao") == ExcecaoCargaUnidade.StatusChoices.RECUSADA
            and not (cleaned.get("motivo_decisao") or "").strip()
        ):
            self.add_error("motivo_decisao", "Informe o motivo da recusa.")
        return cleaned
