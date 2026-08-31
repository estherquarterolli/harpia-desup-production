"""
Forms para Alocação Extracurricular.

Separação clara de responsabilidades:
  - PendenciaExtraForm          → Coordenador de Unidade (cria/edita cabeçalho)
  - OrientacaoTCCForm           → Coordenador (dados do TCC)
  - AtividadeExtensionistaForm  → Coordenador (dados da extensão)
  - ReducaoCargaHorariaForm     → Coordenador (dados da redução)
  - ParecerForm                 → DESUP (parecer + motivo — mesmo widget para os 3 tipos)
"""
from django import forms
from django.forms import inlineformset_factory

from apps.extra_curricular.models import (
    AtividadeExtensionista,
    OrientacaoTCC,
    ParecerChoices,
    PendenciaExtra,
    ReducaoCargaHoraria,
)

# ─── Estilo base para inputs ────────────────────────────────────────
_INPUT  = "form-field w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#1e4e8c] focus:border-transparent"
_SELECT = _INPUT + " cursor-pointer"
_TEXTAREA = _INPUT + " resize-none"
_READONLY = "w-full rounded-lg border border-slate-100 bg-slate-50 px-3 py-2 text-sm text-slate-500 cursor-not-allowed select-none"

# `AtividadeExtensionista.carga_horaria` é DecimalField(max_digits=6,
# decimal_places=1) → cabe no máximo 99999,9h. Como a CH é `num_estudantes × 0,5`,
# a partir de 200.000 estudantes o próprio `save()` estoura com
# `decimal.InvalidOperation` (HTTP 500) em vez de recusar a entrada. Não é regra
# de negócio (a extensão não tem teto de alunos), é o limite físico do campo.
MAX_ESTUDANTES_EXTENSAO = 199_999

# ════════════════════════════════════════════════════════════════════
# Base FormSet com Validações Globais (40h Máximas / BTT)
# ════════════════════════════════════════════════════════════════════
from django.forms.models import BaseInlineFormSet

class BasePendenciaFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return

        pendencia = self.instance
        if not pendencia or not pendencia.pk:
            return

        professor = pendencia.professor
        ch_sala = professor.ch_alocada

        # Calcula a CH dos outros tipos (ignorando o tipo atual que está sendo salvo)
        from apps.extra_curricular.services import get_pendencias_data
        # Para evitar problemas de dependência circular, faremos a soma manualmente:
        # CORR-004: cast explícito para float — `ch_aprovada` já é sempre float,
        # mas o float(...) blinda a soma contra qualquer resquício Decimal/float.
        ch_outros = 0.0
        if self.model != OrientacaoTCC:
            ch_outros += sum(float(item.ch_aprovada) for item in pendencia.orientacoes_tcc.all())
        if self.model != AtividadeExtensionista:
            ch_outros += sum(float(item.ch_aprovada) for item in pendencia.atividades_extensao.all())
        if self.model != ReducaoCargaHoraria:
            ch_outros += sum(float(item.ch_aprovada) for item in pendencia.reducoes_ch.all())

        # Calcula a CH deste formset específico (levando em conta deletes e adições)
        ch_deste_formset = 0
        for form in self.forms:
            if self.can_delete and self._should_delete_form(form):
                continue
            if not form.is_valid():
                continue
                
            dados = form.cleaned_data
            if not dados:
                continue
                
            if self.model == OrientacaoTCC:
                num = dados.get("num_orientandos", 0)
                ch_deste_formset += float(min(num * 0.5, 4.0)) # Limite max 4h TCC
            elif self.model == AtividadeExtensionista:
                num = dados.get("num_estudantes", 0)
                ch_deste_formset += float(num * 0.5)
            elif self.model == ReducaoCargaHoraria:
                ch_deste_formset += float(dados.get("horas_reduzidas", 0))

        ch_extra_total = float(ch_outros) + ch_deste_formset
        ch_global_total = float(ch_sala) + ch_extra_total

        if professor.limite_horas_extra is not None:
            limite = float(professor.limite_horas_extra)
            if ch_extra_total > limite:
                raise forms.ValidationError(
                    f"Limite de horas extracurriculares excedido. O limite definido para este docente é {limite}h. "
                    f"As justificativas extras totalizariam {ch_extra_total}h."
                )
        else:
            limite_total = float(professor.ch_total) if professor.ch_total else 40.0
            if ch_global_total > limite_total:
                raise forms.ValidationError(
                    f"Limite global de {limite_total}h semanais excedido. O docente já possui {ch_sala}h em sala. "
                    f"As justificativas extras totalizariam {ch_extra_total}h (Total: {ch_global_total}h)."
                )

        # Preparação Regra BTT: se for BTT, trava em 10h de sala (o front/alocação já deve travar)
        # if professor.tipo_contrato and "BTT" in professor.tipo_contrato.nome and ch_sala > 10:
        #    raise forms.ValidationError("Regra BTT: Docente BTT não pode ultrapassar 10h em sala.")



