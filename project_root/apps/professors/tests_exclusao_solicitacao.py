"""Regressões da exclusão de professores originados de solicitações."""

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.core.models import (
    AuditoriaGlobal, ReadaptacaoProfessor, SolicitacaoProfessorExterno as Solicitacao,
)
from apps.professors.models import Professor
from apps.professors.tests_e2e import ProfessorE2EBase


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ExclusaoProfessorSolicitadoTests(ProfessorE2EBase):
    def _solicitacao_aprovada(self, **dados):
        valores = dict(
            tipo=Solicitacao.TipoChoices.CADASTRO,
            unidade_solicitante=self.unidade_a,
            professor=self.prof_a1,
            professor_nome='Nome original do pedido',
            professor_id_funcional=self.prof_a1.id_funcional,
            professor_rh_matricula=self.prof_a1.rh_matricula,
            semestre=self.semestre_atual,
            justificativa='Cadastro solicitado pela unidade.',
            solicitado_por=self.coord_a,
            status=Solicitacao.StatusChoices.APROVADA,
            decidido_por=self.desup,
            decidido_em=timezone.now(),
        )
        valores.update(dados)
        return Solicitacao.objects.create(**valores)

    def _excluir(self):
        return self.client.post(reverse('professors:professor_delete', args=[self.prof_a1.pk]))

    def test_exclui_de_fato_preservando_historico_e_auditoria(self):
        solicitacao = self._solicitacao_aprovada()
        self.client.force_login(self.coord_a)
        professor_id = self.prof_a1.pk
        resposta = self._excluir()

        self.assertEqual(resposta.status_code, 302)
        self.assertFalse(Professor.objects.filter(pk=professor_id).exists())
        self.assertFalse(self.unidade_a.professores_vinculados.filter(pk=professor_id).exists())
        self.assertFalse(self.unidade_a.professores.filter(pk=professor_id).exists())
        solicitacao.refresh_from_db()
        self.assertIsNone(solicitacao.professor_id)
        self.assertEqual(solicitacao.professor_nome, 'Nome original do pedido')
        self.assertEqual(solicitacao.professor_id_funcional, self.prof_a1.id_funcional)
        self.assertEqual(solicitacao.professor_rh_matricula, self.prof_a1.rh_matricula)
        self.assertEqual(solicitacao.status, Solicitacao.StatusChoices.APROVADA)
        self.assertEqual(solicitacao.solicitado_por, self.coord_a)
        self.assertEqual(solicitacao.decidido_por, self.desup)
        self.assertIsNotNone(solicitacao.decidido_em)
        self.assertTrue(any('excluído com sucesso' in msg for msg in self._mensagens(resposta)))
        self.assertTrue(AuditoriaGlobal.objects.filter(acao='PROFESSOR_EXCLUIDO', usuario=self.coord_a).exists())

        self.assertNotContains(self.client.get(self.url_lista), self.prof_a1.id_funcional)
        busca = self.client.get(reverse('buscar_professores'), {'q': self.prof_a1.id_funcional})
        self.assertEqual(busca.json()['results'], [])
        self.client.force_login(self.desup)
        historico = self.client.get(reverse('core:solicitacao_professor_list'), {'status': 'APROVADA'})
        self.assertContains(historico, solicitacao.nome_professor)
        self.assertNotContains(historico, reverse('professors:professor_update', args=[professor_id]))

    def test_completa_identificadores_ausentes_em_todos_os_pedidos_aprovados(self):
        pedidos = [self._solicitacao_aprovada(
            professor_nome='', professor_id_funcional=' ', professor_rh_matricula='',
        ) for _ in range(2)]
        self.client.force_login(self.desup)
        self._excluir()
        for pedido in pedidos:
            pedido.refresh_from_db()
            self.assertIsNone(pedido.professor_id)
            self.assertEqual(pedido.professor_nome, self.prof_a1.nome)
            self.assertEqual(pedido.professor_id_funcional, self.prof_a1.id_funcional)
            self.assertEqual(pedido.professor_rh_matricula, self.prof_a1.rh_matricula)

    def test_alocacao_impede_exclusao_e_reverte_desvinculacao_do_pedido(self):
        pedido = self._solicitacao_aprovada(professor_id_funcional='')
        matriz = self._matriz_vigente(self.curso_ads, self.unidade_a)
        self._componente(matriz, 'Algoritmos', 'ALG-EXCLUSAO', docente=self.prof_a1)
        self.client.force_login(self.coord_a)
        resposta = self._excluir()
        pedido.refresh_from_db()

        self.assertTrue(Professor.objects.filter(pk=self.prof_a1.pk).exists())
        self.assertEqual(pedido.professor_id, self.prof_a1.pk)
        self.assertEqual(pedido.professor_id_funcional, '')
        self.assertIn('componentes curriculares', ' '.join(self._mensagens(resposta)))
        self.assertFalse(AuditoriaGlobal.objects.filter(acao='PROFESSOR_EXCLUIDO').exists())
        self.assertFalse(AuditoriaGlobal.objects.filter(acao='SOLICITACAO_PROFESSOR_ALTERADO').exists())

    def test_cessao_continua_protegida_com_mensagem_correspondente(self):
        pedido = self._solicitacao_aprovada()
        cessao = self._solicitacao_aprovada(
            tipo=Solicitacao.TipoChoices.CESSAO,
            unidade_origem=self.unidade_a, unidade_solicitante=self.unidade_b,
        )
        self.client.force_login(self.desup)
        resposta = self._excluir()
        pedido.refresh_from_db()
        cessao.refresh_from_db()

        self.assertEqual(pedido.professor_id, self.prof_a1.pk)
        self.assertEqual(cessao.professor_id, self.prof_a1.pk)
        mensagem = ' '.join(self._mensagens(resposta))
        self.assertIn('cessão', mensagem)
        self.assertNotIn('componentes curriculares', mensagem)

    def test_cadastro_pendente_vinculado_continua_protegido(self):
        pedido = self._solicitacao_aprovada(status=Solicitacao.StatusChoices.PENDENTE)
        self.client.force_login(self.desup)
        resposta = self._excluir()
        pedido.refresh_from_db()
        self.assertEqual(pedido.professor_id, self.prof_a1.pk)
        mensagem = ' '.join(self._mensagens(resposta))
        self.assertIn('solicitações de cadastro', mensagem)
        self.assertNotIn('componentes curriculares', mensagem)

    def test_outro_vinculo_protegido_informa_motivo_e_preserva_pedido(self):
        pedido = self._solicitacao_aprovada()
        ReadaptacaoProfessor.objects.create(
            professor=self.prof_a1, data_inicio=timezone.localdate(),
            justificativa_administrativa='Registro administrativo.',
        )
        self.client.force_login(self.desup)
        resposta = self._excluir()
        pedido.refresh_from_db()
        self.assertEqual(pedido.professor_id, self.prof_a1.pk)
        mensagem = ' '.join(self._mensagens(resposta))
        self.assertIn('readaptações de professores', mensagem)
        self.assertNotIn('componentes curriculares', mensagem)

    def test_coordenador_de_outra_unidade_nao_desvincula_pedido(self):
        pedido = self._solicitacao_aprovada()
        self.client.force_login(self.coord_b)
        resposta = self._excluir()
        self.assertEqual(resposta.status_code, 404)
        pedido.refresh_from_db()
        self.assertEqual(pedido.professor_id, self.prof_a1.pk)
        self.assertTrue(Professor.objects.filter(pk=self.prof_a1.pk).exists())

    def test_nova_solicitacao_cadastra_mesmos_identificadores_sem_reabrir_a_antiga(self):
        # Percorre as rotas reais desde a solicitação até o segundo cadastro.
        self.client.force_login(self.coord_a)
        id_funcional, matricula = 'ID-RECICLADO', 'MAT-RECICLADA'
        for tentativa in range(2):
            resposta = self.client.post(reverse('professors:professor_solicitar_cadastro'), {
                'nome': 'Professor solicitado', 'id_funcional': id_funcional,
                'rh_matricula': matricula, 'tipo_contrato': self.contrato.pk,
                'observacao': 'Novo cadastro.',
            })
            self.assertEqual(resposta.status_code, 302)
            pedido = Solicitacao.objects.filter(professor_id_funcional=id_funcional).latest('pk')
            self.client.force_login(self.desup)
            resposta = self.client.post(reverse('core:solicitacao_professor_decidir', args=[pedido.pk]), {
                'decisao': 'APROVADA', 'motivo_decisao': '',
            })
            url_cadastro = f'{self.url_criar}?solicitacao={pedido.pk}'
            self.assertEqual(resposta['Location'], url_cadastro)
            resposta = self.client.post(url_cadastro, self._dados_professor(
                id_funcional=id_funcional, rh_matricula=matricula, rh_nome='Professor solicitado',
            ))
            self.assertEqual(resposta.status_code, 302)
            pedido.refresh_from_db()
            professor = Professor.objects.get(id_funcional=id_funcional)
            self.assertEqual(pedido.professor_id, professor.pk)
            self.assertEqual(pedido.status, Solicitacao.StatusChoices.APROVADA)
            if tentativa == 0:
                pedido_antigo = pedido
                self.client.force_login(self.coord_a)
                self.client.post(reverse('professors:professor_delete', args=[professor.pk]))
                self.assertFalse(Professor.objects.filter(id_funcional=id_funcional).exists())
                self.client.force_login(self.desup)
                self.client.post(reverse('core:solicitacao_professor_decidir', args=[pedido.pk]), {
                    'decisao': 'APROVADA', 'motivo_decisao': '',
                })
                self.assertFalse(Professor.objects.filter(id_funcional=id_funcional).exists())
                self.client.force_login(self.coord_a)
        pedido_antigo.refresh_from_db()
        self.assertIsNone(pedido_antigo.professor_id)
        self.assertEqual(pedido_antigo.status, Solicitacao.StatusChoices.APROVADA)
