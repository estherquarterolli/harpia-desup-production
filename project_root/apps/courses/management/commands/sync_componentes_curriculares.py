"""
Sincroniza o catálogo de Componentes Curriculares com a lista oficial da DESUP
(seeds/data/componentes_curriculares.csv). Idempotente: pode ser rodado várias vezes.

Casa componentes já existentes SOMENTE por codigo exato (ex.: uma rodada
anterior parcial ja tenha usado o codigo certo). Nao tenta casar por
nome/carga-horaria contra os registros existentes: nao sabemos ainda o
formato do codigo/nome ja usado em producao, e varios nomes do CSV se
repetem em CHs iguais em series diferentes (ex.: "Estagio Supervisionado"
em TEC_ e LIC_) — um casamento por nome+ch arriscaria fundir dois
componentes REAIS diferentes so por coincidencia.

Por isso, um componente existente que nao bate por codigo exato E que ainda
esta em uso real (MatrixComponent.componente_curricular, on_delete=PROTECT)
NAO e removido nem mesclado — o comando so reporta o vinculo (e uma possivel
correspondencia no CSV por nome+ch, como dica) para revisao manual.
Componentes fora da lista e sem uso real sao removidos normalmente.

Uso:
    python manage.py sync_componentes_curriculares --dry-run
    python manage.py sync_componentes_curriculares
    python manage.py sync_componentes_curriculares --csv "caminho/outro_arquivo.csv"
"""
import csv
import unicodedata
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import ProtectedError

from apps.courses.models import CurricularComponent

DEFAULT_CSV_PATH = Path(settings.BASE_DIR) / "seeds" / "data" / "componentes_curriculares.csv"


def _normalizar(texto):
    texto = (texto or "").strip()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return " ".join(texto.lower().split())


