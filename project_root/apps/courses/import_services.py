"""
Importação de Componentes Curriculares por planilha (Excel ou Google Sheets).

Regra do cliente: casa pelo código do componente.
  - Código novo (não existe ainda)  -> cria direto.
  - Código já existente             -> não sobrescreve sozinho; a linha vai
    pra uma tela de confirmação (valor atual x valor da planilha) e só é
    atualizada se o usuário marcar "substituir" pra ela.
"""
import csv
import io
import re
import unicodedata
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from django.core.exceptions import ValidationError

from .models import CurricularComponent


class SpreadsheetImportError(Exception):
    """Erro ao ler/interpretar a planilha (arquivo ou URL), antes de processar linhas."""


@dataclass
class RowPreview:
    row_number: int
    codigo: str
    nome: str
    carga_horaria_padrao: object = None
    creditos: int = 0
    obrigatoria: bool = True
    ementa: str = ""
    status: str = "new"  # 'new' | 'duplicate' | 'error'
    message: str = ""
    existing: dict = None  # snapshot dos valores atuais, só quando status == 'duplicate'


@dataclass
class ImportSummary:
    outcomes: list = field(default_factory=list)

    @property
    def added(self):
        return [o for o in self.outcomes if o.status == 'added']

    @property
    def replaced(self):
        return [o for o in self.outcomes if o.status == 'replaced']

    @property
    def skipped(self):
        return [o for o in self.outcomes if o.status == 'skipped']

    @property
    def errors(self):
        return [o for o in self.outcomes if o.status == 'error']


def _normalize_header(h):
    """'Carga Horária Padrão' -> 'carga_horaria_padrao' (sem acento, minúsculo, _)."""
    h = str(h or "").strip()
    h = unicodedata.normalize("NFKD", h).encode("ascii", "ignore").decode("ascii")
    h = h.lower()
    h = re.sub(r"[^a-z0-9]+", "_", h).strip("_")
    return h

# múltiplos nomes de coluna aceitos, todos já normalizados por _normalize_header
_HEADER_ALIASES = {
    "codigo": "codigo",
    "código": "codigo",
    "cod": "codigo",
    "nome": "nome",
    "componente": "nome",
    "carga_horaria": "carga_horaria_padrao",
    "carga_horaria_padrao": "carga_horaria_padrao",
    "ch": "carga_horaria_padrao",
    "creditos": "creditos",
    "obrigatoria": "obrigatoria",
    "obrigatorio": "obrigatoria",
    "ementa": "ementa",
}

_TRUE_TOKENS = {"sim", "s", "true", "1", "x", "obrigatoria", "obrigatorio", "yes"}
_FALSE_TOKENS = {"nao", "não", "n", "false", "0", "optativa", "optativo", "no"}


def _parse_bool(value, default=True):
    if value is None or str(value).strip() == "":
        return default
    token = _normalize_header(value)
    if token in _TRUE_TOKENS:
        return True
    if token in _FALSE_TOKENS:
        return False
    return default


def _rows_from_matrix(header_row, data_rows):
    """header_row: lista de células do cabeçalho. data_rows: iterável de listas de células."""
    normalized = [_normalize_header(h) for h in header_row]
    mapped = [_HEADER_ALIASES.get(h) for h in normalized]

    if "nome" not in mapped:
        raise SpreadsheetImportError(
            "A planilha precisa de uma coluna 'Nome' (não encontrei essa coluna no cabeçalho)."
        )

    rows = []
    for raw in data_rows:
        row = {}
        for idx, field_name in enumerate(mapped):
            if not field_name or idx >= len(raw):
                continue
            value = raw[idx]
            row[field_name] = "" if value is None else value
        # ignora linhas totalmente vazias
        if any(str(v).strip() for v in row.values()):
            rows.append(row)
    return rows


def parse_uploaded_spreadsheet(uploaded_file):
    """Lê um .xlsx enviado por upload e devolve list[dict] (uma linha = um componente)."""
    try:
        from openpyxl import load_workbook
    except ImportError as e:
        raise SpreadsheetImportError("Suporte a Excel indisponível no servidor (openpyxl não instalado).") from e

    try:
        wb = load_workbook(filename=io.BytesIO(uploaded_file.read()), read_only=True, data_only=True)
    except Exception as e:
        raise SpreadsheetImportError(f"Não consegui abrir o arquivo como planilha Excel (.xlsx): {e}") from e

    ws = wb.active
    rows_iter = ws.iter_rows(values_only=True)
    try:
        header_row = next(rows_iter)
    except StopIteration:
        raise SpreadsheetImportError("A planilha está vazia.")

    return _rows_from_matrix(header_row, rows_iter)


def _google_sheets_csv_url(url):
    """Converte um link normal do Google Sheets (edit#gid=...) na URL de export CSV.

    Só funciona pra planilha compartilhada como 'Qualquer pessoa com o link
    pode visualizar' — não há OAuth configurado neste projeto para acessar
    planilhas privadas.
    """
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url)
    if not m:
        raise SpreadsheetImportError(
            "Não reconheci esse link como um link do Google Sheets "
            "(esperado algo como https://docs.google.com/spreadsheets/d/ID/edit)."
        )
    sheet_id = m.group(1)
    gid_match = re.search(r"[?&#]gid=(\d+)", url)
    gid = gid_match.group(1) if gid_match else "0"
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"


