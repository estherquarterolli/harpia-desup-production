"""
Management command: import_matrizes

Lê a tabela raw `matrizes_curriculares` (criada via SQL pelo usuário) e
importa os dados para os modelos Django:
  CurriculumMatrix  ←  codigo_matriz
  Course            ←  sigla_curso
  Unidade           ←  sigla_unidade
  CurricularComponent ← codigo_materia + nome_materia
  MatrixComponent   ←  ligação entre matriz e componente

Uso:
  python manage.py import_matrizes
  python manage.py import_matrizes --dry-run   # apenas mostra o que seria feito
"""

import re
from django.core.management.base import BaseCommand
from django.db import connection


def _detect_periodo(codigo_materia: str) -> str:
    """
    Tenta extrair o período letivo do código da matéria.
    Exemplos: '1-HEB' → '1o periodo', '2-FE' → '2o periodo',
              '1ORG' → '1o periodo',  'BDA-I' → ''
    """
    m = re.match(r'^(\d+)[-]', codigo_materia)
    if m:
        return f"{m.group(1)}o periodo"
    m = re.match(r'^(\d+)[A-Z]', codigo_materia)
    if m:
        return f"{m.group(1)}o periodo"
    return ''


class Command(BaseCommand):
    help = "Importa dados da tabela SQL 'matrizes_curriculares' para os modelos Django"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Executa sem salvar nada no banco',
        )

    def handle(self, *args, **options):
        from apps.courses.models import (
            Course, CurricularComponent, CurriculumMatrix, MatrixComponent,
        )
        from apps.core.models import Unidade

        dry_run = options['dry_run']
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY-RUN — nenhuma alteração será salva.\n'))

        # ── 1. Verificar se a tabela existe ──────────────────────────────
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_name = 'matrizes_curriculares'
                )
            """)
            exists = cursor.fetchone()[0]

        if not exists:
            self.stdout.write(self.style.ERROR(
                "Tabela 'matrizes_curriculares' não encontrada no banco de dados.\n"
                "Execute o SQL de criação antes deste comando."
            ))
            return

        # ── 2. Ler todos os registros ────────────────────────────────────
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT codigo_matriz, codigo_materia, sigla_curso, sigla_unidade, nome_materia
                FROM matrizes_curriculares
                ORDER BY codigo_matriz, codigo_materia
            """)
            rows = cursor.fetchall()

        if not rows:
            self.stdout.write(self.style.WARNING('Nenhum dado encontrado em matrizes_curriculares.'))
            return

        self.stdout.write(f'Encontrados {len(rows)} componentes para importar.\n')

        stats = {'matrizes': 0, 'cursos': 0, 'componentes': 0, 'vinculos': 0}

        # ── 3. Agrupar por código de matriz ──────────────────────────────
        matrizes_data: dict = {}
        for codigo_matriz, codigo_materia, sigla_curso, sigla_unidade, nome_materia in rows:
            if codigo_matriz not in matrizes_data:
                matrizes_data[codigo_matriz] = {
                    'sigla_curso': sigla_curso,
                    'sigla_unidade': sigla_unidade,
                    'componentes': [],
                }
            matrizes_data[codigo_matriz]['componentes'].append(
                (codigo_materia, nome_materia)
            )

        # ── 4. Importar ──────────────────────────────────────────────────
        for codigo_matriz, data in matrizes_data.items():
            sigla_curso = data['sigla_curso']
            sigla_unidade = data['sigla_unidade']

            # Course
            if not dry_run:
                course, created = Course.objects.get_or_create(
                    sigla=sigla_curso,
                    defaults={'nome': sigla_curso},
                )
                if created:
                    stats['cursos'] += 1
                    self.stdout.write(f'  -> Curso criado: {sigla_curso}')
            else:
                course = None

            # Unidade
            UNIDADE_SIGLA_MAPPING = {
                'FAETERJ-RIO': 'RIO',
                'FAETERJ-PAR': 'PAR',
                'FAETERJ-PET': 'PET',
                'FAETERJ-BMA': 'BAR',
                'FAETERJ-PADUA': 'PAD',
                'FAETERJ-DCX': 'DUQ',
            }
            unidade_sigla_lookup = UNIDADE_SIGLA_MAPPING.get(sigla_unidade, sigla_unidade)
            try:
                unidade = Unidade.objects.get(sigla=unidade_sigla_lookup)
            except Unidade.DoesNotExist:
                self.stdout.write(self.style.WARNING(
                    f'  [AVISO] Unidade "{sigla_unidade}" (buscada como "{unidade_sigla_lookup}") nao encontrada - pulando matriz {codigo_matriz}'
                ))
                continue

            # CurriculumMatrix
            if not dry_run:
                matriz, created = CurriculumMatrix.objects.get_or_create(
                    nome=codigo_matriz,
                    defaults={
                        'curso': course,
                        'is_vigente': True,
                        'is_rascunho': False,
                    },
                )
                if created:
                    stats['matrizes'] += 1
                    self.stdout.write(f'  -> Matriz criada: {codigo_matriz}')
                if course and not matriz.curso_id:
                    matriz.curso = course
                    matriz.save(update_fields=['curso'])
                # Vincular unidade (M2M)
                matriz.unidades.add(unidade)
            else:
                matriz = None
                self.stdout.write(f'  [dry] Matriz: {codigo_matriz} | Curso: {sigla_curso} | Unidade: {sigla_unidade}')

            # Componentes
            for codigo_materia, nome_materia in data['componentes']:
                if not dry_run:
                    comp, created = CurricularComponent.objects.get_or_create(
                        nome=nome_materia,
                        defaults={
                            'codigo': codigo_materia,
                            'carga_horaria_padrao': 0,
                        },
                    )
                    if not created and comp.codigo != codigo_materia:
                        comp.codigo = codigo_materia
                        comp.save(update_fields=['codigo'])
                    if created:
                        stats['componentes'] += 1

                    # MatrixComponent
                    periodo = _detect_periodo(codigo_materia)
                    mc, mc_created = MatrixComponent.objects.get_or_create(
                        matriz=matriz,
                        componente_curricular=comp,
                        defaults={
                            'codigo': codigo_materia,
                            'periodo': periodo,
                            'carga_horaria': 0,
                            'status': MatrixComponent.StatusChoices.SEM_PROFESSOR,
                        },
                    )
                    if not mc_created and (mc.codigo != codigo_materia or mc.periodo != periodo):
                        # Reimportações devem refletir código/período atualizados da fonte;
                        # status e carga_horária não são tocados pois podem ter sido
                        # ajustados manualmente após a criação (ex: alocação de professor).
                        mc.codigo = codigo_materia
                        mc.periodo = periodo
                        mc.save(update_fields=['codigo', 'periodo'])
                    if mc_created:
                        stats['vinculos'] += 1
                else:
                    self.stdout.write(f'    [dry] Componente: {codigo_materia} — {nome_materia}')

        if not dry_run:
            self.stdout.write(self.style.SUCCESS(
                f'\nImportação concluída!\n'
                f'  Cursos criados:      {stats["cursos"]}\n'
                f'  Matrizes criadas:    {stats["matrizes"]}\n'
                f'  Componentes criados: {stats["componentes"]}\n'
                f'  Vínculos criados:    {stats["vinculos"]}\n'
            ))
        else:
            self.stdout.write(self.style.SUCCESS('Dry-run concluído. Use sem --dry-run para aplicar.'))
