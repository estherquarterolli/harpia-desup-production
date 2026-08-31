"""
Sincroniza Unidades, Cursos e o vínculo Unidade x Curso (CourseUnit) com a
lista oficial repassada pela DESUP. Idempotente: pode ser rodado várias vezes.

IMPORTANTE: casa registros já existentes por sigla OU por nome normalizado
(removendo prefixos como "FAETEC "/"FAETERJ "/"Tecnologia em "/
"Licenciatura em " e acentuação) antes de decidir criar ou remover — isso
evita criar duplicatas vazias e apagar em cascata professores/pendências/
matrizes reais só porque a sigla antiga era diferente da nova.

Escopo desta rodada (revisado manualmente em produção antes de codificar):
  - Corrige sigla/nome das 11 unidades já existentes que batem com a lista
    (por sigla ou nome) e cria "Fernando Mota" (nova).
  - NÃO remove FAETERJ Rio de Janeiro / FAETERJ Volta Redonda / GAIO nesta
    rodada (fora da lista, mas deixados para revisão manual posterior).
  - Remove 3 Cursos "placeholder" (nome literalmente igual à sigla: PED,
    TPG, TSI) cujas Matrizes de 2024 não têm CourseUnit nem docente alocado
    (confirmado substituído pelas matrizes atuais MC-LEP/MC-PG/MC-SPI-2026.1).
  - NÃO remove os Cursos "PW" (Programação para Web) e "TIC" (Tecnologia da
    Informação e da Comunicação) nesta rodada — fora da lista de 7 cursos,
    mas com matrizes que ainda não foram revisadas.
  - Remove apenas os vínculos CourseUnit incorretos das unidades desta
    rodada (ex.: Petrópolis deixa de apontar para TIC); não mexe em
    vínculos de unidades fora do escopo (Rio de Janeiro, Volta Redonda, GAIO).

Uso:
    python manage.py sync_unidades_cursos --dry-run
    python manage.py sync_unidades_cursos
"""
import unicodedata

from django.core.management.base import BaseCommand
from django.db import models, transaction
from django.db.models import ProtectedError

from apps.core.models import Unidade
from apps.courses.models import Course, CourseUnit, MatrixComponent

# (nome_unidade, sigla_unidade, nome_curso)
DADOS_CORRETOS = [
    ("Bom Jesus do Itabapoana", "BJI", "Pedagogia"),
    ("ISEPAM", "ISEPAM", "Pedagogia"),
    ("ISERJ", "ISERJ", "Pedagogia"),
    ("Itaperuna", "ITA", "Pedagogia"),
    ("Santo Antônio de Pádua", "SAP", "Pedagogia"),
    ("Três Rios", "TRS", "Pedagogia"),
    ("Fernando Mota", "FMO", "Tecnologia em Análise e Desenvolvimento de Sistemas"),
    ("Paracambi", "PRC", "Tecnologia em Análise e Desenvolvimento de Sistemas"),
    ("Petrópolis", "PTR", "Tecnologia em Análise e Desenvolvimento de Sistemas"),
    ("Paracambi", "PRC", "Tecnologia em Gestão Ambiental"),
    ("Campos dos Goytacazes", "CGO", "Tecnologia em Gestão Portuária"),
    ("Barra Mansa", "BRM", "Tecnologia em Logística"),
    ("Três Rios", "TRS", "Tecnologia em Logística"),
    ("Duque de Caxias", "DCX", "Tecnologia em Processos Gerenciais"),
    ("Barra Mansa", "BRM", "Tecnologia em Sistemas para Internet"),
]

# Siglas de curso não foram informadas pela DESUP — escolhidas aqui de forma
# consistente. Ajuste este dicionário se já existir uma sigla oficial.
CURSO_SIGLAS = {
    "Pedagogia": "PED",
    "Tecnologia em Análise e Desenvolvimento de Sistemas": "ADS",
    "Tecnologia em Gestão Ambiental": "TGA",
    "Tecnologia em Gestão Portuária": "TGP",
    "Tecnologia em Logística": "LOG",
    "Tecnologia em Processos Gerenciais": "TPG",
    "Tecnologia em Sistemas para Internet": "TSI",
}

