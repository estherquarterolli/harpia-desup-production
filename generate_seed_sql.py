"""
Gerador de SQL para importação no Supabase.
Schema real: courses_course tem unidade_id diretamente (sem tabela CourseUnit).
Executa com: python generate_seed_sql.py
"""
import sys, os, csv, re, unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'project_root'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

import django
django.setup()

from django.contrib.auth.hashers import make_password
import pandas as pd

OUT = Path(__file__).parent / 'seed_supabase.sql'

# ─── helpers ──────────────────────────────────────────────────────────────────

def q(s):
    """Escape single-quote para SQL."""
    if s is None:
        return 'NULL'
    return "'" + str(s).replace("'", "''") + "'"

def slugify(text):
    text = unicodedata.normalize('NFKD', str(text))
    text = text.encode('ascii', 'ignore').decode('ascii')
    text = re.sub(r'[^\w\s-]', '', text).strip().lower()
    return re.sub(r'[-\s]+', '_', text)

def ascii_upper(s):
    return unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode().upper()

# ─── unidades ─────────────────────────────────────────────────────────────────
# (id, nome, sigla)
UNIDADES = [
    (1,  'FAETERJ Paracambi',                  'PAR'),
    (2,  'FAETERJ Barra Mansa',                'BAR'),
    (3,  'FAETERJ Campos dos Goytacazes',      'CAM'),
    (4,  'FAETERJ Duque de Caxias',            'DUQ'),
    (5,  'FAETERJ Petrópolis',                 'PET'),
    (6,  'FAETERJ Rio de Janeiro',             'RIO'),
    (7,  'FAETERJ Três Rios',                  '3RIO'),
    (8,  'FAETERJ Santo Antônio de Pádua',     'PAD'),
    (9,  'FAETERJ Bom Jesus de Itabapoana',    'BJI'),
    (10, 'FAETERJ Itaperuna',                  'ITA'),
    (11, 'ISEPAM',                             'ISEPAM'),
    (12, 'ISERJ',                              'ISERJ'),
    (13, 'FAETERJ Volta Redonda',              'VR'),
]

SETOR_TO_UNIDADE_ID = {
    'FAETERJ PARACAMBI':                       1,
    'FAETERJ BARRA MANSA':                     2,
    'FAETERJ CAMPOS DOS GOYTCAZES':            3,
    'FAETERJ DUQUE DE CAXIAS':                4,
    'FAETERJ PETROPOLIS':                      5,
    'FAETERJ RIO DE JANEIRO':                 6,
    'FAETERJ TRES RIOS':                       7,
    'FAETERJ SANTO ANTONIO DE PADUA':          8,
    'FAETERJ BOM JESUS DE ITABAPOANA':         9,
    'FAETERJ ITAPERUNA':                      10,
    'ISEPAM - INSTITUTO SUPERIOR':            11,
    'ISEPAM':                                 11,
    'ISERJ - INSTITUTO SUPERIOR DE EDUCACAO': 12,
    'ISERJ - INSTITUTO SUPERIOR':             12,
    'FAETERJ VOLTA REDONDA':                  13,
}

def setor_to_uid(setor_raw):
    key = ascii_upper(setor_raw)
    if key in SETOR_TO_UNIDADE_ID:
        return SETOR_TO_UNIDADE_ID[key]
    for k, v in SETOR_TO_UNIDADE_ID.items():
        if k in key:
            return v
    return None

# ─── usuários ─────────────────────────────────────────────────────────────────
# (id, email, password, perfil, is_superuser, is_staff, unidade_id, forcar_troca_senha)
USERS = [
    (1, 'estagio.analista1@desup.faetec.rj.gov.br', '@Eq122507@',  'DESUP',               True,  True,  None, False),
    (2, 'estagio.analista2@desup.faetec.rj.gov.br', 'Faetec@123',  'DESUP',               True,  True,  None, False),
    (3, 'alberto.alvaraes@desup.faetec.rj.gov.br',  '0@Aprisma',   'DESUP',               False, True,  None, False),
    (4, 'paracambi.unidade@faeterj-pr.edu.br',       'Faetec@123',  'COORDENADOR_UNIDADE', False, False, 1,    True),
]