def parse_google_sheets_url(url):
    """Baixa uma planilha pública do Google Sheets como CSV e devolve list[dict]."""
    csv_url = _google_sheets_csv_url(url)
    try:
        with urllib.request.urlopen(csv_url, timeout=15) as resp:
            content_type = resp.headers.get("Content-Type", "")
            if "text/csv" not in content_type and "text/plain" not in content_type:
                raise SpreadsheetImportError(
                    "O link não retornou uma planilha em CSV — confirme que o compartilhamento está "
                    "como 'Qualquer pessoa com o link pode visualizar'."
                )
            raw = resp.read().decode("utf-8-sig")
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise SpreadsheetImportError(
                "Sem permissão para ler essa planilha — mude o compartilhamento para "
                "'Qualquer pessoa com o link pode visualizar' e tente de novo."
            ) from e
        raise SpreadsheetImportError(f"Não consegui baixar a planilha do Google Sheets (HTTP {e.code}).") from e
    except urllib.error.URLError as e:
        raise SpreadsheetImportError(f"Não consegui acessar o Google Sheets: {e.reason}") from e

    reader = csv.reader(io.StringIO(raw))
    try:
        header_row = next(reader)
    except StopIteration:
        raise SpreadsheetImportError("A planilha está vazia.")

    return _rows_from_matrix(header_row, reader)


def _clean_row(row, row_number):
    """Normaliza uma linha crua (dict de células) pros tipos certos. Devolve um RowPreview
    com status='error' se faltar algo obrigatório, sem tocar no banco."""
    codigo = str(row.get("codigo", "")).strip()
    nome = str(row.get("nome", "")).strip()

    if not nome:
        return RowPreview(row_number, codigo, nome, status="error", message="Sem nome — linha ignorada.")

    carga_raw = row.get("carga_horaria_padrao", "")
    try:
        carga_horaria_padrao = int(float(str(carga_raw).replace(",", "."))) if str(carga_raw).strip() else None
    except ValueError:
        carga_horaria_padrao = None
    if not carga_horaria_padrao or carga_horaria_padrao <= 0:
        return RowPreview(
            row_number, codigo, nome, status="error",
            message="Carga horária padrão ausente ou inválida — linha ignorada.",
        )

    creditos_raw = row.get("creditos", "")
    try:
        creditos = int(float(str(creditos_raw).replace(",", "."))) if str(creditos_raw).strip() else 0
    except ValueError:
        creditos = 0

    return RowPreview(
        row_number=row_number,
        codigo=codigo,
        nome=nome,
        carga_horaria_padrao=carga_horaria_padrao,
        creditos=max(creditos, 0),
        obrigatoria=_parse_bool(row.get("obrigatoria"), default=True),
        ementa=str(row.get("ementa", "") or "").strip(),
        status="new",
    )


def preview_import(rows):
    """Lê as linhas da planilha e classifica cada uma (new/duplicate/error) sem gravar nada."""
    existing_by_codigo = {
        c.codigo: c
        for c in CurricularComponent.objects.exclude(codigo="")
    }

    previews = []
    for i, row in enumerate(rows, start=2):  # linha 1 é o cabeçalho
        preview = _clean_row(row, i)
        if preview.status == "error":
            previews.append(preview)
            continue

        existing = existing_by_codigo.get(preview.codigo) if preview.codigo else None
        if existing:
            preview.status = "duplicate"
            preview.existing = {
                "nome": existing.nome,
                "carga_horaria_padrao": existing.carga_horaria_padrao,
                "creditos": existing.creditos,
                "obrigatoria": existing.obrigatoria,
                "ementa": existing.ementa,
            }
        previews.append(preview)

    return previews


def apply_import(previews, replace_codigos):
    """Grava no banco: 'new' sempre cria; 'duplicate' só atualiza se o código
    estiver em replace_codigos (marcado pelo usuário na tela de confirmação),
    senão fica 'skipped'. 'error' nunca é tocado."""
    replace_codigos = set(replace_codigos or [])
    summary = ImportSummary()

    for p in previews:
        if p.status == "error":
            summary.outcomes.append(p)
            continue

        if p.status == "duplicate":
            if p.codigo not in replace_codigos:
                p.status = "skipped"
                p.message = "Mantido como estava (não marcado para substituição)."
                summary.outcomes.append(p)
                continue
            try:
                componente = CurricularComponent.objects.get(codigo=p.codigo)
                componente.nome = p.nome
                componente.carga_horaria_padrao = p.carga_horaria_padrao
                componente.creditos = p.creditos
                componente.obrigatoria = p.obrigatoria
                componente.ementa = p.ementa
                componente.full_clean()
                componente.save()
            except (ValidationError, CurricularComponent.DoesNotExist) as e:
                p.status = "error"
                p.message = "; ".join(e.messages) if isinstance(e, ValidationError) else "Componente não encontrado ao salvar."
                summary.outcomes.append(p)
                continue
            except Exception as e:
                p.status = "error"
                p.message = str(e)
                summary.outcomes.append(p)
                continue
            p.status = "replaced"
            summary.outcomes.append(p)
            continue

        # status == 'new'
        componente = CurricularComponent(
            nome=p.nome,
            codigo=p.codigo,
            carga_horaria_padrao=p.carga_horaria_padrao,
            creditos=p.creditos,
            obrigatoria=p.obrigatoria,
            ementa=p.ementa,
        )
        try:
            componente.full_clean()
            componente.save()
        except ValidationError as e:
            p.status = "error"
            p.message = "; ".join(e.messages)
            summary.outcomes.append(p)
            continue
        except Exception as e:
            p.status = "error"
            p.message = str(e)
            summary.outcomes.append(p)
            continue
        p.status = "added"
        summary.outcomes.append(p)

    return summary
