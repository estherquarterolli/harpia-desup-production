"""
seed_data.py — Script Django para inserir dados de teste.
Executar com: python manage.py shell < seed_data.py
"""
import os, sys, django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

import pandas as pd
from apps.accounts.models import User
from apps.core.models import Unidade
from apps.professors.models import Professor, ContractType
from apps.courses.models import Course, CourseUnit, CurricularComponent, CurriculumMatrix, MatrixComponent
from apps.allocations.models import AlocacaoCurricular

SENHA_PADRAO = 'Faetec@123'

print("=" * 60)
print("  SEED DATA — AllocGest HARPIA")
print("=" * 60)

# ─────────────────────────────────────────────
# 1. Criar Unidade FAETERJ Paracambi
# ─────────────────────────────────────────────
print("\n[1] Criando unidade FAETERJ Paracambi...")
unidade_paracambi, created = Unidade.objects.get_or_create(
    nome='FAETERJ Paracambi',
    defaults={'sigla': 'FAETERJ-PCB', 'status': True}
)
print(f"    Unidade: {unidade_paracambi} ({'CRIADA' if created else 'já existia'})")

# ─────────────────────────────────────────────
# 2. Criar Tipo de Contrato padrão
# ─────────────────────────────────────────────
print("\n[2] Criando tipos de contrato...")
contrato_40h, _ = ContractType.objects.get_or_create(
    nome='Professor FAETEC Ensino Superior 40H',
    defaults={
        'categoria': 'EFETIVO',
        'regime_trabalho': '40h',
        'dias_presenca_obrigatorios': 3,
        'max_class_hours': 20,
        'max_total_hours': 40,
        'max_classes': 6,
    }
)
contrato_20h, _ = ContractType.objects.get_or_create(
    nome='Professor FAETEC II 20H',
    defaults={
        'categoria': 'EFETIVO',
        'regime_trabalho': '20h',
        'dias_presenca_obrigatorios': 2,
        'max_class_hours': 12,
        'max_total_hours': 20,
        'max_classes': 4,
    }
)
print(f"    40H: {contrato_40h}")
print(f"    20H: {contrato_20h}")

# ─────────────────────────────────────────────
# 3. Criar Usuário Coordenador de Paracambi
# ─────────────────────────────────────────────
print("\n[3] Criando usuário coordenador de Paracambi...")
email_coord = 'coordenador_paracambi@desup.com'
if not User.objects.filter(email=email_coord).exists():
    # cpf e telefone existem na tabela mas não no modelo Django atual.
    # Precisamos fazer a migração para sincronizar.
    from django.db import connection
    # Tornar cpf e telefone nullable para não bloquear
    try:
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA foreign_keys=off;")
            # Criar tabela temp, copiar dados, recriar sem NOT NULL
            # Mais simples: usar default vazio
            cursor.execute("UPDATE accounts_user SET cpf = '' WHERE cpf IS NULL;")
            cursor.execute("UPDATE accounts_user SET telefone = '' WHERE telefone IS NULL;")
        connection.cursor().execute("PRAGMA foreign_keys=on;")
    except Exception as e:
        print(f"    Aviso ao ajustar schema: {e}")
    
    user_coord = User.objects.create_user(
        email=email_coord,
        password=SENHA_PADRAO,
        first_name='Coordenador',
        last_name='Paracambi',
        perfil='COORDENADOR_UNIDADE',
        unidade=unidade_paracambi,
        forcar_troca_senha=True,
    )
    # Set cpf/telefone via raw SQL since model doesn't have them
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE accounts_user SET cpf=%s, telefone=%s WHERE id=%s",
            ['000.000.000-00', '(00) 00000-0000', user_coord.id]
        )
    print(f"    Usuário criado: {user_coord.email} (senha: {SENHA_PADRAO})")
else:
    print(f"    Usuário {email_coord} já existe.")