PREFIXOS_UNIDADE = ("FAETEC ", "FAETERJ ")
PREFIXOS_CURSO = ("Tecnologia em ", "Licenciatura em ")


def _normalizar(texto, prefixos=()):
    texto = (texto or "").strip()
    for p in prefixos:
        if texto.lower().startswith(p.lower()):
            texto = texto[len(p):]
            break
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return texto.strip().lower()


class Command(BaseCommand):
    help = "Sincroniza Unidades e Cursos com a lista oficial da DESUP (corrige por nome, nao duplica)."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Mostra o que seria feito, sem alterar o banco.')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        prefix = '[DRY-RUN] ' if dry_run else ''

        unidades_corretas = {sigla: nome for nome, sigla, _ in DADOS_CORRETOS}
        cursos_corretos = {}
        combos_corretos = set()
        for nome_unidade, sigla_unidade, nome_curso in DADOS_CORRETOS:
            cursos_corretos[nome_curso] = CURSO_SIGLAS[nome_curso]
            combos_corretos.add((sigla_unidade, CURSO_SIGLAS[nome_curso]))

        with transaction.atomic():
            # ── 0) Limpeza dos Cursos placeholder (nome == sigla), sem uso real ──
            self.stdout.write(self.style.WARNING("-- Limpando Cursos placeholder (nome == sigla, sem uso real) --"))
            for curso in list(Course.objects.filter(nome=models.F('sigla'))):
                tem_courseunit = curso.course_units.exists()
                tem_docente = MatrixComponent.objects.filter(matriz__curso=curso).exclude(docente=None).exists()
                if tem_courseunit or tem_docente:
                    self.stdout.write(self.style.ERROR(
                        f"  PULADO (tem uso real, nao e placeholder): {curso.sigla} - {curso.nome}"
                    ))
                    continue
                self.stdout.write(
                    f"{prefix}Removendo Curso placeholder: {curso.sigla} "
                    f"(matrizes vinculadas: {curso.matrizes.count()}, todas sem CourseUnit/docente)"
                )
                # Sempre executa de verdade (mesmo em --dry-run): o rollback no final desfaz
                # tudo. Pular a exclusao aqui faria o passo 2 (casar Cursos) encontrar esse
                # mesmo placeholder em vez de cair no fallback por nome (ex.: LICPED).
                curso.delete()

            # ── 1) Unidades: casar por sigla ou nome normalizado; corrigir ou criar ──
            pks_unidade_usados = set()
            unidade_por_sigla_correta = {}

            def achar_unidade(nome_correto, sigla_correto):
                candidatos = Unidade.objects.exclude(pk__in=pks_unidade_usados)
                for u in candidatos:
                    if u.sigla == sigla_correto:
                        return u
                alvo = _normalizar(nome_correto, PREFIXOS_UNIDADE)
                for u in candidatos:
                    if _normalizar(u.nome, PREFIXOS_UNIDADE) == alvo:
                        return u
                return None

            self.stdout.write("")
            self.stdout.write(self.style.WARNING("-- Corrigindo/criando Unidades --"))
            for sigla_correto, nome_correto in unidades_corretas.items():
                existente = achar_unidade(nome_correto, sigla_correto)
                if existente:
                    pks_unidade_usados.add(existente.pk)
                    if existente.sigla != sigla_correto or existente.nome != nome_correto or not existente.status:
                        self.stdout.write(
                            f"{prefix}Corrigindo Unidade: '{existente.sigla} - {existente.nome}' "
                            f"-> '{sigla_correto} - {nome_correto}'"
                        )
                        existente.sigla = sigla_correto
                        existente.nome = nome_correto
                        existente.status = True
                        existente.save(update_fields=['sigla', 'nome', 'status'])
                    else:
                        self.stdout.write(f"{prefix}OK: Unidade {sigla_correto} - {nome_correto}")
                    unidade_por_sigla_correta[sigla_correto] = existente
                else:
                    self.stdout.write(f"{prefix}Criando Unidade: {sigla_correto} - {nome_correto}")
                    nova = Unidade.objects.create(sigla=sigla_correto, nome=nome_correto, status=True)
                    unidade_por_sigla_correta[sigla_correto] = nova
                    pks_unidade_usados.add(nova.pk)

            # ── 2) Cursos: casar por sigla ou nome normalizado; corrigir ou criar ──
            pks_curso_usados = set()
            curso_por_nome_correto = {}

            def achar_curso(nome_correto, sigla_correto):
                candidatos = Course.objects.exclude(pk__in=pks_curso_usados)
                for c in candidatos:
                    if c.sigla == sigla_correto:
                        return c
                alvo = _normalizar(nome_correto, PREFIXOS_CURSO)
                for c in candidatos:
                    if _normalizar(c.nome, PREFIXOS_CURSO) == alvo:
                        return c
                return None

            self.stdout.write("")
            self.stdout.write(self.style.WARNING("-- Corrigindo/criando Cursos --"))
            for nome_correto, sigla_correto in cursos_corretos.items():
                existente = achar_curso(nome_correto, sigla_correto)
                if existente:
                    pks_curso_usados.add(existente.pk)
                    if existente.sigla != sigla_correto or existente.nome != nome_correto:
                        self.stdout.write(
                            f"{prefix}Corrigindo Curso: '{existente.sigla} - {existente.nome}' "
                            f"-> '{sigla_correto} - {nome_correto}'"
                        )
                        existente.sigla = sigla_correto
                        existente.nome = nome_correto
                        existente.save(update_fields=['sigla', 'nome'])
                    else:
                        self.stdout.write(f"{prefix}OK: Curso {sigla_correto} - {nome_correto}")
                    curso_por_nome_correto[nome_correto] = existente
                else:
                    self.stdout.write(f"{prefix}Criando Curso: {sigla_correto} - {nome_correto}")
                    curso_por_nome_correto[nome_correto] = Course.objects.create(
                        sigla=sigla_correto, nome=nome_correto,
                    )

            # ── 3) CourseUnit: criar as combinacoes corretas ──
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("-- Criando vinculos Unidade x Curso --"))
            for nome_unidade, sigla_unidade, nome_curso in DADOS_CORRETOS:
                unidade = unidade_por_sigla_correta[sigla_unidade]
                curso = curso_por_nome_correto[nome_curso]
                _, created = CourseUnit.objects.get_or_create(curso=curso, unidade=unidade)
                if created:
                    self.stdout.write(f"{prefix}Criado vinculo: {unidade.sigla} x {curso.sigla}")

            # ── 4) Remove vinculos incorretos, mas apenas para as unidades desta rodada ──
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("-- Removendo vinculos incorretos (apenas unidades desta rodada) --"))
            siglas_geridas = set(unidades_corretas.keys())
            for cu in CourseUnit.objects.select_related('curso', 'unidade').all():
                if cu.unidade.sigla not in siglas_geridas:
                    continue  # unidade fora do escopo desta rodada (ex.: Rio de Janeiro, Volta Redonda, GAIO)
                if (cu.unidade.sigla, cu.curso.sigla) not in combos_corretos:
                    self.stdout.write(f"{prefix}Removendo vinculo incorreto: {cu.unidade.sigla} x {cu.curso.sigla}")
                    cu.delete()

            # ── 5) Relatorio: Unidades fora da lista, deixadas para revisao manual ──
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("-- Unidades fora da lista (NAO removidas nesta rodada) --"))
            for unidade in Unidade.objects.exclude(pk__in=pks_unidade_usados):
                self.stdout.write(
                    f"  {unidade.sigla} - {unidade.nome} "
                    f"(professores: {unidade.professores.count()}, "
                    f"pendencias: {unidade.pendencias_extra.count()}, "
                    f"alocacoes: {unidade.alocacoes_consolidadas.count()})"
                )

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"{prefix}Concluido."))
