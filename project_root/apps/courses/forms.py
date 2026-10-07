# pyrefly: ignore [missing-import]
from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory

from .models import (
    ClassGroup,
    Course,
    CourseUnit,
    CurriculumMatrix,
    MatrixComponent,
    CurricularComponent,
    calcular_carga_horaria_semanal,
)
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
        fields = ['curso', 'unidades', 'nome', 'turno']
        widgets = {
            'curso': forms.Select(attrs={'class': _FIELD_CSS}),
            'unidades': forms.CheckboxSelectMultiple(),
            'nome': forms.TextInput(attrs={
                'class': _FIELD_CSS,
                'placeholder': 'Ex: MC-ADS-2026',
            }),
            'turno': forms.Select(attrs={'class': _FIELD_CSS}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['nome'].label = "Código da Matriz"
        self.fields['curso'].queryset = Course.objects.all().order_by('nome')
        self.fields['curso'].required = False
        self.fields['unidades'].queryset = Unidade.objects.filter(status=True).order_by('nome')
        self.fields['unidades'].required = False
        # Matrizes legadas podem continuar sem turno no banco até o saneamento,
        # mas toda criação/edição feita pela aplicação precisa escolher um valor.
        self.fields['turno'].required = True
        self.fields['turno'].choices = [
            ('', 'Selecione o turno'),
            *CurriculumMatrix._meta.get_field('turno').choices,
        ]


class CatalogoChoiceField(forms.ModelChoiceField):
    """ModelChoiceField que valida contra um dicionário já carregado.

    Num formset com dezenas de linhas, o ModelChoiceField padrão faz um
    ``queryset.get()`` por linha no POST. Com o banco remoto, cada ida e volta
    custa caro; aqui o catálogo é lido uma única vez pelo formset.
    """

    catalogo_cache = None

    def to_python(self, value):
        if self.catalogo_cache is None or value in self.empty_values:
            return super().to_python(value)
        try:
            return self.catalogo_cache[int(value)]
        except (KeyError, TypeError, ValueError):
            raise forms.ValidationError(
                self.error_messages['invalid_choice'],
                code='invalid_choice',
                params={'value': value},
            )


class MatrixComponentForm(forms.ModelForm):
    # Não é campo do model — chave que decide, por linha, se a disciplina vem do
    # catálogo (`componente_curricular`) ou é digitada na hora (`nome_temporario`).
    # Ver clean() e _usar_temporaria_ativo().
    usar_disciplina_temporaria = forms.BooleanField(
        required=False,
        label="Disciplina não cadastrada (temporária, só nesta matriz)",
        widget=forms.CheckboxInput(attrs={'class': 'rounded text-[#1e4e8c] usar-disciplina-temporaria'}),
    )

    class Meta:
        model = MatrixComponent
        field_classes = {'componente_curricular': CatalogoChoiceField}
        fields = [
            'componente_curricular',
            'nome_temporario',
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
            'nome_temporario': forms.TextInput(attrs={
                'class': _FIELD_CSS,
                'placeholder': 'Nome da disciplina (temporária)',
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

    def __init__(self, *args, catalogo_cache=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['codigo'].required = False
        self.fields['carga_horaria'].required = False
        self.fields['creditos'].required = False
        self.fields['carga_horaria_semanal'].required = False
        self.fields['nome_temporario'].required = False
        # FK obrigatória no model, mas aqui a linha pode usar disciplina
        # temporária em vez de catálogo — quem garante "um dos dois" é o clean().
        self.fields['componente_curricular'].required = False
        self.fields['componente_curricular'].queryset = CurricularComponent.objects.all().order_by('nome')
        self.fields['componente_curricular'].catalogo_cache = catalogo_cache
        # A tela escolhe a disciplina pelo autocomplete (o <select> fica oculto e o
        # JS cria as <option> sob demanda). Renderizar o catálogo inteiro em cada
        # linha gerava uma consulta e centenas de <option> por linha; aqui o
        # select leva só a disciplina atualmente escolhida.
        self.fields['componente_curricular'].widget.choices = self._choices_disciplina_atual(catalogo_cache)

        if self.instance.pk and self.instance.componente_curricular_id is None and self.instance.nome_temporario:
            self.fields['usar_disciplina_temporaria'].initial = True

        # O template precisa deste estado também ao re-renderizar um POST com
        # erro. Basear-se apenas na instance escondia o nome temporário e deixava
        # o campo de pesquisa do catálogo vazio, embora o checkbox estivesse marcado.
        self.modo_temporario_ativo = self._usar_temporaria_ativo()

        # CORR-007: na matriz, o usuário só escolhe a **Disciplina** e o **Período**.
        # Todo o resto ('Código', 'CH Total', 'Créditos', 'CH Sem.') deriva da
        # disciplina e NÃO pode ser alterado pela DESUP — só via Django admin
        # (super admin/dev). disabled=True bloqueia a edição na UI e faz o Django
        # ignorar qualquer valor vindo no POST (à prova de adulteração); o valor
        # correto é recalculado no clean() a partir da disciplina.
        self.fields['codigo'].disabled = True
        self.fields['creditos'].disabled = True
        self.fields['carga_horaria_semanal'].disabled = True
        # Exceção: disciplina TEMPORÁRIA não existe em lugar nenhum pra derivar a
        # CH — a DESUP digita direto. Por isso `carga_horaria` só fica travada
        # (herdada do catálogo) quando a linha NÃO está em modo temporário.
        self.fields['carga_horaria'].disabled = not self.modo_temporario_ativo

    def _choices_disciplina_atual(self, catalogo_cache):
        choices = [('', '---------')]
        if self.is_bound:
            raw = self.data.get(self.add_prefix('componente_curricular'))
            try:
                atual = catalogo_cache.get(int(raw)) if catalogo_cache and raw else None
            except (TypeError, ValueError):
                atual = None
        else:
            atual = self.instance.componente_curricular if self.instance.componente_curricular_id else None
        self.componente_curricular_nome_exibicao = atual.nome if atual is not None else ''
        if atual is not None:
            choices.append((atual.pk, str(atual)))
        return choices

    def _usar_temporaria_ativo(self):
        """Se esta linha (pelo prefixo do formset) está em modo disciplina
        temporária — decide se `carga_horaria` fica editável nesta renderização.
        Bound (POST/re-render após erro): olha o valor enviado. Unbound (GET,
        edição de uma linha já salva como temporária): olha a instance."""
        if self.is_bound:
            return bool(self.data.get(self.add_prefix('usar_disciplina_temporaria')))
        return bool(
            self.instance.pk
            and self.instance.componente_curricular_id is None
            and self.instance.nome_temporario
        )

    def clean(self):
        cleaned_data = super().clean()
        cc = cleaned_data.get('componente_curricular')
        usar_temporaria = cleaned_data.get('usar_disciplina_temporaria')
        nome_temp = (cleaned_data.get('nome_temporario') or '').strip()

        if usar_temporaria:
            # O checkbox é a fonte de verdade do modo da linha. Autocomplete,
            # importação e abas antigas podem deixar um FK residual no <select>
            # oculto; nesse caso, normalize para temporária em vez de rejeitar o
            # rascunho como se o usuário tivesse escolhido conscientemente os dois.
            cleaned_data['componente_curricular'] = None
            if not nome_temp:
                self.add_error('nome_temporario', 'Informe o nome da disciplina temporária.')
                return cleaned_data
            ch = cleaned_data.get('carga_horaria')
            if not ch or ch <= 0:
                self.add_error('carga_horaria', 'Informe a carga horária desta disciplina temporária.')
                return cleaned_data
            cleaned_data['componente_curricular'] = None
            cleaned_data['nome_temporario'] = nome_temp
            # Ao converter uma disciplina de catálogo em temporária, nunca
            # preserve o código antigo. MatrixComponent.save() gera TEMP-xxxxx
            # usando o id da linha, inclusive durante a edição de uma matriz.
            cleaned_data['codigo'] = ''
            # Mesma regra de derivação de créditos/CH semanal do fluxo de catálogo
            # (MatrixComponent.save()), só que a partir da CH digitada na hora.
            cleaned_data['creditos'] = ch // 20
            cleaned_data['carga_horaria_semanal'] = calcular_carga_horaria_semanal(ch)
            return cleaned_data

        # Fluxo original (disciplina do catálogo) — inalterado.
        cleaned_data['nome_temporario'] = ''
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
            cleaned_data['carga_horaria_semanal'] = calcular_carga_horaria_semanal(ch)
        else:
            self.add_error(
                'componente_curricular',
                'Selecione uma disciplina do catálogo ou marque "disciplina não cadastrada" e informe o nome.'
            )
        return cleaned_data


class MatrixComponentBaseFormSet(BaseInlineFormSet):
    """Permite ignorar linhas extras totalmente vazias.

    ``min_num=1`` é mantido para renderizar uma linha inicial e garantir que a
    matriz tenha ao menos um componente. Por padrão, porém, o Django torna essa
    primeira linha extra obrigatória. Isso quebrava a importação: as linhas da
    planilha eram acrescentadas depois dela e a linha inicial vazia invalidava o
    formset. O próprio ``validate_min`` continua recusando uma matriz realmente
    vazia depois que as linhas extras passam a ser opcionais individualmente.
    """

    def __init__(self, *args, **kwargs):
        if kwargs.get('queryset') is None:
            kwargs['queryset'] = MatrixComponent.objects.select_related('componente_curricular')
        bound = kwargs.get('data') is not None or (args and args[0] is not None)
        if bound:
            # Um único SELECT para validar todas as linhas (ver CatalogoChoiceField).
            catalogo = {c.pk: c for c in CurricularComponent.objects.all()}
            kwargs['form_kwargs'] = {**(kwargs.get('form_kwargs') or {}), 'catalogo_cache': catalogo}
        super().__init__(*args, **kwargs)
        for form in self.extra_forms:
            form.empty_permitted = True


MatrixComponentFormSet = inlineformset_factory(
    CurriculumMatrix,
    MatrixComponent,
    form=MatrixComponentForm,
    formset=MatrixComponentBaseFormSet,
    fields=MatrixComponentForm.Meta.fields,
    # Na criação, min_num garante uma linha inicial. Na edição, mostrar apenas
    # os componentes realmente salvos; novas linhas são adicionadas pelo botão
    # "Adicionar componente". Evita três linhas vazias a cada reabertura.
    extra=0,
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


class SpreadsheetImportForm(forms.Form):
    """Base: upload de planilha (.xlsx) OU link público do Google Sheets — um dos dois.

    Compartilhada por `CurricularComponentImportForm` (catálogo de disciplinas) e
    `MatrixComponentImportForm` (linhas de uma matriz) — mesma regra de validação
    do arquivo/link nos dois casos, só muda o que se faz com as linhas depois.
    """

    arquivo = forms.FileField(
        required=False,
        label="Planilha Excel (.xlsx)",
        widget=forms.ClearableFileInput(attrs={'class': _FIELD_CSS, 'accept': '.xlsx'}),
    )
    google_sheets_url = forms.URLField(
        required=False,
        label="ou link do Google Sheets",
        widget=forms.URLInput(attrs={
            'class': _FIELD_CSS,
            'placeholder': 'https://docs.google.com/spreadsheets/d/.../edit',
        }),
    )

    def clean(self):
        cleaned = super().clean()
        arquivo = cleaned.get('arquivo')
        url = cleaned.get('google_sheets_url')
        if not arquivo and not url:
            raise forms.ValidationError("Envie um arquivo .xlsx ou cole o link de uma planilha do Google Sheets.")
        if arquivo and url:
            raise forms.ValidationError("Escolha só uma opção: arquivo OU link do Google Sheets, não os dois.")
        if arquivo and not arquivo.name.lower().endswith('.xlsx'):
            raise forms.ValidationError("O arquivo precisa ser .xlsx (Excel).")
        return cleaned


class CurricularComponentImportForm(SpreadsheetImportForm):
    """Upload de planilha pra importar o catálogo de Componentes Curriculares."""


class MatrixComponentImportForm(SpreadsheetImportForm):
    """Upload de planilha pra importar as linhas de disciplina de UMA matriz.

    Só habilitado na tela depois que a unidade da matriz é selecionada
    (ver MatrixImportRowsView e o JS de matrix_form.html) — pedido do cliente
    pra não deixar importar planilha "solta" antes de saber pra qual unidade ela vale.
    """


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