# ─────────────────────────────────────────────
# 4. Importar professores do Excel
# ─────────────────────────────────────────────
print("\n[4] Importando professores da planilha...")
try:
    df = pd.read_excel('..\\docs\\LISTA F_FEV-23 C DISCIPLINA (pronta-completa).xlsx')
    paracambi_df = df[df['SETOR_DESC'].str.contains('PARACAMBI', case=False, na=False)]
    
    # Filtrar somente linhas que parecem ser professores (cargo contém PROF ou PROFESSOR)
    prof_df = paracambi_df[
        paracambi_df['NOME_CARGO'].str.contains('PROF', case=False, na=False)
    ]
    
    created_count = 0
    skipped_count = 0
    
    for _, row in prof_df.iterrows():
        id_func = str(row['ID_FUNCIONAL']).strip()
        matricula = str(row['MATRICULA']).strip()
        nome = str(row['NOME']).strip()
        cargo = str(row['NOME_CARGO']).strip() if pd.notna(row['NOME_CARGO']) else ''
        
        if matricula == 'nan' or not matricula:
            matricula = f'MAT-{id_func}'
        
        # Determinar tipo de contrato pela descrição do cargo
        if '20' in cargo:
            tipo_contrato = contrato_20h
        else:
            tipo_contrato = contrato_40h
        
        # Determinar o eixo pela disciplina
        disciplina = str(row['DISCIPLINA']).strip().upper() if pd.notna(row['DISCIPLINA']) else ''
        if 'INFORMÁTICA' in disciplina or 'INFORMATIC' in disciplina or 'COMPUTAÇÃO' in disciplina or 'MICRO' in disciplina:
            eixo = 'INFO'
        elif 'MEIO AMBIENTE' in disciplina or 'AMBIENTE' in disciplina:
            eixo = 'QUIMICA'
        elif 'BIOLOGIA' in disciplina or 'PATOLOGIA' in disciplina:
            eixo = 'SAUDE'
        elif 'ADMINISTRA' in disciplina:
            eixo = 'ADMIN'
        elif 'DIREITO' in disciplina or 'LEGISLA' in disciplina:
            eixo = 'FORMACAO'
        elif 'PSICOLOGIA' in disciplina:
            eixo = 'FORMACAO'
        elif 'MATEMÁT' in disciplina or 'MATEMATICA' in disciplina:
            eixo = 'FORMACAO'
        elif 'INGLÊS' in disciplina or 'LINGUA' in disciplina:
            eixo = 'FORMACAO'
        elif 'GEOGRAF' in disciplina:
            eixo = 'FORMACAO'
        elif 'AGRONOMIA' in disciplina:
            eixo = 'QUIMICA'
        else:
            eixo = 'OUTROS'
        
        if not Professor.objects.filter(id_funcional=id_func).exists():
            email_prof = f"{nome.lower().replace(' ', '.')}@faeterj.edu.br"[:254]
            Professor.objects.create(
                id_funcional=id_func,
                rh_matricula=matricula,
                rh_nome=nome,
                rh_email=email_prof,
                unidade_principal=unidade_paracambi,
                tipo_contrato=tipo_contrato,
                materia=eixo,
                status='Ativo',
            )
            created_count += 1
        else:
            skipped_count += 1
    
    print(f"    Professores criados: {created_count}")
    print(f"    Professores ignorados (já existiam): {skipped_count}")
except Exception as e:
    print(f"    ERRO ao importar professores: {e}")
    import traceback; traceback.print_exc()

# ─────────────────────────────────────────────
# 5. Criar Cursos
# ─────────────────────────────────────────────
print("\n[5] Criando cursos...")
curso_ads, _ = Course.objects.get_or_create(
    sigla='ADS',
    defaults={'nome': 'Tecnologia em Análise e Desenvolvimento de Sistemas'}
)
curso_tga, _ = Course.objects.get_or_create(
    sigla='TGA',
    defaults={'nome': 'Tecnologia em Gestão Ambiental'}
)
CourseUnit.objects.get_or_create(curso=curso_ads, unidade=unidade_paracambi)
CourseUnit.objects.get_or_create(curso=curso_tga, unidade=unidade_paracambi)
print(f"    {curso_ads}")
print(f"    {curso_tga}")

# ─────────────────────────────────────────────
# 6. Criar Componentes Curriculares e Matrizes
# ─────────────────────────────────────────────
print("\n[6] Criando componentes curriculares e matrizes...")

