"""Janelas de detalhe (explicação + lista) dos cartões da página de Alertas e Limites de Carga."""

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.models import Unidade
from apps.courses.models import (
    Course, CourseUnit, CurricularComponent, CurriculumMatrix, MatrixComponent,
)
from apps.professors.models import ContractType, Professor


class AlertasDetalhesTests(TestCase):
    def setUp(self):
        self.unidade = Unidade.objects.create(nome='U1', sigla='U1')
        curso = Course.objects.create(nome='Curso A', sigla='CA')
        CourseUnit.objects.create(curso=curso, unidade=self.unidade)
        matriz = CurriculumMatrix.objects.create(curso=curso, nome='M', is_vigente=True, turno='M')
        matriz.unidades.add(self.unidade)
        catalogo = CurricularComponent.objects.create(
            nome='Cálculo', codigo='C1', carga_horaria_padrao=80, creditos=4
        )
        MatrixComponent.objects.create(
            matriz=matriz, componente_curricular=catalogo, periodo='1', carga_horaria=80,
            creditos=4, carga_horaria_semanal=4, quantidade_turmas=2,
        )
        contrato = ContractType.objects.create(
            nome='T', regime_trabalho='40h', max_class_hours=20, max_total_hours=40, max_classes=4
        )
        professor = Professor.objects.create(
            id_funcional='1', rh_matricula='1', rh_nome='Ana Teste',
            tipo_contrato=contrato, unidade_principal=self.unidade,
        )
        professor.unidades.add(self.unidade)
        self.desup = User.objects.create_user(
            email='d.alertas@harpia.test', password='pw', perfil='DESUP', forcar_troca_senha=False
        )
        self.coord = User.objects.create_user(
            email='c.alertas@harpia.test', password='pw', perfil='COORDENADOR_UNIDADE',
            unidade=self.unidade, forcar_troca_senha=False,
        )
        self.url = reverse('core:alertas_carga_desup')

    def test_detalhes_listam_disciplinas_e_professores(self):
        self.client.force_login(self.desup)
        resposta = self.client.get(self.url)

        resumo = resposta.context['resumo_p1']
        self.assertEqual(resumo['detalhe_disciplinas'][0]['turmas_sem_docente'], 2)
        self.assertEqual(resumo['detalhe_sobra'][0]['nome'], 'ANA TESTE')
        for texto in (
            'modalDetalheDisciplinas', 'modalDetalheSobra', 'modalDetalheLimite',
            'modalDetalheAcima', 'Cálculo', 'ANA TESTE',
        ):
            self.assertContains(resposta, texto)

    def test_pagina_continua_restrita_a_desup(self):
        self.client.force_login(self.coord)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_acima_do_limite_explica_a_conta_e_a_origem_das_horas(self):
        from apps.allocations.services import atribuir_docente

        professor = Professor.objects.get(rh_nome='ANA TESTE')
        professor.tipo_contrato.max_class_hours = 2
        professor.tipo_contrato.save(update_fields=['max_class_hours'])
        atribuir_docente(MatrixComponent.objects.get(), professor)
        self.client.force_login(self.desup)

        resposta = self.client.get(self.url)
        detalhe = resposta.context['resumo_p1']['detalhe_acima'][0]

        self.assertEqual(detalhe['horas_aula'], 4)
        self.assertEqual(detalhe['horas_extra'], 0)
        self.assertEqual(detalhe['meta'], 2)
        self.assertEqual(detalhe['diferenca'], 2)
        self.assertContains(resposta, '4 h contabilizadas − 2 h de limite = 2 h de excesso')
        self.assertContains(resposta, '0 h em outras horas aprovadas')

    def test_lista_acima_do_limite_mostra_mais_de_cem_professores(self):
        from django.utils import timezone

        from apps.allocations.models import AlocacaoCurricular, AlocacaoTurmaDocente

        contrato = Professor.objects.get(rh_nome='ANA TESTE').tipo_contrato
        contrato.max_class_hours = 2
        contrato.save(update_fields=['max_class_hours'])
        professores = Professor.objects.bulk_create([
            Professor(
                id_funcional=f'excesso-{numero}', rh_nome=f'Professor {numero:03d}',
                tipo_contrato=contrato, unidade_principal=self.unidade,
            )
            for numero in range(101)
        ])
        hoje = timezone.localdate()
        semestre = f"{hoje.year}.{'1' if hoje.month <= 6 else '2'}"
        alocacao = AlocacaoCurricular.objects.create(
            unidade=self.unidade, curso=CourseUnit.objects.get(), semestre=semestre, turno='M',
        )
        AlocacaoTurmaDocente.objects.bulk_create([
            AlocacaoTurmaDocente(
                alocacao_curricular=alocacao, componente_matriz=MatrixComponent.objects.get(),
                docente=professor,
            )
            for professor in professores
        ])
        self.client.force_login(self.desup)

        resposta = self.client.get(self.url)

        self.assertEqual(resposta.context['resumo_p1']['professores_excedidos'], 101)
        self.assertEqual(len(resposta.context['resumo_p1']['detalhe_acima']), 101)
        self.assertContains(resposta, 'PROFESSOR 100')
        self.assertNotContains(resposta, 'Mostrando os primeiros')

    def test_readaptado_em_sala_nao_gera_ponto_de_atencao(self):
        from datetime import timedelta

        from django.utils import timezone

        from apps.allocations.services import atribuir_docente
        from apps.core.models import ReadaptacaoProfessor
        from apps.courses.models import MatrixComponent

        professor = Professor.objects.get(rh_nome='ANA TESTE')
        componente = MatrixComponent.objects.get()
        atribuir_docente(componente, professor)
        ReadaptacaoProfessor.objects.create(
            professor=professor, data_inicio=timezone.localdate() - timedelta(days=5)
        )
        self.client.force_login(self.desup)

        resposta = self.client.get(self.url)

        resumo = resposta.context['resumo_p1']
        self.assertNotIn('readaptados_em_sala', resumo)
        self.assertNotContains(resposta, 'modalPontoReadaptados')
        self.assertContains(resposta, 'Professor <strong>readaptado</strong> é aquele com restrição funcional para dar aula.')
        # Sem ocorrência não há botão para abrir a lista.
        self.assertNotContains(resposta, "abrirModal('modalPontoDiretivos')")
