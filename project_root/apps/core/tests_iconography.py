import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


# Vocabulário visual canônico da aplicação. Variações de tamanho e cor
# continuam livres; o glifo que comunica cada entidade/ação deve ser único.
CANONICAL_ICONS = {
    'professor/docente': 'ph-chalkboard-teacher',
    'unidade': 'ph-buildings',
    'curso': 'ph-graduation-cap',
    'matriz': 'ph-file-text',
    'componente curricular': 'ph-book-open',
    'adicionar/novo item': 'ph-plus-circle',
    'editar': 'ph-pencil-simple',
    'excluir/remover': 'ph-trash',
    'salvar': 'ph-floppy-disk',
    'importar planilha': 'ph-file-arrow-up',
    'alerta': 'ph-warning-circle',
    'voltar': 'ph-arrow-left',
    'carregando': 'ph-circle-notch',
}


# Aliases que já causaram divergência visual. O teste obriga qualquer mudança
# futura no vocabulário a ser deliberada, em vez de surgir isolada numa página.
NON_CANONICAL_ALIASES = {
    'ph-user-minus': CANONICAL_ICONS['professor/docente'],
    'ph-user-list': CANONICAL_ICONS['professor/docente'],
    'ph-users': CANONICAL_ICONS['professor/docente'],
    'ph-folder-open': CANONICAL_ICONS['professor/docente'],
    'ph-tree-structure': CANONICAL_ICONS['unidade'],
    'ph-table': CANONICAL_ICONS['matriz'],
    'ph-file-dashed': CANONICAL_ICONS['matriz'],
    'ph-list-bullets': CANONICAL_ICONS['componente curricular'],
    'ph-plus': CANONICAL_ICONS['adicionar/novo item'],
    'ph-pencil': CANONICAL_ICONS['editar'],
    'ph-warning': CANONICAL_ICONS['alerta'],
    'ph-caret-left': CANONICAL_ICONS['voltar'],
    'ph-upload-simple': CANONICAL_ICONS['importar planilha'],
    'ph-file-xls': CANONICAL_ICONS['importar planilha'],
    'ph-spinner': CANONICAL_ICONS['carregando'],
    'ph-seal-check': 'ph-check-circle',
}


class IconographyConsistencyTests(SimpleTestCase):
    @staticmethod
    def _templates():
        return (Path(settings.BASE_DIR) / 'templates').rglob('*.html')

    def test_templates_nao_reintroduzem_aliases_de_icones(self):
        templates_dir = Path(settings.BASE_DIR) / 'templates'
        token_pattern = re.compile(r'(?<![\w-])ph-[a-z0-9-]+(?![\w-])')
        violations = []

        for template in self._templates():
            content = template.read_text(encoding='utf-8')
            tokens = set(token_pattern.findall(content))
            for alias in sorted(tokens & NON_CANONICAL_ALIASES.keys()):
                violations.append(
                    f'{template.relative_to(templates_dir)}: {alias} -> '
                    f'{NON_CANONICAL_ALIASES[alias]}'
                )

        self.assertFalse(
            violations,
            'Foram encontrados ícones fora do vocabulário visual:\n' + '\n'.join(violations),
        )

    def test_mesmo_rotulo_visivel_nao_usa_icones_diferentes(self):
        """Detecta automaticamente frases iguais com glifos diferentes."""
        icon_label_pattern = re.compile(
            r'(?P<tag><i[^>]*\bph ph-(?P<icon>[a-z0-9-]+)[^>]*>)</i>\s*'
            r'(?:<span[^>]*>)?\s*(?P<label>[^<{]+)',
            re.IGNORECASE,
        )
        labels = {}

        for template in self._templates():
            content = template.read_text(encoding='utf-8')
            for match in icon_label_pattern.finditer(content):
                # O caret apenas separa os itens do breadcrumb; ele não
                # representa semanticamente o texto que aparece em seguida.
                if 'breadcrumb-separator' in match.group('tag'):
                    continue
                label = ' '.join(match.group('label').split()).strip(' .:;!-').casefold()
                if not label:
                    continue
                labels.setdefault(label, set()).add(f"ph-{match.group('icon')}")

        inconsistent = {
            label: sorted(icons)
            for label, icons in labels.items()
            if len(icons) > 1
        }
        self.assertFalse(
            inconsistent,
            'O mesmo rótulo visível usa ícones diferentes: ' + repr(inconsistent),
        )