# --- ADS: Componentes curriculares ---
ads_disciplinas = [
    # (codigo, sigla, nome, creditos, ch_padrao, periodo)
    ('BDA-I', 'BDA-I', 'Modelagem Conceitual de Dados', 4, 80, '1'),
    ('HSO-I', 'HSO-I', 'Arquitetura de Computadores', 4, 80, '1'),
    ('FGE-I', 'FGE-I', 'Fundamentos de Sistemas de Informação', 2, 40, '1'),
    ('PRG-I', 'PRG-I', 'Programação Estruturada', 4, 80, '1'),
    ('FGE-II', 'FGE-II', 'Matemática Discreta', 4, 80, '1'),
    ('PRG-II', 'PRG-II', 'Ambiente de Edição Web', 4, 80, '1'),
    ('FGE-III', 'FGE-III', 'Português Instrumental', 2, 40, '1'),
    # Periodo 2
    ('BDA-II', 'BDA-II', 'Modelo Relacional e Projeto Lógico de Banco de Dados', 4, 80, '2'),
    ('ENS-I', 'ENS-I', 'Fundamentos de Engenharia de Software', 4, 80, '2'),
    ('ENS-II', 'ENS-II', 'Modelo e Programação Orientados a Objetos', 4, 80, '2'),
    ('PRG-III', 'PRG-III', 'Estruturas de Dados', 4, 80, '2'),
    ('HSO-II', 'HSO-II', 'Sistemas Operacionais e Serviços de Virtualização', 4, 80, '2'),
    ('FGE-IV', 'FGE-IV', 'Estatística', 2, 40, '2'),
    ('FGE-V', 'FGE-V', 'Inglês Instrumental', 2, 40, '2'),
    # Periodo 3
    ('PRG-IV', 'PRG-IV', 'Desenvolvimento Frontend', 4, 80, '3'),
    ('PRG-V', 'PRG-V', 'Interface Humano-Máquina e UI Design', 2, 40, '3'),
    ('FGE-VI', 'FGE-VI', 'Metodologia da Pesquisa', 2, 40, '3'),
    ('ENS-III', 'ENS-III', 'Técnicas de Análise e Projeto de Sistemas', 4, 80, '3'),
    ('HSO-III', 'HSO-III', 'Redes de Computadores', 4, 80, '3'),
    ('ENS-IV', 'ENS-IV', 'Métodos Ágeis', 2, 40, '3'),
    ('EXT-I', 'EXT-I', 'Projeto de Extensão I', 2, 48, '3'),
    # Periodo 4
    ('PRG-VI', 'PRG-VI', 'Desenvolvimento Backend', 4, 80, '4'),
    ('ENS-V', 'ENS-V', 'Arquitetura de Software', 3, 60, '4'),
    ('GTI-I', 'GTI-I', 'Gestão de Processos de Negócios (BPM)', 3, 60, '4'),
    ('PRG-VII', 'PRG-VII', 'Padrões de Projeto', 3, 60, '4'),
    ('ENS-VI', 'ENS-VI', 'Testes de Software', 3, 60, '4'),
    ('ENS-VII', 'ENS-VII', 'Qualidade de Software', 2, 40, '4'),
    ('EXT-II', 'EXT-II', 'Projeto de Extensão II', 4, 96, '4'),
    # Periodo 5
    ('PRG-VIII', 'PRG-VIII', 'Desenvolvimento Mobile', 4, 80, '5'),
    ('ENS-VIII', 'ENS-VIII', 'Abordagem DevOps e Entregas Contínuas', 4, 80, '5'),
    ('FGE-VII', 'FGE-VII', 'Empreendedorismo e Computação', 2, 40, '5'),
    ('GTI-II', 'GTI-II', 'Gestão e Governança de TI', 4, 80, '5'),
    ('GTI-III', 'GTI-III', 'Segurança da Informação', 4, 80, '5'),
    ('GTI-IV', 'GTI-IV', 'Gestão de Projetos', 4, 80, '5'),
    ('FGE-VIII', 'FGE-VIII', 'Direito e Legislação de Informática', 2, 40, '5'),
    ('EXT-III', 'EXT-III', 'Projeto de Extensão III', 4, 96, '5'),
]

