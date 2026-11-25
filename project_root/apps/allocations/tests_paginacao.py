from html import unescape
from re import DOTALL, search

from django.template.loader import render_to_string
from django.core.paginator import Paginator
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.models import Unidade
from apps.courses.models import Course, CurriculumMatrix, MatrixComponent
from apps.professors.models import ContractType, Professor


class PaginacaoAlocacaoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.unidade = Unidade.objects.create(nome='Unidade da paginação', sigla='UP')
        cls.desup = User.objects.create_user(
            email='paginacao@desup.test', perfil='DESUP', forcar_troca_senha=False,
        )
        cls.coord = User.objects.create_user(
            email='paginacao@unidade.test', perfil='COORDENADOR_UNIDADE',
            unidade=cls.unidade, forcar_troca_senha=False,
        )
        contrato = ContractType.objects.create(nome='Contrato', max_class_hours=20, max_classes=4)
        cls.professor = Professor.objects.create(
            id_funcional='PAG-1', rh_nome='Docente Disponível',
            unidade_principal=cls.unidade, tipo_contrato=contrato,
        )
        for i in range(4):
            curso = Course.objects.create(nome=f'Curso {i}', sigla=f'P{i}')
            matriz = CurriculumMatrix.objects.create(
                curso=curso, nome=f'Matriz {i}', turno='M', is_vigente=True,
            )
            matriz.unidades.add(cls.unidade)
            MatrixComponent.objects.create(
                matriz=matriz, nome_temporario=f'Disciplina {i}', codigo=f'PAG{i}',
                periodo='1', carga_horaria=40,
            )

    def link_paginacao(self, resposta, texto):
        html = resposta.content.decode()
        nav = search(r'<nav\b[^>]*aria-label="Carregamento da lista".*?</nav>', html, flags=DOTALL)
        self.assertIsNotNone(nav)
        # Estes controles e modais são inicializados no carregamento completo;
        # substituir só <main> deixa os novos campos sem seus eventos.
        self.assertIn('hx-boost="false"', nav[0])
        link = search(r'<a\b[^>]*href="([^"]+)"[^>]*>\s*(?:<i[^>]*></i>\s*)?' + texto, nav[0])
        self.assertIsNotNone(link)
        return reverse('alloc_curricular') + unescape(link[1])

    def test_ver_mais_e_anteriores_preservam_campos_e_busca_nos_dois_perfis(self):
        for usuario in (self.desup, self.coord):
            with self.subTest(perfil=usuario.perfil):
                self.client.force_login(usuario)
                primeira = self.client.get(reverse('alloc_curricular'), {'unidade_id': self.unidade.pk})
                self.assertEqual(primeira.status_code, 200)
                self.assertContains(primeira, 'Disciplina 0')
                self.assertNotContains(primeira, 'Disciplina 3')

                segunda = self.client.get(self.link_paginacao(primeira, 'Ver mais'))
                self.assertEqual(segunda.status_code, 200)
                self.assertContains(segunda, 'Disciplina 3')
                self.assertContains(segunda, 'class="ac-input ')
                self.assertContains(segunda, "document.addEventListener('DOMContentLoaded'")
                self.assertContains(segunda, 'id="allocConfirmModal"')

                busca = self.client.get(reverse('buscar_professores'), {
                    'q': 'Disponivel', 'unidade_alocacao': self.unidade.pk,
                })
                self.assertEqual(busca.status_code, 200)
                self.assertEqual([p['id'] for p in busca.json()['results']], [self.professor.pk])

                volta = self.client.get(self.link_paginacao(segunda, 'Anteriores'))
                self.assertEqual(volta.status_code, 200)
                self.assertContains(volta, 'Disciplina 0')

    def test_paginacao_compartilhada_mantem_htmx_por_padrao(self):
        pagina = Paginator(range(4), 3).get_page(1)
        html = render_to_string('partials/pagination.html', {
            'is_paginated': True, 'page_obj': pagina, 'paginator': pagina.paginator,
        })
        self.assertIn('hx-boost="true"', html)
