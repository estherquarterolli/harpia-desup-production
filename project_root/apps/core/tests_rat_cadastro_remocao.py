from datetime import timedelta
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone

from apps.professors.models import Professor
from apps.professors.tests_e2e import ProfessorE2EBase

from .models import AuditoriaGlobal, ExcecaoCargaUnidade, Notificacao, SolicitacaoProfessorExterno


class CadastroProfessorJaComoRatTests(ProfessorE2EBase):
    """Botão "Professor já vem como RAT" no cadastro de professor (DESUP)."""

    def setUp(self):
        super().setUp()
        self.hoje = timezone.localdate()
        self.client.force_login(self.desup)

    def dados_rat(self, **overrides):
        dados = self._dados_professor(
            vem_com_rat='on',
            rat_unidade=self.unidade_a.pk,
            rat_horas_adicionais='4.00',
            rat_data_inicio=self.hoje.isoformat(),
            rat_data_fim=(self.hoje + timedelta(days=180)).isoformat(),
            rat_justificativa='',
        )
        dados.update(overrides)
        return dados

    def test_botao_aparece_no_cadastro_e_some_na_edicao(self):
        cadastro = self.client.get(self.url_criar)
        self.assertIn('vem_com_rat', cadastro.context['form'].fields)
        self.assertContains(cadastro, 'Professor já vem como RAT')

        edicao = self.client.get(reverse('professors:professor_update', args=[self.prof_a1.pk]))
        self.assertNotIn('vem_com_rat', edicao.context['form'].fields)
        self.assertNotContains(edicao, 'Professor já vem como RAT')

    def test_cadastro_como_rat_cria_rat_aprovado_e_avisa_a_unidade(self):
        resposta = self.client.post(self.url_criar, self.dados_rat())
        self.assertEqual(resposta.status_code, 302)

        professor = Professor.objects.get(id_funcional='IDF-NOVO')
        rat = ExcecaoCargaUnidade.objects.get(professor=professor)
        self.assertEqual(rat.unidade, self.unidade_a)
        self.assertEqual(rat.status, ExcecaoCargaUnidade.StatusChoices.APROVADA)
        self.assertEqual(rat.horas_adicionais, Decimal('4.00'))
        self.assertEqual(rat.decidido_por, self.desup)
        self.assertTrue(rat.justificativa)
        self.assertTrue(
            Notificacao.objects.filter(
                unidade_destino=self.unidade_a, titulo='RAT registrado no cadastro do professor',
            ).exists()
        )
        self.assertTrue(AuditoriaGlobal.objects.filter(acao='RAT_CADASTRADO_COM_PROFESSOR').exists())

    def test_unica_unidade_marcada_e_usada_quando_unidade_do_rat_fica_vazia(self):
        resposta = self.client.post(self.url_criar, self.dados_rat(rat_unidade=''))
        self.assertEqual(resposta.status_code, 302)
        professor = Professor.objects.get(id_funcional='IDF-NOVO')
        self.assertEqual(ExcecaoCargaUnidade.objects.get(professor=professor).unidade, self.unidade_a)

    def test_sem_marcar_rat_nao_cria_rat(self):
        resposta = self.client.post(self.url_criar, self._dados_professor())
        self.assertEqual(resposta.status_code, 302)
        professor = Professor.objects.get(id_funcional='IDF-NOVO')
        self.assertFalse(ExcecaoCargaUnidade.objects.filter(professor=professor).exists())

    def test_rat_sem_horas_bloqueia_o_cadastro_inteiro(self):
        resposta = self.client.post(self.url_criar, self.dados_rat(rat_horas_adicionais=''))
        self.assertEqual(resposta.status_code, 200)
        self.assertIn('rat_horas_adicionais', resposta.context['form'].errors)
        self.assertFalse(Professor.objects.filter(id_funcional='IDF-NOVO').exists())
        self.assertFalse(ExcecaoCargaUnidade.objects.exists())

    def test_unidade_do_rat_precisa_estar_entre_as_unidades_do_professor(self):
        resposta = self.client.post(self.url_criar, self.dados_rat(rat_unidade=self.unidade_b.pk))
        self.assertEqual(resposta.status_code, 200)
        self.assertIn('rat_unidade', resposta.context['form'].errors)
        self.assertFalse(Professor.objects.filter(id_funcional='IDF-NOVO').exists())

    def test_fim_antes_do_inicio_e_recusado(self):
        resposta = self.client.post(self.url_criar, self.dados_rat(
            rat_data_fim=(self.hoje - timedelta(days=1)).isoformat(),
        ))
        self.assertEqual(resposta.status_code, 200)
        self.assertIn('rat_data_fim', resposta.context['form'].errors)
        self.assertFalse(Professor.objects.filter(id_funcional='IDF-NOVO').exists())