# ════════════════════════════════════════════════════════════════════
# PendenciaExtraForm — Cabeçalho (Coordenador)
# ════════════════════════════════════════════════════════════════════
class PendenciaExtraForm(forms.ModelForm):
    class Meta:
        model   = PendenciaExtra
        fields  = ["professor", "semestre", "sei_numero"]
        widgets = {
            "professor": forms.Select(attrs={"class": _SELECT}),
            "semestre": forms.TextInput(attrs={
                "class": _INPUT,
                "placeholder": "Ex: 2026.1",
            }),
            "sei_numero": forms.TextInput(attrs={
                "class": _INPUT,
                "placeholder": "SEI-999999/999999/9999",
            }),
        }

    def __init__(self, *args, unidade=None, **kwargs):
        super().__init__(*args, **kwargs)
        if unidade:
            from apps.professors.models import Professor
            self.fields["professor"].queryset = (
                Professor.objects
                .filter(unidade_principal=unidade)
                .order_by("rh_nome")
            )
        self.fields["professor"].empty_label = "Selecionar docente..."
        self.fields["sei_numero"].required = False


# ════════════════════════════════════════════════════════════════════
# OrientacaoTCC (Coordenador)
# ════════════════════════════════════════════════════════════════════
class OrientacaoTCCForm(forms.ModelForm):
    class Meta:
        model  = OrientacaoTCC
        fields = ["num_orientandos"]
        widgets = {
            "num_orientandos": forms.NumberInput(attrs={
                "class": _INPUT + " text-center",
                "min": 1,
                "max": 8,
                "placeholder": "1–8",
                "data-ch-tcc": "1",
            }),
        }

    def clean_num_orientandos(self):
        valor = self.cleaned_data.get("num_orientandos")
        if valor and valor > 8:
            raise forms.ValidationError("O máximo é 8 orientandos por professor.")
        return valor


OrientacaoTCCFormSet = inlineformset_factory(
    PendenciaExtra,
    OrientacaoTCC,
    form=OrientacaoTCCForm,
    formset=BasePendenciaFormSet,
    fields=["num_orientandos"],
    extra=1,
    can_delete=True,
)


# ════════════════════════════════════════════════════════════════════
# AtividadeExtensionista (Coordenador)
# ════════════════════════════════════════════════════════════════════
class AtividadeExtensionistaForm(forms.ModelForm):
    class Meta:
        model  = AtividadeExtensionista
        fields = ["num_estudantes"]
        widgets = {
            "num_estudantes": forms.NumberInput(attrs={
                "class": _INPUT + " text-center",
                "min": 1,
                "placeholder": "Nº estudantes",
                "data-ch-ext": "1",
            }),
        }

    def clean_num_estudantes(self):
        valor = self.cleaned_data.get("num_estudantes")
        if valor and valor > MAX_ESTUDANTES_EXTENSAO:
            raise forms.ValidationError(
                f"Valor acima do suportado: informe no máximo {MAX_ESTUDANTES_EXTENSAO} estudantes."
            )
        return valor


AtividadeExtensionistaFormSet = inlineformset_factory(
    PendenciaExtra,
    AtividadeExtensionista,
    form=AtividadeExtensionistaForm,
    formset=BasePendenciaFormSet,
    fields=["num_estudantes"],
    extra=1,
    can_delete=True,
)


# ════════════════════════════════════════════════════════════════════
# ReducaoCargaHoraria (Coordenador)
# ════════════════════════════════════════════════════════════════════
class ReducaoCargaHorariaForm(forms.ModelForm):
    class Meta:
        model  = ReducaoCargaHoraria
        fields = ["motivo_reducao", "horas_reduzidas"]
        widgets = {
            "motivo_reducao": forms.Textarea(attrs={
                "class": _TEXTAREA,
                "rows": 2,
                "placeholder": "Descreva a legislação ou aprovação que fundamenta a redução...",
            }),
            "horas_reduzidas": forms.NumberInput(attrs={
                "class": _INPUT + " text-center",
                "min": "0.5",
                "step": "0.5",
                "placeholder": "Horas",
            }),
        }

    def clean_horas_reduzidas(self):
        valor = self.cleaned_data.get("horas_reduzidas")
        # Redução negativa (ou zerada) não é justificativa: além de não fazer
        # sentido, um valor negativo ABATE a CH já aprovada do docente e libera
        # aprovações que estourariam o limite de horas extras.
        if valor is not None and valor <= 0:
            raise forms.ValidationError("Informe um valor de horas maior que zero.")
        return valor


ReducaoCargaHorariaFormSet = inlineformset_factory(
    PendenciaExtra,
    ReducaoCargaHoraria,
    form=ReducaoCargaHorariaForm,
    formset=BasePendenciaFormSet,
    fields=["motivo_reducao", "horas_reduzidas"],
    extra=1,
    can_delete=True,
)