class Command(BaseCommand):
    help = "Sincroniza o catalogo de Componentes Curriculares com o CSV oficial da DESUP."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Mostra o que seria feito, sem alterar o banco.')
        parser.add_argument('--csv', default=str(DEFAULT_CSV_PATH), help='Caminho do CSV (codigo;componente_curricular;ch).')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        prefix = '[DRY-RUN] ' if dry_run else ''
        csv_path = Path(options['csv'])

        if not csv_path.exists():
            raise CommandError(f"Arquivo nao encontrado: {csv_path}")

        linhas_corretas = []  # lista de (codigo, nome, ch), na ordem do CSV
        codigos_vistos = set()
        with open(csv_path, encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                codigo = (row.get('codigo') or '').strip()
                nome = (row.get('componente_curricular') or '').strip()
                ch_raw = (row.get('ch') or '').strip()
                if not codigo or not nome:
                    continue
                if codigo in codigos_vistos:
                    raise CommandError(f"Codigo duplicado no CSV: {codigo}")
                codigos_vistos.add(codigo)
                linhas_corretas.append((codigo, nome, int(float(ch_raw)) if ch_raw else 0))

        if not linhas_corretas:
            raise CommandError(f"Nenhuma linha valida encontrada em {csv_path}")

        # O par (nome, ch) sozinho NAO e unico no CSV: series diferentes (ex.: TEC_ / LIC_)
        # reutilizam nomes genericos ("Estagio Supervisionado", "Disciplina Eletiva 1", ...)
        # nos mesmos niveis de CH. O prefixo do codigo (antes do primeiro "_") e o que
        # distingue as series -- por isso a chave de casamento usa (prefixo, nome, ch).
        chaves_csv = {}
        for codigo, nome, ch in linhas_corretas:
            prefixo = codigo.split('_', 1)[0]
            chave = (prefixo, _normalizar(nome), ch)
            if chave in chaves_csv:
                raise CommandError(
                    f"Colisao (prefixo, nome, ch) no CSV entre {chaves_csv[chave]} e {codigo}: "
                    f"'{nome}' ({ch}h). Ajuste o CSV antes de sincronizar."
                )
            chaves_csv[chave] = codigo

        criados = atualizados = removidos = protegidos = 0
        pks_usados = set()

        with transaction.atomic():
            existentes = list(CurricularComponent.objects.all())
            por_codigo_exato = {c.codigo: c for c in existentes if c.codigo}
            # NOTA: so casa por codigo EXATO (ex.: rodada anterior parcial ja usou o
            # codigo certo). Ainda nao sabemos o formato do codigo/nome dos registros
            # existentes em producao, entao NAO tentamos casar por nome+ch aqui --
            # arriscaria fundir dois componentes REAIS diferentes (ex.: confundir a
            # serie TEC_ com a LIC_) so por coincidirem em nome+carga horaria.
            # Ver `vinculos_matriz` no relatorio de remocao para revisar manualmente.

            self.stdout.write(self.style.WARNING("-- Corrigindo/criando Componentes Curriculares --"))
            for codigo, nome, ch in linhas_corretas:
                existente = None
                candidato = por_codigo_exato.get(codigo)
                if candidato and candidato.pk not in pks_usados:
                    existente = candidato

                creditos = ch // 20  # Regra: creditos = CH total / 20 (divisao inteira)
                if existente:
                    pks_usados.add(existente.pk)
                    if (existente.codigo != codigo or existente.nome != nome
                            or existente.carga_horaria_padrao != ch or existente.creditos != creditos):
                        existente.codigo = codigo
                        existente.nome = nome
                        existente.carga_horaria_padrao = ch
                        existente.creditos = creditos
                        existente.save(update_fields=['codigo', 'nome', 'carga_horaria_padrao', 'creditos'])
                        atualizados += 1
                    else:
                        pass  # ja estava correto, nada a fazer
                else:
                    nova = CurricularComponent.objects.create(
                        codigo=codigo, nome=nome, carga_horaria_padrao=ch, creditos=creditos
                    )
                    pks_usados.add(nova.pk)
                    criados += 1

            self.stdout.write(f"{prefix}Criados: {criados} | Atualizados/corrigidos: {atualizados}")

            self.stdout.write("")
            self.stdout.write(self.style.WARNING("-- Removendo Componentes Curriculares fora da lista --"))
            for comp in CurricularComponent.objects.exclude(pk__in=pks_usados):
                n_vinculos = comp.vinculos_matriz.count()
                if n_vinculos:
                    # Apenas uma DICA informativa (nao aplicada automaticamente): existe
                    # alguma linha no CSV com o mesmo nome+carga horaria? Pode ser o
                    # mesmo componente sob codigo antigo -- ou pode ser coincidencia
                    # (ex.: serie TEC_ vs LIC_). Revisar manualmente antes de mesclar.
                    possiveis = sorted({
                        codigo_csv
                        for (prefixo_csv, nome_csv, ch_csv), codigo_csv in chaves_csv.items()
                        if nome_csv == _normalizar(comp.nome) and ch_csv == comp.carga_horaria_padrao
                    })
                    dica = f" (possivel correspondencia no CSV: {', '.join(possiveis)})" if possiveis else ""
                    self.stdout.write(self.style.ERROR(
                        f"  NAO REMOVIDO (em uso em {n_vinculos} matriz(es)): "
                        f"{comp.codigo or '(sem codigo)'} - {comp.nome} ({comp.carga_horaria_padrao}h){dica}"
                    ))
                    protegidos += 1
                    continue
                self.stdout.write(
                    f"{prefix}Removendo: {comp.codigo or '(sem codigo)'} - {comp.nome} ({comp.carga_horaria_padrao}h)"
                )
                try:
                    comp.delete()
                    removidos += 1
                except ProtectedError:
                    self.stdout.write(self.style.ERROR("  -> NAO REMOVIDO: ainda referenciado."))
                    protegidos += 1

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"{prefix}Concluido. Criados: {criados} | Atualizados: {atualizados} | "
            f"Removidos: {removidos} | Nao removidos (em uso): {protegidos}"
        ))