# ─── tipos de contrato ────────────────────────────────────────────────────────
# (id, nome, categoria, regime, dias_pres, max_class_hours, max_total_hours, max_classes)
CONTRACT_TYPES = [
    (1, 'Professor FAETEC I - 40h',            'EFETIVO', '40h',    3, 32, 40, 6),
    (2, 'Professor FAETEC I - 20h',            'EFETIVO', '20h',    2, 16, 20, 4),
    (3, 'Professor FAETEC Ensino Superior 40h','EFETIVO', '40h DE', 3, 32, 40, 6),
    (4, 'Instrutor',                            'EFETIVO', '40h',    3, 20, 40, 4),
]

def get_contract_id(cargo):
    cargo = ascii_upper(str(cargo) if cargo else '')
    if 'INSTRUTOR' in cargo:                return 4
    if 'ENS SUP' in cargo or 'ENSINO SUP' in cargo: return 3
    if '20 H' in cargo or '20H' in cargo:   return 2
    return 1

# ─── CSVs das matrizes ────────────────────────────────────────────────────────
CSV_DIR = Path(__file__).parent / 'docs' / 'sensivel'

# CSV → lista de unidade_ids a que se aplica
CSV_UNIDADES = {
    'FAETERJ_PARACAMBI.CSV':                              [1],
    'FAETERJ_BARRAMANSA.CSV':                             [2],
    'FAETERJ_CAMPOS.CSV':                                 [3],
    'FAETERJ_DUQUEDECAXIAS.CSV':                          [4],
    'FAETERJ_PETROPOLIS.CSV':                             [5],
    'FAETERJ_RIO.CSV':                                    [6],
    'FAETERJ_3RIOS.CSV':                                  [7],
    'FAETERJ_STANTONIODEPADUA-ITABOANA-ITAPERUNA-3RIOS.CSV': [7, 8, 9, 10],
    'ISEPAM.CSV':                                         [11],
    'ISERJ.CSV':                                          [12],
}

COURSE_SIGLA = {
    'Análise e Desenvolvimento de Sistemas':    'ADS',
    'Gestão Ambiental':                         'GESTAMB',
    'Sistemas para Internet':                   'SPI',
    'Gestão Portuária':                         'GPORT',
    'Processos Gerenciais':                     'PGER',
    'Tecnologia da Informação e da Comunicação':'TIC',
    'Logística':                                'LOG',
    'Licenciatura em Pedagogia':                'LICPED',
}

def read_csv(fname):
    path = CSV_DIR / fname
    rows = []
    with open(path, encoding='utf-8-sig') as f:
        reader = csv.reader(f, delimiter=';')
        next(reader)  # header
        for row in reader:
            if len(row) >= 5:
                rows.append({
                    'curso':      row[1].strip(),
                    'periodo':    row[2].strip(),
                    'disciplina': row[4].strip(),
                })
    return rows

# ─── Coletar dados ────────────────────────────────────────────────────────────

# courses_course: (id, nome, sigla, unidade_id)
# Um registro por (curso_nome, unidade_id)
course_list = []        # list of (id, nome, sigla, unidade_id)
course_key_to_id = {}   # (nome, unidade_id) → id
course_id_seq = 1

# courses_curricularcomponent: únicos por nome
comp_list = []          # list of (id, nome, sigla)
comp_name_to_id = {}    # nome → id
comp_id_seq = 1

# courses_curriculummatrix: (id, curso_id, nome, periodo_letivo)
matrix_list = []        # list of (id, curso_id, nome_mat)
matrix_curso_to_id = {} # curso_id → matrix_id
matrix_id_seq = 1

# courses_matrixcomponent: (id, matriz_id, componente_id, periodo)
mc_list = []
mc_id_seq = 1
mc_seen = set()  # (matriz_id, comp_id)