# --- TGA: Componentes curriculares ---
tga_disciplinas = [
    # Periodo 1
    ('QUG', 'QUG', 'Química Geral', 2, 40, '1'),
    ('NOD', 'NOD', 'Noções de Direito', 2, 40, '1'),
    ('POR', 'POR', 'Língua Portuguesa', 2, 40, '1'),
    ('STM', 'STM', 'Segurança do Trabalho e Meio Ambiente', 2, 40, '1'),
    ('ETI', 'ETI', 'Ética', 2, 40, '1'),
    ('EDU', 'EDU', 'Educação Ambiental e Sustentabilidade', 3, 60, '1'),
    ('GAM', 'GAM', 'Geometria Aplicada ao Meio Ambiente', 3, 60, '1'),
    ('ENS-TGA', 'ENS', 'Energia e Sustentabilidade', 3, 60, '1'),
    ('MPC', 'MPC', 'Metodologia da Pesquisa Científica', 2, 40, '1'),
    # Periodo 2
    ('EAP', 'EAP', 'Estatística Aplicada', 2, 40, '2'),
    ('MER', 'MER', 'Economia dos Recursos Naturais e Ambiente', 3, 60, '2'),
    ('QIN', 'QIN', 'Química Inorgânica', 2, 40, '2'),
    ('BBT', 'BBT', 'Biologia e Biotecnologia Aplicada', 3, 60, '2'),
    ('BOT', 'BOT', 'Botânica Geral', 2, 40, '2'),
    ('GEO', 'GEO', 'Geociência Ambiental', 2, 40, '2'),
    ('ZGE', 'ZGE', 'Zoologia Geral', 3, 60, '2'),
    ('ELA', 'ELA', 'Ecologia', 3, 60, '2'),
    ('POL', 'POL', 'Política e Legislação Ambiental', 3, 60, '2'),
    ('EXT1-TGA', 'EXT1', 'Extensão 1', 2, 40, '2'),
    # Periodo 3
    ('AGP', 'AGP', 'Administração e Gerenciamento de Projetos', 3, 60, '3'),
    ('RES', 'RES', 'Gerenciamento de Resíduos', 3, 60, '3'),
    ('GES', 'GES', 'Gestão pela Qualidade de Equipes', 2, 40, '3'),
    ('GRR', 'GRR', 'Georreferenciamento', 3, 60, '3'),
    ('QAN', 'QAN', 'Química Analítica', 3, 60, '3'),
    ('MIC', 'MIC', 'Microbiologia Ambiental', 2, 40, '3'),
    ('QOR', 'QOR', 'Química Orgânica Ambiental', 2, 40, '3'),
    ('LAG', 'LAG', 'Limnologia', 2, 40, '3'),
    ('CON', 'CON', 'Controle Poluição da Água', 3, 60, '3'),
    ('EXT2-TGA', 'EXT2', 'Projeto de Extensão 2', 4, 80, '3'),
    # Periodo 4
    ('REC', 'REC', 'Recuperação de Áreas Degradadas', 3, 60, '4'),
    ('CAR', 'CAR', 'Controle da Poluição Atmosférica', 3, 60, '4'),
    ('MGB', 'MGB', 'Manejo e Gerenciamento de Bacias Hidrográficas', 3, 60, '4'),
    ('CSO', 'CSO', 'Controle da Poluição do Solo', 3, 60, '4'),
    ('SPQ', 'SPQ', 'Saúde Pública e a Questão Ambiental', 3, 60, '4'),
    ('LCA', 'LCA', 'Licenciamento, Certificação e Auditoria Ambiental', 5, 100, '4'),
    ('GUC', 'GUC', 'Gestão de Unidades de Conservação', 2, 40, '4'),
    ('EXT3-TGA', 'EXT3', 'Projeto de Extensão 3', 4, 80, '4'),
]

def create_components_and_matrix(disciplinas_data, curso, nome_matriz, unidade=None):
    """Cria componentes curriculares e a matriz com seus vínculos."""
    matriz, m_created = CurriculumMatrix.objects.get_or_create(
        curso=curso,
        nome=nome_matriz,
        defaults={
            'is_vigente': True,
            'periodo_letivo': '2026.1',
            'turno': 'N',
        }
    )
    if unidade and m_created:
        matriz.unidades.add(unidade)
    print(f"    Matriz: {matriz} ({'CRIADA' if m_created else 'já existia'})")
    
    comp_count = 0
    for codigo, sigla, nome, creditos, ch, periodo in disciplinas_data:
        # Criar componente curricular
        componente, _ = CurricularComponent.objects.get_or_create(
            codigo=codigo,
            defaults={
                'nome': nome,
                'carga_horaria_padrao': ch,
                'creditos': creditos,
            }
        )
        
        # Vincular à matriz
        mc, mc_created = MatrixComponent.objects.get_or_create(
            matriz=matriz,
            componente_curricular=componente,
            defaults={
                'codigo': codigo,
                'periodo': f'{periodo}º Período',
                'carga_horaria': ch,
                'creditos': creditos,
                'status': 'SEM_PROFESSOR',
            }
        )
        if mc_created:
            comp_count += 1
    
    print(f"    Componentes vinculados: {comp_count}")
    return matriz

