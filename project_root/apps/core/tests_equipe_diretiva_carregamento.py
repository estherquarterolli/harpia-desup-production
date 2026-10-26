from datetime import timedelta
from decimal import Decimal

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.courses.models import Course, CourseUnit
from apps.professors.models import ContractType, Professor

from .models import OcupacaoEquipeDiretiva, TipoCargoDiretivo, Unidade


class EquipeDiretivaCarregamentoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.unidade = Unidade.objects.create(nome='Unidade de desempenho', sigla='UD')
        cls.outra = Unidade.objects.create(nome='Outra unidade', sigla='OU')
        cls.desup = User.objects.create_user(email='carga@desup.test', perfil=User.Perfil.DESUP, forcar_troca_senha=False)
        cls.coord = User.objects.create_user(
            email='carga@unidade.test', perfil=User.Perfil.COORDENADOR_UNIDADE,
            unidade=cls.unidade, forcar_troca_senha=False,
        )
        contrato = ContractType.objects.create(nome='Contrato de desempenho', max_class_hours=20, max_classes=8)
        cls.prof = Professor.objects.create(
            id_funcional='PERF-ID', rh_matricula='PERF-MAT', rh_nome='Professor Local',
            tipo_contrato=contrato, unidade_principal=cls.unidade,
        )
        cls.prof_externo = Professor.objects.create(
            id_funcional='EXT-ID', rh_matricula='EXT-MAT', rh_nome='Professor Externo',
            tipo_contrato=contrato, unidade_principal=cls.outra,
        )
        cls.curso = CourseUnit.objects.create(
            curso=Course.objects.create(nome='Curso Local', sigla='CL'), unidade=cls.unidade,
        )
        cls.curso_externo = CourseUnit.objects.create(
            curso=Course.objects.create(nome='Curso Externo', sigla='CE'), unidade=cls.outra,
        )
        cls.cargo = TipoCargoDiretivo.objects.create(nome='Cargo de desempenho', exige_curso=True, permite_multiplos=True)

    def medir(self, user, **params):
        self.client.force_login(user)
        nome = 'core:equipe_diretiva_desup' if user == self.desup else 'core:equipe_diretiva_unidade'
        if user == self.desup:
            params['unidade_id'] = self.unidade.pk
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse(nome), params)
        self.assertEqual(response.status_code, 200)
        return response, len(queries)

    def test_consultas_nao_crescem_com_cargos_e_ocupantes_nos_dois_perfis(self):
        OcupacaoEquipeDiretiva.objects.create(
            cargo=self.cargo, unidade=self.unidade, professor=self.prof, curso=self.curso,
            data_inicio=timezone.localdate(), carga_reducao_horas=Decimal('2'),
        )
        iniciais = {user.pk: self.medir(user)[1] for user in (self.desup, self.coord)}
        for i in range(10):
            cargo = TipoCargoDiretivo.objects.create(nome=f'Cargo adicional {i}', exige_curso=True, permite_multiplos=True)
            OcupacaoEquipeDiretiva.objects.create(
                cargo=cargo, unidade=self.unidade, professor=self.prof, curso=self.curso,
                data_inicio=timezone.localdate(), carga_reducao_horas=Decimal('2'),
            )
        for user in (self.desup, self.coord):
            with self.subTest(perfil=user.perfil):
                response, total = self.medir(user)
                self.assertEqual(total, iniciais[user.pk], f'{user.perfil}: {iniciais[user.pk]} -> {total} consultas')
                form = response.context['composicao'][0]['form']
                self.assertEqual([str(label) for value, label in form.fields['professor'].choices if value], [str(self.prof)])
                self.assertEqual([str(label) for value, label in form.fields['curso'].choices if value], [str(self.curso)])

    def test_desup_sem_unidade_nao_carrega_catalogo_ou_ocupantes(self):
        self.client.force_login(self.desup)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse('core:equipe_diretiva_desup'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['composicao'], [])
        self.assertFalse(any('harpiadb_nucleo_tipo_cargo_diretivo' in q['sql'] for q in queries))

    def test_listas_compartilhadas_nao_vazam_entre_requisicoes_de_unidades_distintas(self):
        self.medir(self.desup)
        response = self.client.get(reverse('core:equipe_diretiva_desup'), {'unidade_id': self.outra.pk})
        form = response.context['composicao'][0]['form']
        self.assertEqual([value for value, label in form.fields['professor'].choices if value], [self.prof_externo.pk])
        self.assertEqual([value for value, label in form.fields['curso'].choices if value], [self.curso_externo.pk])

    def test_historico_parcial_do_coordenador_nao_reconstroi_composicao_e_formularios(self):
        OcupacaoEquipeDiretiva.objects.create(
            cargo=self.cargo, unidade=self.unidade, professor=self.prof, curso=self.curso,
            data_inicio=timezone.localdate() - timedelta(days=10),
            data_fim=timezone.localdate() - timedelta(days=1),
        )
        self.client.force_login(self.coord)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse('core:equipe_diretiva_unidade'), {'partial': 'historico'}, HTTP_HX_REQUEST='true')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.prof.nome)
        self.assertNotIn('composicao', response.context)
        self.assertFalse(any('FROM "harpiadb_professores_professor"' in q['sql'] for q in queries))

    def test_historico_desup_paginado_preserva_unidade_e_composicao(self):
        OcupacaoEquipeDiretiva.objects.bulk_create([
            OcupacaoEquipeDiretiva(
                cargo=self.cargo, unidade=self.unidade, professor=self.prof, curso=self.curso,
                data_inicio=timezone.localdate() - timedelta(days=20),
                data_fim=timezone.localdate() - timedelta(days=1), observacoes=f'Histórico {i}',
            ) for i in range(35)
        ])
        OcupacaoEquipeDiretiva.objects.create(
            cargo=self.cargo, unidade=self.unidade, professor=self.prof, curso=self.curso,
            data_inicio=timezone.localdate(), carga_reducao_horas=Decimal('7'),
        )
        response, _ = self.medir(self.desup, historico_page='2')
        self.assertEqual(len(response.context['historico']), 15)
        self.assertEqual(response.context['historico_page_obj'].paginator.count, 35)
        self.assertEqual(response.context['reducao_total'], Decimal('7'))
        self.assertContains(response, f'unidade_id={self.unidade.pk}')
