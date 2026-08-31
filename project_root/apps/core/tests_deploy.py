"""
Guardas de configuração de deploy (SEC-003).

Não testam comportamento de view — travam invariantes que, se quebradas, só
aparecem em produção e de forma silenciosa.
"""
import io
import re
from pathlib import Path

from django.test import TestCase

BASE = Path(__file__).resolve().parent.parent.parent  # .../project_root
RAIZ_REPO = BASE.parent


def _ler(caminho):
    return io.open(caminho, encoding="utf-8").read()


class SettingsModuleDeDeployTests(TestCase):
    """
    `wsgi.py`/`asgi.py` são importados apenas por servidor de aplicação
    (gunicorn/uvicorn). O default deles precisa ser o settings de **produção**:
    com o default de development, um deploy que não exportasse
    `DJANGO_SETTINGS_MODULE` subia com `DEBUG=True` e `ALLOWED_HOSTS=['*']` — e
    o `Procfile` não exportava (só o `render.yaml` define).
    """

    def test_wsgi_e_asgi_apontam_para_producao(self):
        for modulo in ("wsgi.py", "asgi.py"):
            with self.subTest(modulo=modulo):
                conteudo = _ler(BASE / "config" / modulo)
                self.assertIn("'config.settings.production'", conteudo)
                self.assertNotIn("'config.settings.development'", conteudo)

    def test_manage_py_continua_em_development(self):
        """O manage.py é a porta de entrada do desenvolvimento local — não muda."""
        conteudo = _ler(BASE / "manage.py")
        self.assertIn("'config.settings.development'", conteudo)

    def test_procfile_declara_o_settings_explicitamente(self):
        """Defesa em profundidade: não depender do default do wsgi/manage."""
        conteudo = _ler(RAIZ_REPO / "Procfile")
        linhas = [ln for ln in conteudo.splitlines() if ln.strip()]
        self.assertTrue(linhas, "Procfile vazio")
        for linha in linhas:
            with self.subTest(linha=linha.split(":", 1)[0]):
                self.assertIn("DJANGO_SETTINGS_MODULE=config.settings.production", linha)


class ProducaoNaoLigaDebugTests(TestCase):
    """`DEBUG` em produção precisa ser constante no código, não vir de env."""

    def test_production_fixa_debug_false(self):
        conteudo = _ler(BASE / "config" / "settings" / "production.py")
        self.assertIsNotNone(
            re.search(r"^DEBUG\s*=\s*False\s*$", conteudo, re.M),
            "production.py precisa fixar DEBUG = False",
        )

    def test_production_nao_le_debug_de_env(self):
        conteudo = _ler(BASE / "config" / "settings" / "production.py")
        self.assertIsNone(
            re.search(r"DEBUG\s*=\s*config\(", conteudo),
            "DEBUG em produção não pode vir de variável de ambiente",
        )
