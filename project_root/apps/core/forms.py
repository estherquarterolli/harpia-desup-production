import re

from django import forms
from .models import (
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
        fields = ["nome", "exige_curso", "permite_multiplos", "ativo", "ordem"]
        widgets = {
            "nome": forms.TextInput(attrs={"class": _INPUT_CSS}),
            "exige_curso": forms.CheckboxInput(attrs={"class": "h-4 w-4 rounded"}),
            "permite_multiplos": forms.CheckboxInput(attrs={"class": "h-4 w-4 rounded"}),
            "ativo": forms.CheckboxInput(attrs={"class": "h-4 w-4 rounded"}),
            "ordem": forms.NumberInput(attrs={"class": _INPUT_CSS, "min": 0}),
        }


class ReducaoOcupacaoEquipeDiretivaForm(forms.ModelForm):
    class Meta:
        model = OcupacaoEquipeDiretiva
        fields = ["carga_reducao_horas", "observacoes"]
        widgets = {
            "carga_reducao_horas": forms.NumberInput(attrs={"class": _INPUT_CSS, "min": "0", "max": "168", "step": "0.25"}),
            "observacoes": forms.Textarea(attrs={"class": _INPUT_CSS, "rows": 3}),
        }


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