for fname, unids in CSV_UNIDADES.items():
    rows = read_csv(fname)

    # Cursos únicos neste arquivo
    cursos_no_arquivo = {}
    for row in rows:
        cursos_no_arquivo.setdefault(row['curso'], []).append(row)

    for curso_nome, disc_rows in cursos_no_arquivo.items():
        sigla_base = COURSE_SIGLA.get(curso_nome, ascii_upper(curso_nome[:6]))

        for uid in unids:
            key = (curso_nome, uid)
            if key not in course_key_to_id:
                # Sigla única: base + sigla da unidade se repetir
                sigla = sigla_base
                existing = {c[2] for c in course_list if c[3] == uid}
                counter = 1
                while sigla in existing:
                    sigla = sigla_base[:5] + str(counter)
                    counter += 1

                course_list.append((course_id_seq, curso_nome, sigla, uid))
                course_key_to_id[key] = course_id_seq
                course_id_seq += 1

            cid = course_key_to_id[key]

            # Matriz para este curso (uma por curso)
            if cid not in matrix_curso_to_id:
                # Nome da matriz baseado na sigla do curso
                initials_m = ascii_upper(curso_nome)
                initials_m = ''.join(w[0] for w in initials_m.split() if w)[:5]
                nome_mat = f"MC-{initials_m}-2026.1"
                matrix_list.append((matrix_id_seq, cid, nome_mat))
                matrix_curso_to_id[cid] = matrix_id_seq
                matrix_id_seq += 1

            mxid = matrix_curso_to_id[cid]

            # Componentes curriculares
            for row in disc_rows:
                nome_disc = row['disciplina']

                # Registrar componente global
                if nome_disc not in comp_name_to_id:
                    words = [w for w in nome_disc.split() if len(w) > 2]
                    raw_sigla = ''.join(w[0].upper() for w in words[:5]) if words else nome_disc[:5].upper()
                    sigla_cc = ascii_upper(raw_sigla)[:5]
                    # Garantir unicidade de sigla
                    base_cc = sigla_cc
                    counter = 1
                    existing_cc = {v[1] for v in comp_list}
                    while sigla_cc in existing_cc:
                        sigla_cc = base_cc[:4] + str(counter)
                        counter += 1
                    comp_list.append((comp_id_seq, nome_disc, sigla_cc))
                    comp_name_to_id[nome_disc] = comp_id_seq
                    comp_id_seq += 1

                ccid = comp_name_to_id[nome_disc]
                key_mc = (mxid, ccid)
                if key_mc not in mc_seen:
                    mc_seen.add(key_mc)
                    periodo_str = f"{row['periodo']}º Semestre" if row['periodo'].isdigit() else row['periodo']
                    mc_list.append((mc_id_seq, mxid, ccid, periodo_str))
                    mc_id_seq += 1

# ─── Professores ──────────────────────────────────────────────────────────────

def load_professors():
    df = pd.read_excel(
        r'C:\Users\esther.santos\Downloads\LISTA F_FEV-23 C DISCIPLINA (pronta-completa) (1).xlsx',
        sheet_name='TRAB'
    )
    cargo_prof = df['NOME_CARGO'].str.contains('PROFESSOR|INSTRUTOR|PROF FAETEC', na=False)
    setor_ok   = df['SETOR_DESC'].str.contains(
        r'FAETERJ|ISEPAM - INSTITUTO|ISERJ - INSTITUTO SUPERIOR DE',
        na=False, regex=True
    )
    return df[cargo_prof & setor_ok].copy()

profs_df = load_professors()

prof_list = []          # (id, id_func, matricula, nome, email_rh, unidade_id, contrato_id)
prof_id_seq = 1
seen_idf = set()

for _, row in profs_df.iterrows():
    id_func  = str(row['ID_FUNCIONAL']).strip()
    if id_func in seen_idf:
        continue
    seen_idf.add(id_func)

    matricula = str(row['MATRICULA']).strip() if pd.notna(row['MATRICULA']) else id_func
    nome      = str(row['NOME']).strip()
    setor_raw = str(row['SETOR_DESC']).strip() if pd.notna(row['SETOR_DESC']) else ''
    cargo     = str(row['NOME_CARGO']).strip() if pd.notna(row['NOME_CARGO']) else ''

    uid  = setor_to_uid(setor_raw)
    ctid = get_contract_id(cargo)

    slug_nome  = slugify(nome)[:30]
    email_rh   = f"{slug_nome}@faetec.rj.gov.br"

    prof_list.append((prof_id_seq, id_func, matricula, nome, email_rh, uid, ctid))
    prof_id_seq += 1

