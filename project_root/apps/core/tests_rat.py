from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from apps.allocations.models import AlocacaoTurmaDocente
from apps.professors.tests_e2e import ProfessorE2EBase
from apps.professors.services import MENSAGEM_CARGA_RAT_INCOMPLETA, obter_cargas_rat
from .models import ExcecaoCargaUnidade, Notificacao, AuditoriaGlobal
from .services import solicitar_rat


class RatUnidadeTests(ProfessorE2EBase):
    def setUp(self):
        super().setUp()
        self.url = reverse('core:rat_unidade')
        self.hoje = timezone.localdate()
        self.client.force_login(self.coord_a)

    def dados(self, **overrides):
        dados = {
            'professor': self.prof_a1.pk, 'horas_adicionais': '4.50',
            'data_inicio': self.hoje.isoformat(),
            'data_fim': (self.hoje + timedelta(days=30)).isoformat(),
            'justificativa': 'Atendimento a turma adicional.',
        }
        dados.update(overrides)
        return dados

    def completar_carga(self, horas=20):
        matriz = self._matriz_vigente(self.curso_ads, self.unidade_a)
        return self._componente(
            matriz, 'Carga regular', 'REGULAR', carga_horaria=horas * 20, docente=self.prof_a1,
        )

    def test_tutorial_rat_reutiliza_componente_e_aponta_para_campos_reais(self):
        resposta = self.client.get(self.url)
        self.assertContains(resposta, 'data-ajuda-abrir')
        self.assertContains(resposta, 'id="tourRoot"')
        self.assertContains(resposta, 'id="ajuda-dados"')
        ajuda = resposta.context['ajuda_pagina']
        self.assertIn('carga horária regular completa', ' '.join(ajuda['funcionalidades']))
        for passo in ajuda['passos']:
            for alvo in passo['alvo']:
                self.assertTrue(alvo.startswith('#'))
                self.assertContains(resposta, f'id="{alvo[1:]}"')

    def request(self, user=None):
        request = RequestFactory().post(self.url)
        request.user = user or self.coord_a
        return request

    def solicitar_pelo_servico(self, **overrides):
        dados = {
            'request': self.request(), 'professor_id': self.prof_a1.pk,
            'horas_adicionais': Decimal('4.50'), 'data_inicio': self.hoje,
            'data_fim': self.hoje + timedelta(days=30), 'justificativa': 'Turma extra.',
        }
        dados.update(overrides)
        return solicitar_rat(**dados)

    def test_carga_incompleta_bloqueada_na_interface_e_post_direto(self):
        pagina = self.client.get(self.url)
        self.assertContains(pagina, MENSAGEM_CARGA_RAT_INCOMPLETA)
        self.assertFalse(pagina.context['cargas_rat'][str(self.prof_a1.pk)]['completa'])
        resposta = self.client.post(self.url, self.dados())
        self.assertContains(resposta, MENSAGEM_CARGA_RAT_INCOMPLETA)
        self.assertFalse(ExcecaoCargaUnidade.objects.exists())
        with self.assertRaisesMessage(ValidationError, MENSAGEM_CARGA_RAT_INCOMPLETA):
            self.solicitar_pelo_servico()

    def test_envio_com_carga_completa_usa_identidade_e_unidade_do_servidor(self):
        self.completar_carga()
        pagina = self.client.get(self.url)
        self.assertTrue(pagina.context['cargas_rat'][str(self.prof_a1.pk)]['completa'])
        self.assertEqual(pagina.context['cargas_rat'][str(self.prof_a1.pk)]['id_funcional'], self.prof_a1.id_funcional)
        resposta = self.client.post(self.url, self.dados(
            unidade=self.unidade_b.pk, solicitado_por=self.coord_b.pk,
            status='APROVADA', nome='Nome adulterado', id_funcional='FALSO',
        ))
        self.assertRedirects(resposta, self.url)
        pedido = ExcecaoCargaUnidade.objects.get()
        self.assertEqual(pedido.unidade, self.unidade_a)
        self.assertEqual(pedido.solicitado_por, self.coord_a)
        self.assertEqual(pedido.professor, self.prof_a1)
        self.assertEqual(pedido.status, 'PENDENTE')
        self.assertEqual(pedido.horas_adicionais, Decimal('4.50'))
        self.assertTrue(Notificacao.objects.filter(titulo='Solicitação de RAT').exists())
        self.assertTrue(AuditoriaGlobal.objects.filter(acao='RAT_SOLICITADO').exists())

    def test_professor_estrangeiro_nao_aparece_e_nao_pode_ser_enviado(self):
        pagina = self.client.get(self.url, {'unidade_id': self.unidade_b.pk})
        self.assertNotIn(str(self.prof_b1.pk), pagina.context['cargas_rat'])
        resposta = self.client.post(self.url, self.dados(professor=self.prof_b1.pk))
        self.assertEqual(resposta.status_code, 200)
        self.assertIn('professor', resposta.context['form'].errors)
        with self.assertRaises(PermissionDenied):
            self.solicitar_pelo_servico(professor_id=self.prof_b1.pk)
        self.assertFalse(ExcecaoCargaUnidade.objects.exists())

    def test_vinculo_adicional_permite_professor(self):
        self.prof_a1.unidade_principal = self.unidade_b
        self.prof_a1.save(update_fields=['unidade_principal'])
        self.prof_a1.unidades.add(self.unidade_a)
        self.completar_carga()
        self.assertRedirects(self.client.post(self.url, self.dados()), self.url)

    def test_id_funcional_e_inicio_da_vigencia_obrigatorios(self):
        from apps.professors.models import Professor
        from apps.professors.services import MENSAGEM_ID_RAT_OBRIGATORIO

        self.completar_carga()
        resposta = self.client.post(self.url, self.dados(data_inicio=''))
        self.assertIn('data_inicio', resposta.context['form'].errors)
        self.assertTrue(resposta.context['form'].fields['data_inicio'].required)
        with self.assertRaises(ValidationError):
            self.solicitar_pelo_servico(data_inicio=None)
        for id_invalido in ('', '   '):
            with self.subTest(id_funcional=id_invalido):
                Professor.objects.filter(pk=self.prof_a1.pk).update(id_funcional=id_invalido)
                resposta = self.client.post(self.url, self.dados())
                self.assertContains(resposta, MENSAGEM_ID_RAT_OBRIGATORIO)
                with self.assertRaisesMessage(ValidationError, MENSAGEM_ID_RAT_OBRIGATORIO):
                    self.solicitar_pelo_servico()
        self.assertFalse(ExcecaoCargaUnidade.objects.exists())

    def test_campos_invalidos_nao_criam_solicitacao(self):
        self.completar_carga()
        for overrides in (
            {'horas_adicionais': '0'}, {'horas_adicionais': '-1'},
            {'horas_adicionais': 'abc'}, {'professor': ''},
            {'data_fim': (self.hoje - timedelta(days=1)).isoformat()},
            {'justificativa': ''}, {'data_inicio': ''},
        ):
            with self.subTest(overrides=overrides):
                resposta = self.client.post(self.url, self.dados(**overrides))
                self.assertEqual(resposta.status_code, 200)
                self.assertTrue(resposta.context['form'].errors)
        with self.assertRaises(ValidationError):
            self.solicitar_pelo_servico(horas_adicionais=Decimal('-1'))
        self.assertFalse(ExcecaoCargaUnidade.objects.exists())

    def test_historico_isolado_e_unidade_nao_pode_decidir(self):
        self.completar_carga()
        pedido = self.solicitar_pelo_servico()
        self.client.force_login(self.coord_b)
        resposta = self.client.get(self.url, {'unidade_id': self.unidade_a.pk})
        self.assertNotContains(resposta, pedido.justificativa)
        self.assertEqual(resposta.context['solicitacoes'].paginator.count, 0)
        resposta = self.client.post(reverse('core:excecao_carga_decidir', args=[pedido.pk]), {'decisao': 'APROVADA'})
        self.assertEqual(resposta.status_code, 403)
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, 'PENDENTE')

    def test_recebimento_decisao_desup_e_acompanhamento_da_unidade(self):
        self.completar_carga()
        pedido = self.solicitar_pelo_servico()
        self.client.force_login(self.desup)
        pagina = self.client.get(reverse('core:alertas_carga_desup'))
        self.assertContains(pagina, f'id="modalExcecao{pedido.pk}"')
        self.assertContains(pagina, self.prof_a1.id_funcional)
        self.client.post(reverse('core:excecao_carga_decidir', args=[pedido.pk]), {
            'decisao': 'APROVADA', 'motivo_decisao': 'Autorizado para a vigência.',
        })
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, 'APROVADA')
        self.assertEqual(pedido.decidido_por, self.desup)
        self.client.force_login(self.coord_a)
        pagina = self.client.get(self.url)
        self.assertContains(pagina, 'Aprovada')
        self.assertContains(pagina, 'Autorizado para a vigência.')

    def test_envio_e_aprovacao_sem_fim_da_vigencia(self):
        self.completar_carga()
        pagina = self.client.get(self.url)
        self.assertFalse(pagina.context['form'].fields['data_fim'].required)
        self.assertRedirects(self.client.post(self.url, self.dados(data_fim='')), self.url)
        pedido = ExcecaoCargaUnidade.objects.get()
        self.assertIsNone(pedido.data_fim)
        self.client.force_login(self.desup)
        pagina = self.client.get(reverse('core:alertas_carga_desup'))
        self.assertContains(pagina, 'Sem fim definido')
        self.client.post(reverse('core:excecao_carga_decidir', args=[pedido.pk]), {'decisao': 'APROVADA'})
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, 'APROVADA')
        self.assertIsNone(pedido.data_fim)
        self.client.force_login(self.coord_a)
        self.assertContains(self.client.get(self.url), 'Sem fim definido')

    def test_paginacao_padrao_isola_unidade_e_nao_repete_solicitacoes(self):
        for unidade, professor, user, total in (
            (self.unidade_a, self.prof_a1, self.coord_a, 21),
            (self.unidade_b, self.prof_b1, self.coord_b, 1),
        ):
            ExcecaoCargaUnidade.objects.bulk_create([
                ExcecaoCargaUnidade(
                    unidade=unidade, professor=professor, solicitado_por=user,
                    horas_adicionais=2, data_inicio=self.hoje,
                    justificativa=f'Pedido {unidade.sigla} {i}',
                ) for i in range(total)
            ])
        primeira = self.client.get(self.url)
        segunda = self.client.get(self.url, {'page': 2, 'unidade_id': self.unidade_b.pk}, HTTP_HX_REQUEST='true')
        self.assertContains(primeira, 'Exibindo 1–20 de 21')
        self.assertContains(primeira, 'Ver mais')
        self.assertContains(segunda, 'Exibindo 21–21 de 21')
        self.assertContains(segunda, 'Anteriores')
        self.assertTemplateUsed(segunda, 'partials/pagination.html')
        ids_primeira = {s.pk for s in primeira.context['solicitacoes']}
        ids_segunda = {s.pk for s in segunda.context['solicitacoes']}
        self.assertEqual(len(ids_primeira), 20)
        self.assertEqual(len(ids_segunda), 1)
        self.assertFalse(ids_primeira & ids_segunda)
        self.assertEqual(segunda.context['solicitacoes'][0].unidade_id, self.unidade_a.pk)

    def test_rat_aprovado_sem_fim_entra_no_limite_somente_apos_inicio(self):
        from .models import LimiteCargaUnidade
        from .priority1 import obter_resumo_prioridade1

        self.completar_carga()
        LimiteCargaUnidade.objects.create(
            unidade=self.unidade_a, limite_horas_semanais=20,
            data_inicio=self.hoje, criado_por=self.desup,
        )
        pedido = self.solicitar_pelo_servico(data_fim=None)

        def no_limite():
            return obter_resumo_prioridade1(unidade_id=self.unidade_a.pk)['unidades_no_limite_count']

        self.assertEqual(no_limite(), 1)
        pedido.status = 'APROVADA'
        pedido.save(update_fields=['status'])
        self.assertEqual(no_limite(), 0)
        pedido.data_inicio = self.hoje + timedelta(days=1)
        pedido.save(update_fields=['data_inicio'])
        self.assertEqual(no_limite(), 1)
        pedido.data_inicio = self.hoje - timedelta(days=2)
        pedido.data_fim = self.hoje - timedelta(days=1)
        pedido.save(update_fields=['data_inicio', 'data_fim'])
        self.assertEqual(no_limite(), 1)

    def test_status_tem_as_cores_solicitadas(self):
        from html.parser import HTMLParser

        class StatusParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.classes = ''
                self.status = {}

            def handle_starttag(self, tag, attrs):
                if tag == 'span':
                    self.classes = dict(attrs).get('class', '')

            def handle_data(self, data):
                if data in ('Pendente', 'Recusada', 'Aprovada'):
                    self.status[data] = self.classes

        for status in ('PENDENTE', 'RECUSADA', 'APROVADA'):
            ExcecaoCargaUnidade.objects.create(
                unidade=self.unidade_a, professor=self.prof_a1, solicitado_por=self.coord_a,
                horas_adicionais=2, data_inicio=self.hoje, justificativa='Cor do status', status=status,
            )
        parser = StatusParser()
        parser.feed(self.client.get(self.url).content.decode())
        for status, cor in (('Pendente', 'bg-blue-50'), ('Recusada', 'bg-red-50'), ('Aprovada', 'bg-green-50')):
            self.assertIn(cor, parser.status[status])

    def test_rat_existente_nao_completa_carga_regular(self):
        self.completar_carga(horas=16)
        ExcecaoCargaUnidade.objects.create(
            unidade=self.unidade_a, professor=self.prof_a1, solicitado_por=self.coord_a,
            horas_adicionais=4, data_inicio=self.hoje, data_fim=self.hoje,
            justificativa='RAT anterior.', status='APROVADA',
        )
        self.assertFalse(obter_cargas_rat([self.prof_a1])[str(self.prof_a1.pk)]['completa'])
        self.assertContains(self.client.post(self.url, self.dados()), MENSAGEM_CARGA_RAT_INCOMPLETA)

    def test_backend_revalida_apos_mudanca_da_carga(self):
        self.completar_carga()
        self.assertTrue(self.client.get(self.url).context['cargas_rat'][str(self.prof_a1.pk)]['completa'])
        AlocacaoTurmaDocente.objects.filter(docente=self.prof_a1).delete()
        self.assertContains(self.client.post(self.url, self.dados()), MENSAGEM_CARGA_RAT_INCOMPLETA)

    def test_carga_justificada_aprovada_completa_meta(self):
        self.completar_carga(horas=18)
        self._justificativa_aprovada(self.prof_a1, self.unidade_a)
        self.assertTrue(obter_cargas_rat([self.prof_a1])[str(self.prof_a1.pk)]['completa'])
        self.assertRedirects(self.client.post(self.url, self.dados()), self.url)

    def test_justificativa_pendente_e_semestre_anterior_nao_completam_meta(self):
        from apps.extra_curricular.models import PendenciaExtra

        self.completar_carga(horas=18)
        pendencia = self._justificativa_aprovada(
            self.prof_a1, self.unidade_a, status=PendenciaExtra.StatusChoices.RASCUNHO,
        )
        self.assertFalse(obter_cargas_rat([self.prof_a1])[str(self.prof_a1.pk)]['completa'])
        pendencia.status = PendenciaExtra.StatusChoices.APROVADO
        pendencia.semestre = '2020.1'
        pendencia.save(update_fields=['status', 'semestre'])
        self.assertFalse(obter_cargas_rat([self.prof_a1])[str(self.prof_a1.pk)]['completa'])

    def test_reducao_vigente_da_desup_altera_meta_regular(self):
        from .models import TipoCargoDiretivo, OcupacaoEquipeDiretiva

        self.completar_carga(horas=18)
        cargo = TipoCargoDiretivo.objects.create(nome='Cargo RAT teste', codigo='RAT_TESTE')
        OcupacaoEquipeDiretiva.objects.create(
            unidade=self.unidade_a, professor=self.prof_a1, cargo=cargo,
            carga_reducao_horas=2, data_inicio=self.hoje, criado_por=self.desup,
        )
        self.assertRedirects(self.client.post(self.url, self.dados()), self.url)

    def test_perfis_sem_unidade_inativa_e_anonimo(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.client.force_login(self.desup)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.coord_a.unidade = None
        self.coord_a.save(update_fields=['unidade'])
        self.client.force_login(self.coord_a)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.coord_a.unidade = self.unidade_a
        self.coord_a.save(update_fields=['unidade'])
        self.unidade_a.status = False
        self.unidade_a.save(update_fields=['status'])
        self.assertEqual(self.client.get(self.url).status_code, 403)