# ════════════════════════════════════════════════════════════════════
# ParecerForm — Exclusivo DESUP (avalia parecer de cada item)
# ════════════════════════════════════════════════════════════════════
class ParecerTCCForm(forms.ModelForm):
    class Meta:
        model  = OrientacaoTCC
        fields = ["parecer_desup", "num_orientandos_aprovados", "horas_aprovadas", "motivo_parecer"]
        widgets = {
            "parecer_desup": forms.Select(attrs={"class": _SELECT}),
            "num_orientandos_aprovados": forms.NumberInput(attrs={
                "class": _INPUT + " text-center",
                "min": 0,
                "max": 8,
                "placeholder": "0–8",
            }),
            "horas_aprovadas": forms.NumberInput(attrs={
                "class": _READONLY,
                "readonly": "readonly",
                "step": "0.1",
            }),
            "motivo_parecer": forms.Textarea(attrs={
                "class": _TEXTAREA,
                "rows": 2,
                "placeholder": "Justifique o parecer (se necessário)...",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.prefix:
            for field in self.fields.values():
                field.widget.attrs['form'] = f"form-{self.prefix}"

    def clean(self):
        cleaned = super().clean()
        aprovados = cleaned.get("num_orientandos_aprovados")
        # O nº solicitado não está no form (é campo da unidade); vem da instância.
        solicitados = self.instance.num_orientandos
        # A DESUP defere, no máximo, o que foi pedido: aprovar mais orientandos
        # do que os solicitados inventa CH que ninguém pediu (o `ch_aprovada` é
        # recalculado a partir do nº aprovado).
        if aprovados is not None and solicitados is not None and aprovados > solicitados:
            self.add_error(
                "num_orientandos_aprovados",
                f"Não é possível aprovar {aprovados} orientandos: foram solicitados apenas {solicitados}.",
            )
        return cleaned


class ParecerExtensaoForm(forms.ModelForm):
    class Meta:
        model  = AtividadeExtensionista
        fields = ["parecer_desup", "num_estudantes_aprovados", "horas_aprovadas", "motivo_parecer"]
        widgets = {
            "parecer_desup": forms.Select(attrs={"class": _SELECT}),
            "num_estudantes_aprovados": forms.NumberInput(attrs={
                "class": _INPUT + " text-center",
                "min": 0,
                "placeholder": "Nº aprovado",
            }),
            "horas_aprovadas": forms.NumberInput(attrs={
                "class": _READONLY,
                "readonly": "readonly",
                "step": "0.1",
            }),
            "motivo_parecer": forms.Textarea(attrs={
                "class": _TEXTAREA,
                "rows": 2,
                "placeholder": "Justifique o parecer (se necessário)...",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.prefix:
            for field in self.fields.values():
                field.widget.attrs['form'] = f"form-{self.prefix}"

    def clean(self):
        cleaned = super().clean()
        aprovados = cleaned.get("num_estudantes_aprovados")
        # Mesma regra do TCC: o deferimento é limitado ao que a unidade pediu.
        solicitados = self.instance.num_estudantes
        if aprovados is not None and solicitados is not None and aprovados > solicitados:
            self.add_error(
                "num_estudantes_aprovados",
                f"Não é possível aprovar {aprovados} estudantes: foram solicitados apenas {solicitados}.",
            )
        return cleaned


class ParecerReducaoForm(forms.ModelForm):
    """Parecer da DESUP sobre uma redução de carga horária."""

    class Meta:
        model  = ReducaoCargaHoraria
        fields = ["parecer_desup", "horas_aprovadas", "motivo_parecer"]
        widgets = {
            "parecer_desup": forms.Select(attrs={"class": _SELECT}),
            "horas_aprovadas": forms.NumberInput(attrs={
                "class": _INPUT,
                "step": "0.1",
                "min": "0",
            }),
            "motivo_parecer": forms.Textarea(attrs={
                "class": _TEXTAREA,
                "rows": 2,
                "placeholder": "Justifique o parecer (se necessário)...",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.prefix:
            for field in self.fields.values():
                field.widget.attrs['form'] = f"form-{self.prefix}"

    def clean(self):
        cleaned = super().clean()
        aprovadas = cleaned.get("horas_aprovadas")
        # As horas solicitadas não estão no form (é campo da unidade); vêm da
        # instância. Mesma regra dos pareceres de TCC e Extensão: a DESUP defere
        # no máximo o que foi pedido — aprovar mais horas do que as solicitadas
        # inventa CH que ninguém pediu e ainda consome o limite do docente.
        solicitadas = self.instance.horas_reduzidas
        if aprovadas is not None and solicitadas is not None and aprovadas > solicitadas:
            self.add_error(
                "horas_aprovadas",
                f"Não é possível aprovar {aprovadas}h: foram solicitadas apenas {solicitadas}h.",
            )
        return cleaned