# ─── Gerar SQL ────────────────────────────────────────────────────────────────

lines = []
def emit(s=''): lines.append(s)

emit('-- ============================================================')
emit('-- Seed SQL gerado para Supabase — schema real')
emit('-- Gerado em: 2026-06-26')
emit('-- ============================================================')
emit()
emit('BEGIN;')
emit()

# ── 1. Unidades ───────────────────────────────────────────────────────────────
emit('-- ── 1. Unidades ─────────────────────────────────────────────')
emit('INSERT INTO core_unidade (id, nome, sigla, status) VALUES')
emit(',\n'.join(
    f"  ({uid}, {q(nome)}, {q(sigla)}, TRUE)"
    for uid, nome, sigla in UNIDADES
) + ';')
emit(f"SELECT setval('core_unidade_id_seq', {max(u[0] for u in UNIDADES)});")
emit()

# ── 2. Usuários ───────────────────────────────────────────────────────────────
emit('-- ── 2. Usuários ─────────────────────────────────────────────')
emit('INSERT INTO accounts_user')
emit('  (id, password, last_login, is_superuser, username, first_name, last_name,')
emit('   email, is_staff, is_active, date_joined, perfil, unidade_id,')
emit('   dados_submetidos, forcar_troca_senha)')
emit('VALUES')
user_rows = []
for uid, email, pwd, perfil, is_super, is_staff, unid, forcar in USERS:
    hashed  = make_password(pwd)
    username = email.split('@')[0]
    unid_val = str(unid) if unid else 'NULL'
    user_rows.append(
        f"  ({uid}, {q(hashed)}, NULL, {'TRUE' if is_super else 'FALSE'}, "
        f"{q(username)}, '', '', {q(email)}, {'TRUE' if is_staff else 'FALSE'}, "
        f"TRUE, NOW(), {q(perfil)}, {unid_val}, FALSE, {'TRUE' if forcar else 'FALSE'})"
    )
emit(',\n'.join(user_rows) + ';')
emit(f"SELECT setval('accounts_user_id_seq', {max(u[0] for u in USERS)});")
emit()

# ── 3. Tipos de Contrato ──────────────────────────────────────────────────────
emit('-- ── 3. Tipos de Contrato ────────────────────────────────────')
emit('INSERT INTO professors_contracttype')
emit('  (id, nome, categoria, regime_trabalho, dias_presenca_obrigatorios,')
emit('   max_class_hours, max_total_hours, max_classes)')
emit('VALUES')
emit(',\n'.join(
    f"  ({cid}, {q(nome)}, {q(cat)}, {q(regime)}, {dias}, {mch}, {mth}, {mc})"
    for cid, nome, cat, regime, dias, mch, mth, mc in CONTRACT_TYPES
) + ';')
emit(f"SELECT setval('professors_contracttype_id_seq', {len(CONTRACT_TYPES)});")
emit()

# ── 4. Cursos (com unidade_id) ────────────────────────────────────────────────
emit('-- ── 4. Cursos (com unidade_id) ─────────────────────────────')
emit('INSERT INTO courses_course (id, nome, sigla, unidade_id) VALUES')
emit(',\n'.join(
    f"  ({cid}, {q(nome)}, {q(sigla)}, {uid})"
    for cid, nome, sigla, uid in course_list
) + ';')
emit(f"SELECT setval('courses_course_id_seq', {len(course_list)});")
emit()