class RemoverSolicitacaoUnidadeTests(ProfessorE2EBase):
    """Botão "Remover" na tela de Solicitações da DESUP."""

    def setUp(self):
        super().setUp()
        self.solicitacao = SolicitacaoProfessorExterno.objects.create(
            tipo=SolicitacaoProfessorExterno.TipoChoices.CADASTRO,
            unidade_solicitante=self.unidade_a,
            professor_nome='Docente Pedido',
            semestre=f'{timezone.localdate().year}.1',
            justificativa='Pedido de teste.',
            solicitado_por=self.coord_a,
        )
        self.url = reverse('core:solicitacao_professor_remover', args=[self.solicitacao.pk])

    def test_lista_mostra_botao_remover(self):
        self.client.force_login(self.desup)
        resposta = self.client.get(reverse('core:solicitacao_professor_list'))
        self.assertContains(resposta, self.url)
        self.assertContains(resposta, f'modalRemoverSolicitacao{self.solicitacao.pk}')

    def test_desup_remove_solicitacao_pendente_e_unidade_e_avisada(self):
        self.client.force_login(self.desup)
        resposta = self.client.post(self.url)
        self.assertRedirects(resposta, reverse('core:solicitacao_professor_list'), fetch_redirect_response=False)
        self.assertFalse(SolicitacaoProfessorExterno.objects.filter(pk=self.solicitacao.pk).exists())
        self.assertTrue(
            Notificacao.objects.filter(unidade_destino=self.unidade_a, titulo='Solicitação removida').exists()
        )
        self.assertTrue(AuditoriaGlobal.objects.filter(acao='SOLICITACAO_PROFESSOR_REMOVIDA').exists())

    def test_remover_volta_para_a_lista_filtrada(self):
        self.client.force_login(self.desup)
        destino = reverse('core:solicitacao_professor_list') + '?status=&tipo=CADASTRO'
        resposta = self.client.post(self.url, {'next': destino})
        self.assertRedirects(resposta, destino, fetch_redirect_response=False)

    def test_solicitacao_ja_decidida_pode_ser_removida_sem_avisar_unidade(self):
        SolicitacaoProfessorExterno.objects.filter(pk=self.solicitacao.pk).update(
            status=SolicitacaoProfessorExterno.StatusChoices.RECUSADA,
        )
        self.client.force_login(self.desup)
        self.client.post(self.url)
        self.assertFalse(SolicitacaoProfessorExterno.objects.filter(pk=self.solicitacao.pk).exists())
        self.assertFalse(Notificacao.objects.filter(titulo='Solicitação removida').exists())

    def test_coordenador_nao_remove(self):
        self.client.force_login(self.coord_a)
        self.client.post(self.url)
        self.assertTrue(SolicitacaoProfessorExterno.objects.filter(pk=self.solicitacao.pk).exists())

    def test_get_nao_remove(self):
        self.client.force_login(self.desup)
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 405)
        self.assertTrue(SolicitacaoProfessorExterno.objects.filter(pk=self.solicitacao.pk).exists())

    def test_solicitacao_inexistente_mostra_aviso(self):
        self.client.force_login(self.desup)
        self.solicitacao.delete()
        resposta = self.client.post(self.url)
        self.assertRedirects(resposta, reverse('core:solicitacao_professor_list'), fetch_redirect_response=False)