# Criar para ADS
print("  --- ADS ---")
matriz_ads = create_components_and_matrix(ads_disciplinas, curso_ads, 'Matriz ADS 2023', unidade_paracambi)

# Criar para TGA
print("  --- TGA ---")
matriz_tga = create_components_and_matrix(tga_disciplinas, curso_tga, 'Matriz TGA 2023', unidade_paracambi)

# ─────────────────────────────────────────────
# 7. Alocações de Teste
# ─────────────────────────────────────────────
print("\n[7] Criando alocações de teste...")

# Buscar professores de Paracambi com eixo Informática
profs_info = list(Professor.objects.filter(
    unidade_principal=unidade_paracambi,
    materia='INFO',
    status='Ativo'
))

profs_quimica = list(Professor.objects.filter(
    unidade_principal=unidade_paracambi,
    materia='QUIMICA',
    status='Ativo'
))

profs_formacao = list(Professor.objects.filter(
    unidade_principal=unidade_paracambi,
    materia='FORMACAO',
    status='Ativo'
))

profs_saude = list(Professor.objects.filter(
    unidade_principal=unidade_paracambi,
    materia='SAUDE',
    status='Ativo'
))

all_profs = list(Professor.objects.filter(unidade_principal=unidade_paracambi, status='Ativo'))

print(f"    Professores Info: {len(profs_info)}")
print(f"    Professores Química/MA: {len(profs_quimica)}")
print(f"    Professores Formação: {len(profs_formacao)}")
print(f"    Professores Saúde: {len(profs_saude)}")

# Alocar professores de informática nas disciplinas de ADS (1o e 2o período)
ads_components = MatrixComponent.objects.filter(
    matriz=matriz_ads,
    periodo__in=['1º Período', '2º Período']
).select_related('componente_curricular')

alloc_count = 0
prof_idx = 0

for mc in ads_components:
    if profs_info:
        prof = profs_info[prof_idx % len(profs_info)]
        mc.docente = prof
        mc.status = 'COMPLETO'
        mc.save()
        alloc_count += 1
        prof_idx += 1

# Alocar professores de quimica/meio ambiente nas disciplinas de TGA (1o período)
tga_components = MatrixComponent.objects.filter(
    matriz=matriz_tga,
    periodo='1º Período'
).select_related('componente_curricular')

prof_idx = 0
profs_tga = profs_quimica + profs_saude + profs_formacao
for mc in tga_components:
    if profs_tga:
        prof = profs_tga[prof_idx % len(profs_tga)]
        mc.docente = prof
        mc.status = 'COMPLETO'
        mc.save()
        alloc_count += 1
        prof_idx += 1

print(f"    Alocações realizadas: {alloc_count}")

# ─────────────────────────────────────────────
# 8. Criar Alocação Curricular consolidada
# ─────────────────────────────────────────────
print("\n[8] Criando alocações curriculares consolidadas...")
cu_ads = CourseUnit.objects.get(curso=curso_ads, unidade=unidade_paracambi)
cu_tga = CourseUnit.objects.get(curso=curso_tga, unidade=unidade_paracambi)
for cu, turno in [(cu_ads, 'N'), (cu_tga, 'N')]:
    aloc, created = AlocacaoCurricular.objects.get_or_create(
        curso=cu,
        semestre='2026.1',
        turno=turno,
        defaults={
            'unidade': unidade_paracambi,
            'status': 'Rascunho',
        }
    )
    print(f"    {aloc} ({'CRIADA' if created else 'já existia'})")

# ─────────────────────────────────────────────
# Resumo
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("  SEED CONCLUÍDO COM SUCESSO!")
print("=" * 60)
print(f"\n  Unidade: {unidade_paracambi}")
print(f"  Login Coordenador: {email_coord} / {SENHA_PADRAO}")
print(f"  Cursos: {CourseUnit.objects.filter(unidade=unidade_paracambi).count()}")
print(f"  Professores em Paracambi: {Professor.objects.filter(unidade_principal=unidade_paracambi).count()}")
print(f"  Componentes ADS: {MatrixComponent.objects.filter(matriz=matriz_ads).count()}")
print(f"  Componentes TGA: {MatrixComponent.objects.filter(matriz=matriz_tga).count()}")
print(f"  Alocações docentes feitas: {MatrixComponent.objects.filter(docente__isnull=False, matriz__unidades=unidade_paracambi).count()}")
print()