# ── 5. Componentes Curriculares ───────────────────────────────────────────────
emit('-- ── 5. Componentes Curriculares ────────────────────────────')
emit('INSERT INTO courses_curricularcomponent')
emit('  (id, nome, sigla, codigo, carga_horaria_padrao, creditos, ementa)')
emit('VALUES')
emit(',\n'.join(
    f"  ({ccid}, {q(nome)}, {q(sigla)}, '', 80, 4, '')"
    for ccid, nome, sigla in comp_list
) + ';')
emit(f"SELECT setval('courses_curricularcomponent_id_seq', {len(comp_list)});")
emit()

# ── 6. Matrizes Curriculares ──────────────────────────────────────────────────
emit('-- ── 6. Matrizes Curriculares ───────────────────────────────')
emit('INSERT INTO courses_curriculummatrix')
emit('  (id, curso_id, nome, is_vigente, is_rascunho, periodo_letivo, turno, criada_em)')
emit('VALUES')
emit(',\n'.join(
    f"  ({mxid}, {cid}, {q(nome_mat)}, TRUE, FALSE, '2026.1', NULL, NOW())"
    for mxid, cid, nome_mat in matrix_list
) + ';')
emit(f"SELECT setval('courses_curriculummatrix_id_seq', {len(matrix_list)});")
emit()

# ── 7. Componentes das Matrizes ───────────────────────────────────────────────
emit('-- ── 7. Componentes das Matrizes ────────────────────────────')
emit('INSERT INTO courses_matrixcomponent')
emit('  (id, matriz_id, componente_curricular_id, codigo, periodo,')
emit('   carga_horaria, creditos, docente_id, compartilhado, curso_compartilhado_id,')
emit('   carga_horaria_semanal, distribuicao_semanal, status, observacoes)')
emit('VALUES')
emit(',\n'.join(
    f"  ({mcid}, {mxid}, {ccid}, '', {q(periodo)}, 80, 4, NULL, FALSE, NULL, 4.00, '', 'SEM_PROFESSOR', '')"
    for mcid, mxid, ccid, periodo in mc_list
) + ';')
emit(f"SELECT setval('courses_matrixcomponent_id_seq', {len(mc_list)});")
emit()

# ── 8. Professores ────────────────────────────────────────────────────────────
emit('-- ── 8. Professores ──────────────────────────────────────────')
emit('INSERT INTO professors_professor')
emit('  (id, "ID_FUNCIONAL", rh_matricula, rh_nome, rh_email,')
emit('   unidade_principal_id, desup_nome, desup_email,')
emit('   tipo_contrato_id, is_cedido, ha, materia, status)')
emit('VALUES')
emit(',\n'.join(
    f"  ({pid}, {q(idf)}, {q(mat)}, {q(nome)}, {q(email)}, "
    f"{uid if uid else 'NULL'}, NULL, NULL, {ctid}, FALSE, 0, '', 'Ativo')"
    for pid, idf, mat, nome, email, uid, ctid in prof_list
) + ';')
emit(f"SELECT setval('professors_professor_id_seq', {len(prof_list)});")
emit()

emit('COMMIT;')
emit()
emit('-- ── Resumo ───────────────────────────────────────────────────')
emit(f'-- Unidades:              {len(UNIDADES)}')
emit(f'-- Usuários:              {len(USERS)}')
emit(f'-- Tipos de Contrato:     {len(CONTRACT_TYPES)}')
emit(f'-- Cursos (por unidade):  {len(course_list)}')
emit(f'-- Componentes Curricul.: {len(comp_list)}')
emit(f'-- Matrizes:              {len(matrix_list)}')
emit(f'-- MatrixComponents:      {len(mc_list)}')
emit(f'-- Professores:           {len(prof_list)}')

with open(OUT, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))

print(f'SQL gerado em: {OUT}')
print(f'Unidades:              {len(UNIDADES)}')
print(f'Tipos de Contrato:     {len(CONTRACT_TYPES)}')
print(f'Cursos (por unidade):  {len(course_list)}')
print(f'Componentes Curricul.: {len(comp_list)}')
print(f'Matrizes:              {len(matrix_list)}')
print(f'MatrixComponents:      {len(mc_list)}')
print(f'Professores:           {len(prof_list)}')
