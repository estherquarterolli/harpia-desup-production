from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.professors.models import ContractType, Professor

from .models import ConfiguracaoCargoDiretivoUnidade, OcupacaoEquipeDiretiva, TipoCargoDiretivo, Unidade
from .services import obter_reducao_cargo_unidade


class CargaCargoUnidadeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hoje = timezone.localdate()
        cls.a = Unidade.objects.create(nome='Unidade A', sigla='UA')
        cls.b = Unidade.objects.create(nome='Unidade B', sigla='UB')
        cls.desup = User.objects.create_user(email='carga@desup.test', perfil=User.Perfil.DESUP, forcar_troca_senha=False)
        cls.coord = User.objects.create_user(
            email='carga@unidade.test', perfil=User.Perfil.COORDENADOR_UNIDADE,
            unidade=cls.a, forcar_troca_senha=False,
        )
        cls.cargo = TipoCargoDiretivo.objects.create(nome='Coordenação', permite_multiplos=True, carga_reducao_horas=Decimal('8'))
        cls.contrato = ContractType.objects.create(nome='Contrato 40h', max_class_hours=20, max_classes=8)
        cls.pa = cls.professor('A', cls.a)
        cls.pb = cls.professor('B', cls.b)

    @classmethod
    def professor(cls, nome, unidade):
        return Professor.objects.create(
            id_funcional=f'ID-{nome}', rh_matricula=f'MAT-{nome}', rh_nome=f'Professor {nome}',
            unidade_principal=unidade, tipo_contrato=cls.contrato,
        )

    def setUp(self):
        self.client.force_login(self.desup)

    def url_editar(self, unidade):
        return reverse('core:cargo_diretivo_unidade_update', args=[unidade.pk, self.cargo.pk])

    def dados(self, horas='12', nome='Coordenação atualizada'):
        return {'nome': nome, 'carga_reducao_unidade': horas, 'permite_multiplos': 'on', 'ativo': 'on'}

    def configurar(self, unidade, horas):
        resposta = self.client.post(self.url_editar(unidade), self.dados(horas))
        self.assertRedirects(resposta, f"{reverse('core:equipe_diretiva_desup')}?unidade_id={unidade.pk}")

    def ocupar(self, unidade, professor, pela_unidade=False):
        nome = 'core:ocupacao_diretiva_unidade_create' if pela_unidade else 'core:ocupacao_diretiva_create'
        args = [self.cargo.pk] if pela_unidade else [unidade.pk, self.cargo.pk]
        response = self.client.post(reverse(nome, args=args), {
            'professor': professor.pk, 'data_inicio': self.hoje.isoformat(),
            'carga_reducao_horas': '99', 'reducao_personalizada': True,
        })
        self.assertEqual(response.status_code, 302)
        return OcupacaoEquipeDiretiva.objects.get(unidade=unidade, professor=professor, cargo=self.cargo)

    def ajustar_individual(self, ocupacao, horas):
        response = self.client.post(reverse('core:ocupacao_diretiva_update', args=[ocupacao.pk]), {
            'carga_reducao_horas': horas, 'observacoes': 'Valor individual explícito.',
        })
        self.assertEqual(response.status_code, 302)

    def painel(self, unidade):
        response = self.client.get(reverse('core:equipe_diretiva_desup'), {'unidade_id': unidade.pk})
        self.assertEqual(response.status_code, 200)
        return response, next(i for i in response.context['composicao'] if i['cargo'].pk == self.cargo.pk)

    def test_a_b_e_edicao_conjunta_isola_cargas_e_persiste_apos_recarregar(self):
        oa = self.ocupar(self.a, self.pa)
        ob = self.ocupar(self.b, self.pb)
        self.configurar(self.a, '12.50')
        ob.refresh_from_db()
        self.assertEqual(ob.carga_reducao_horas, Decimal('8'))
        self.configurar(self.b, '6')
        self.configurar(self.a, '10.25')
        for unidade, ocupacao, valor in ((self.a, oa, '10.25'), (self.b, ob, '6')):
            with self.subTest(unidade=unidade.sigla):
                ocupacao.refresh_from_db()
                pagina, item = self.painel(unidade)
                self.assertEqual(ocupacao.carga_reducao_horas, Decimal(valor))
                self.assertEqual(item['carga_reducao_horas'], Decimal(valor))
                self.assertEqual(item['form_cargo'].initial['carga_reducao_unidade'], Decimal(valor))
                self.assertEqual(item['ocupantes'][0].carga_reducao_horas, Decimal(valor))
                self.assertEqual(pagina.context['reducao_total'], Decimal(valor))
        self.cargo.refresh_from_db()
        self.assertEqual(self.cargo.nome, 'Coordenação atualizada')
        self.assertEqual(self.cargo.carga_reducao_horas, Decimal('8'))
        self.assertEqual(ConfiguracaoCargoDiretivoUnidade.objects.count(), 2)

    def test_c_d_e_individual_zero_e_valor_igual_ao_padrao_sao_preservados(self):
        for valor in ('3.25', '0', '8'):
            with self.subTest(valor=valor):
                OcupacaoEquipeDiretiva.objects.all().delete()
                ConfiguracaoCargoDiretivoUnidade.objects.all().delete()
                ocupacao = self.ocupar(self.a, self.pa)
                self.ajustar_individual(ocupacao, valor)
                self.configurar(self.a, '16')
                ocupacao.refresh_from_db()
                self.assertTrue(ocupacao.reducao_personalizada)
                self.assertEqual(ocupacao.carga_reducao_horas, Decimal(valor))
                self.assertEqual(ocupacao.observacoes, 'Valor individual explícito.')
                pagina, item = self.painel(self.a)
                self.assertEqual(item['carga_reducao_horas'], Decimal('16'))
                self.assertEqual(pagina.context['reducao_total'], Decimal(valor))
                self.assertEqual(self.pa.reducao_carga_vigente, float(valor))

    def test_ocupantes_individuais_e_herdados_coexistem_na_mesma_unidade(self):
        individual = self.ocupar(self.a, self.pa)
        herdado = self.ocupar(self.a, self.professor('Outro', self.a))
        self.ajustar_individual(individual, '4')
        self.configurar(self.a, '14')
        individual.refresh_from_db()
        herdado.refresh_from_db()
        self.assertEqual(individual.carga_reducao_horas, Decimal('4'))
        self.assertEqual(herdado.carga_reducao_horas, Decimal('14'))

    def test_cargas_preexistentes_sao_preservadas_sem_inferir_por_igualdade(self):
        for valor in ('8', '4', '0'):
            ocupacao = OcupacaoEquipeDiretiva.objects.create(
                cargo=self.cargo, unidade=self.a, professor=self.pa,
                data_inicio=self.hoje, carga_reducao_horas=Decimal(valor),
            )
            self.configurar(self.a, '18')
            ocupacao.refresh_from_db()
            self.assertTrue(ocupacao.reducao_personalizada)
            self.assertEqual(ocupacao.carga_reducao_horas, Decimal(valor))

    def test_desup_e_coordenador_preenchem_com_padrao_local_inclusive_zero(self):
        for pela_unidade, valor in ((False, '11.50'), (True, '0')):
            with self.subTest(pela_unidade=pela_unidade):
                OcupacaoEquipeDiretiva.objects.all().delete()
                self.configurar(self.a, valor)
                if pela_unidade:
                    self.client.force_login(self.coord)
                ocupacao = self.ocupar(self.a, self.pa, pela_unidade)
                self.assertEqual(ocupacao.carga_reducao_horas, Decimal(valor))
                self.assertFalse(ocupacao.reducao_personalizada)
                self.client.force_login(self.desup)
                self.configurar(self.a, '7')
                ocupacao.refresh_from_db()
                self.assertEqual(ocupacao.carga_reducao_horas, Decimal('7'))

    def test_coordenador_nao_sobrescreve_reducao_ou_indicador_individual(self):
        ocupacao = self.ocupar(self.a, self.pa)
        self.ajustar_individual(ocupacao, '5')
        self.client.force_login(self.coord)
        response = self.client.post(reverse('core:ocupacao_diretiva_unidade_update', args=[ocupacao.pk]), {
            'professor': self.pa.pk, 'data_inicio': self.hoje.isoformat(),
            'carga_reducao_horas': '99', 'reducao_personalizada': False,
        })
        self.assertEqual(response.status_code, 302)
        self.client.force_login(self.desup)
        self.configurar(self.a, '16')
        ocupacao.refresh_from_db()
        self.assertEqual(ocupacao.carga_reducao_horas, Decimal('5'))
        self.assertTrue(ocupacao.reducao_personalizada)

    def test_modal_editar_contem_metadados_e_reducao_local_no_mesmo_formulario(self):
        self.configurar(self.a, '6.25')
        pagina, _ = self.painel(self.a)
        modal = pagina.content.decode().split(f'id="modalCargo{self.cargo.pk}"')[1].split(f'id="modalDetalhe{self.cargo.pk}"')[0]
        self.assertIn('name="nome"', modal)
        self.assertIn('name="carga_reducao_unidade"', modal)
        self.assertIn('value="6.25"', modal)
        self.assertIn(self.url_editar(self.a), modal)
        self.assertNotContains(pagina, 'modalReducaoCargo')
        response = self.client.get(self.url_editar(self.a))
        self.assertEqual(response.context['form'].initial['carga_reducao_unidade'], Decimal('6.25'))

    def test_post_nao_pode_trocar_escopo_ou_carga_global(self):
        self.client.post(self.url_editar(self.a), {
            **self.dados('12.50'), 'unidade': self.b.pk, 'carga_reducao_horas': '99',
        })
        self.cargo.refresh_from_db()
        self.assertEqual(self.cargo.carga_reducao_horas, Decimal('8'))
        self.assertEqual(obter_reducao_cargo_unidade(self.cargo, self.a), Decimal('12.50'))
        self.assertEqual(obter_reducao_cargo_unidade(self.cargo, self.b), Decimal('8'))

    def test_formulario_invalido_nao_salva_metadados_ou_reducao(self):
        TipoCargoDiretivo.objects.create(nome='Nome em uso')
        for dados in (self.dados('-1'), self.dados('169'), self.dados('abc'), self.dados('1.001'), self.dados(''), self.dados('12', 'Nome em uso')):
            with self.subTest(dados=dados):
                self.assertEqual(self.client.post(self.url_editar(self.a), dados).status_code, 200)
                self.cargo.refresh_from_db()
                self.assertEqual(self.cargo.nome, 'Coordenação')
                self.assertFalse(ConfiguracaoCargoDiretivoUnidade.objects.exists())

    def test_falha_de_auditoria_reverte_metadados_configuracao_e_ocupacoes(self):
        ocupacao = self.ocupar(self.a, self.pa)
        with patch('apps.core.services.registrar_evento_prioridade1', side_effect=RuntimeError('Falha simulada')):
            with self.assertRaises(RuntimeError):
                self.client.post(self.url_editar(self.a), self.dados())
        self.cargo.refresh_from_db()
        ocupacao.refresh_from_db()
        self.assertEqual(self.cargo.nome, 'Coordenação')
        self.assertEqual(ocupacao.carga_reducao_horas, Decimal('8'))
        self.assertFalse(ConfiguracaoCargoDiretivoUnidade.objects.exists())

    def test_permissoes_unidade_ativa_e_get_sem_escrita(self):
        self.assertEqual(self.client.get(self.url_editar(self.a)).status_code, 200)
        self.assertFalse(ConfiguracaoCargoDiretivoUnidade.objects.exists())
        self.client.force_login(self.coord)
        self.assertEqual(self.client.post(self.url_editar(self.a), self.dados()).status_code, 403)
        self.client.force_login(self.desup)
        self.assertEqual(self.client.post(reverse('core:cargo_diretivo_unidade_update', args=[999999, self.cargo.pk]), self.dados()).status_code, 404)
        self.a.status = False
        self.a.save(update_fields=['status'])
        self.assertEqual(self.client.post(self.url_editar(self.a), self.dados()).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.post(self.url_editar(self.b), self.dados()).status_code, 302)

    def test_endpoint_global_antigo_ignora_ambos_os_campos_de_carga(self):
        ocupacao = self.ocupar(self.a, self.pa)
        response = self.client.post(reverse('core:cargo_diretivo_update', args=[self.cargo.pk]), {
            **self.dados('16'), 'carga_reducao_horas': '20',
        })
        self.assertEqual(response.status_code, 302)
        self.cargo.refresh_from_db()
        ocupacao.refresh_from_db()
        self.assertEqual(self.cargo.carga_reducao_horas, Decimal('8'))
        self.assertEqual(ocupacao.carga_reducao_horas, Decimal('8'))
        self.assertFalse(ConfiguracaoCargoDiretivoUnidade.objects.exists())

    def test_historico_futuros_e_outros_cargos_nao_mudam(self):
        for inicio, fim in ((self.hoje - timedelta(days=10), self.hoje - timedelta(days=1)),
                            (self.hoje - timedelta(days=10), self.hoje), (self.hoje + timedelta(days=1), None)):
            OcupacaoEquipeDiretiva.objects.create(
                cargo=self.cargo, unidade=self.a, professor=self.pa, data_inicio=inicio, data_fim=fim,
                carga_reducao_horas=Decimal('6'), reducao_personalizada=False,
            )
        outro = TipoCargoDiretivo.objects.create(nome='Outro cargo')
        OcupacaoEquipeDiretiva.objects.create(
            cargo=outro, unidade=self.a, professor=self.pa, data_inicio=self.hoje,
            carga_reducao_horas=Decimal('6'), reducao_personalizada=False,
        )
        self.configurar(self.a, '18')
        self.assertEqual(set(OcupacaoEquipeDiretiva.objects.values_list('carga_reducao_horas', flat=True)), {Decimal('6')})

    def test_configuracao_unica_por_par(self):
        self.configurar(self.a, '10')
        self.configurar(self.a, '12')
        self.assertEqual(ConfiguracaoCargoDiretivoUnidade.objects.count(), 1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ConfiguracaoCargoDiretivoUnidade.objects.create(cargo=self.cargo, unidade=self.a, carga_reducao_horas=Decimal('14'))
