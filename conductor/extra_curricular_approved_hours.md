# Extracurricular Approved Students/Units Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow DESUP administrators to approve extracurricular activities by specifying the number of students/units (e.g., "3 out of 6 students"), automatically calculating the approved hours while defaulting to total requested hours if left blank. The approval column will be moved to the left for better visibility.

**Architecture:** 
1.  Add `num_orientandos_aprovados` to `OrientacaoTCC` and `num_estudantes_aprovados` to `AtividadeExtensionista`.
2.  Update `ch_aprovada` properties to calculate hours based on these new fields if provided.
3.  Modify forms to include the new fields.
4.  Refactor UI templates (Detail and Batch views) to move the approval input to the left.

**Tech Stack:** Django, Python, HTML/Tailwind CSS.

---

### Task 1: Update Models

**Files:**
- Modify: `project_root/apps/extra_curricular/models.py`

- [ ] **Step 1: Add new fields to `OrientacaoTCC` and `AtividadeExtensionista`**

```python
# In OrientacaoTCC
num_orientandos_aprovados = models.PositiveSmallIntegerField(
    null=True,
    blank=True,
    verbose_name="Orientandos Aprovados",
    validators=[MaxValueValidator(8)],
    help_text="Nº de orientandos aprovados pela DESUP. Se vazio, usa o total solicitado.",
)

# In AtividadeExtensionista
num_estudantes_aprovados = models.PositiveIntegerField(
    null=True,
    blank=True,
    verbose_name="Estudantes Aprovados",
    help_text="Nº de estudantes aprovados pela DESUP. Se vazio, usa o total solicitado.",
)
```

- [ ] **Step 2: Update `ch_aprovada` properties and `save()` logic**

Update the `ch_aprovada` property in both models to prioritize the new approved counts.
Update `save()` to calculate `horas_aprovadas` based on the new fields if they are set.

- [ ] **Step 3: Create and run migrations**

Run: `python manage.py makemigrations extra_curricular && python manage.py migrate extra_curricular`

---

### Task 2: Update Forms

**Files:**
- Modify: `project_root/apps/extra_curricular/forms.py`

- [ ] **Step 1: Update `ParecerTCCForm` and `ParecerExtensaoForm`**

Replace `horas_aprovadas` with the new approved count fields in these forms (since Alberto wants to input the number of students).
Keep `horas_aprovadas` as a readonly field or remove it from these specific forms if we want strictly student count input. The requirement says Alberto confirms "quantas horas... Foram aprovadas" but the scenario says "aprovou 3 de 6 alunos", and user confirmed "Input Students/Units". So we show the student count input.

---

### Task 3: Update Detail View Templates

**Files:**
- Modify: `project_root/templates/extra_curricular/partials/_accordion_tcc.html`
- Modify: `project_root/templates/extra_curricular/partials/_accordion_extensao.html`
- Modify: `project_root/templates/extra_curricular/partials/_accordion_reducao.html`

- [ ] **Step 1: Reorder columns in `_accordion_tcc.html`**

Move "Aprovar (Nº Orientandos)" to the left, right after "Docente".
Update the form to use `num_orientandos_aprovados`.

- [ ] **Step 2: Reorder columns in `_accordion_extensao.html`**

Move "Aprovar (Nº Estudantes)" to the left.
Update the form to use `num_estudantes_aprovados`.

- [ ] **Step 3: Reorder columns in `_accordion_reducao.html`**

Move "CH Aprovada (DESUP)" to the left for consistency, even though it's still hours.

---

### Task 4: Update Batch (Lote) View Templates

**Files:**
- Modify: `project_root/templates/extra_curricular/partials/_accordion_tcc_lote.html`
- Modify: `project_root/templates/extra_curricular/partials/_accordion_extensao_lote.html`
- Modify: `project_root/templates/extra_curricular/partials/_accordion_reducao_lote.html`

- [ ] **Step 1: Apply same reordering and field updates to lote partials**

Ensure the "Mesa de Trabalho" also reflects the new layout and inputs.

---

### Task 5: Verification

- [ ] **Step 1: Run Django system checks**
Run: `python manage.py check`

- [ ] **Step 2: Verify logic in a shell or test**
Create a test case where a TCC has 6 students (3h) and 3 are approved (1.5h).
Verify `ch_aprovada` returns 1.5.
Verify if blank it returns 3.0.
