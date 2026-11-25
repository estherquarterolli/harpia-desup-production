from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.courses.models import Course, CourseUnit, CurriculumMatrix
from apps.professors.models import ContractType, Professor

from .forms import OcupacaoEquipeDiretivaUnidadeForm, OpcoesOcupacaoEquipeDiretiva
from .models import (
    AuditoriaGlobal, ConfiguracaoCargoDiretivoUnidade, OcupacaoEquipeDiretiva,
    TipoCargoDiretivo, Unidade,
)


class EquipeDiretivaModalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hoje = timezone.localdate()
        cls.unidade = Unidade.objects.create(nome='Unidade Modal', sigla='UM')
        cls.outra = Unidade.objects.create(nome='Outra Unidade Modal', sigla='OM')
        cls.desup = User.objects.create_user(
            email='modal@desup.test', perfil=User.Perfil.DESUP, forcar_troca_senha=False,
        )
        cls.coord = User.objects.create_user(
            email='modal@unidade.test', perfil=User.Perfil.COORDENADOR_UNIDADE,
            unidade=cls.unidade, forcar_troca_senha=False,
        )
        contrato = ContractType.objects.create(nome='Contrato Modal', max_class_hours=20, max_classes=8)
        cls.professor = Professor.objects.create(
            id_funcional='MODAL-ID', rh_matricula='MODAL-MAT', rh_nome='Servidor Modal',
            tipo_contrato=contrato, unidade_principal=cls.unidade,
        )
        cls.curso = CourseUnit.objects.create(
            curso=Course.objects.create(nome='Z Curso Atual', sigla='ZCA'), unidade=cls.unidade,
        )
        cls.adicional = CourseUnit.objects.create(
            curso=Course.objects.create(nome='A Curso Adicional', sigla='ACA'), unidade=cls.unidade,
        )
        cls.externo = CourseUnit.objects.create(curso=cls.curso.curso, unidade=cls.outra)
        cls.inativo = CourseUnit.objects.create(
            curso=Course.objects.create(nome='Curso Inativo', sigla='CI'), unidade=cls.unidade, ativo=False,
        )
        cls.cargo = TipoCargoDiretivo.objects.create(
            nome='Cargo Modal por Curso', exige_curso=True, permite_multiplos=True,
            carga_reducao_horas=Decimal('4'),
        )
        ConfiguracaoCargoDiretivoUnidade.objects.create(
            cargo=cls.cargo, unidade=cls.unidade, carga_reducao_horas=Decimal('5'),
        )

    def criar_ocupacao(self):
        return OcupacaoEquipeDiretiva.objects.create(
            unidade=self.unidade, cargo=self.cargo, professor=self.professor, curso=self.curso,
            data_inicio=self.hoje, carga_reducao_horas=Decimal('7'), reducao_personalizada=True,
            criado_por=self.desup,
        )

    def dados(self, **alteracoes):
        return {
            'professor': self.professor.pk, 'data_inicio': self.hoje.isoformat(),
            'abrangencia_cursos': 'ESPECIFICOS', 'cursos': [self.curso.pk, self.adicional.pk],
            **alteracoes,
        }

    def enviar(self, url, dados):
        return self.client.post(url, dados, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    def test_edicao_abre_checklist_com_curso_atual_marcado(self):
        ocupacao = self.criar_ocupacao()
        form = OcupacaoEquipeDiretivaUnidadeForm(
            unidade=self.unidade, cargo=self.cargo, instance=ocupacao,
        )
        self.assertTrue(form.fields['curso'].widget.is_hidden)
        self.assertEqual(form['abrangencia_cursos'].value(), 'ESPECIFICOS')
        self.assertEqual(form['cursos'].value(), [str(self.curso.pk)])
        self.assertEqual(set(form.fields['cursos'].queryset), {self.curso, self.adicional})
        self.client.force_login(self.coord)
        page = self.client.get(reverse('core:equipe_diretiva_unidade'))
        self.assertContains(page, 'data-ocupacao-form')
        self.assertContains(page, 'fieldset data-abrangencia-cursos')
        self.assertContains(page, 'js/equipe-diretiva.js')

    def test_cadastro_sem_cursos_mostra_erro_no_modal_nos_dois_perfis(self):
        for user, url in (
            (self.coord, reverse('core:ocupacao_diretiva_unidade_create', args=[self.cargo.pk])),
            (self.desup, reverse('core:ocupacao_diretiva_create', args=[self.unidade.pk, self.cargo.pk])),
        ):
            with self.subTest(perfil=user.perfil):
                self.client.force_login(user)
                response = self.enviar(url, self.dados(cursos=[]))
                self.assertEqual(response.status_code, 422)
                self.assertIn('Selecione ao menos um curso.', response.json()['html'])
                self.assertNotIn('<html', response.json()['html'])
                self.assertFalse(OcupacaoEquipeDiretiva.objects.exists())

    def test_cadastro_todos_cria_so_cursos_ativos_da_unidade(self):
        self.client.force_login(self.coord)
        response = self.enviar(
            reverse('core:ocupacao_diretiva_unidade_create', args=[self.cargo.pk]),
            self.dados(abrangencia_cursos='TODOS', cursos=[]),
        )
        self.assertEqual(response.json(), {'redirect_url': reverse('core:equipe_diretiva_unidade')})
        self.assertEqual(
            set(OcupacaoEquipeDiretiva.objects.values_list('curso_id', flat=True)),
            {self.curso.pk, self.adicional.pk},
        )

    def test_edicao_varios_cursos_preserva_registro_atual_e_reducao_da_desup(self):
        ocupacao = self.criar_ocupacao()
        self.client.force_login(self.coord)
        response = self.enviar(
            reverse('core:ocupacao_diretiva_unidade_update', args=[ocupacao.pk]),
            self.dados(carga_reducao_horas='20', unidade=self.outra.pk, observacoes='Portaria atualizada'),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['redirect_url'], reverse('core:equipe_diretiva_unidade'))
        ocupacao.refresh_from_db()
        self.assertEqual(ocupacao.curso, self.curso)
        self.assertEqual(ocupacao.criado_por, self.desup)
        self.assertEqual(ocupacao.carga_reducao_horas, Decimal('7'))
        nova = OcupacaoEquipeDiretiva.objects.exclude(pk=ocupacao.pk).get()
        self.assertEqual(nova.curso, self.adicional)
        self.assertEqual(nova.criado_por, self.coord)
        self.assertEqual(nova.carga_reducao_horas, Decimal('5'))
        self.assertFalse(nova.reducao_personalizada)
        for item in (ocupacao, nova):
            self.assertEqual(item.unidade, self.unidade)
            self.assertEqual(item.observacoes, 'Portaria atualizada')
        self.assertTrue(ocupacao.reducao_personalizada)
        self.assertTrue(AuditoriaGlobal.objects.filter(acao='OCUPACAO_DIRETIVA_UNIDADE_ATUALIZADA').exists())

    def test_edicao_todos_expande_para_os_cursos_ativos(self):
        ocupacao = self.criar_ocupacao()
        self.client.force_login(self.coord)
        response = self.enviar(
            reverse('core:ocupacao_diretiva_unidade_update', args=[ocupacao.pk]),
            self.dados(abrangencia_cursos='TODOS', cursos=[]),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(OcupacaoEquipeDiretiva.objects.count(), 2)

    def test_conflito_em_curso_adicional_nao_salva_parcialmente(self):
        ocupacao = self.criar_ocupacao()
        OcupacaoEquipeDiretiva.objects.create(
            unidade=self.unidade, cargo=self.cargo, professor=self.professor, curso=self.adicional,
            data_inicio=self.hoje,
        )
        self.client.force_login(self.coord)
        response = self.enviar(
            reverse('core:ocupacao_diretiva_unidade_update', args=[ocupacao.pk]),
            self.dados(observacoes='Não deve salvar'),
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn('ocupação conflitante', response.json()['html'])
        ocupacao.refresh_from_db()
        self.assertEqual(ocupacao.observacoes, '')
        self.assertEqual(OcupacaoEquipeDiretiva.objects.count(), 2)

    def test_edicao_rejeita_curso_externo_inativo_ou_nenhum(self):
        ocupacao = self.criar_ocupacao()
        self.client.force_login(self.coord)
        for cursos in ([self.externo.pk], [self.inativo.pk], []):
            with self.subTest(cursos=cursos):
                response = self.enviar(
                    reverse('core:ocupacao_diretiva_unidade_update', args=[ocupacao.pk]),
                    self.dados(cursos=cursos),
                )
                self.assertEqual(response.status_code, 422)
                ocupacao.refresh_from_db()
                self.assertEqual(ocupacao.curso, self.curso)
                self.assertEqual(OcupacaoEquipeDiretiva.objects.count(), 1)

    def test_post_legado_de_edicao_continua_trocando_um_curso(self):
        ocupacao = self.criar_ocupacao()
        self.client.force_login(self.coord)
        response = self.client.post(
            reverse('core:ocupacao_diretiva_unidade_update', args=[ocupacao.pk]),
            {'professor': self.professor.pk, 'curso': self.adicional.pk, 'data_inicio': self.hoje.isoformat()},
        )
        self.assertRedirects(response, reverse('core:equipe_diretiva_unidade'))
        ocupacao.refresh_from_db()
        self.assertEqual(ocupacao.curso, self.adicional)
        self.assertEqual(OcupacaoEquipeDiretiva.objects.count(), 1)

    def criar_matriz(self, curso=None, unidade=None, turno='M', **kwargs):
        matriz = CurriculumMatrix.objects.create(
            curso=(curso or self.curso).curso, turno=turno, **kwargs,
        )
        matriz.unidades.add(unidade or self.unidade)
        return matriz

    def test_checklist_separa_turnos_vigentes_sem_duplicar_matrizes(self):
        self.criar_matriz(turno='M')
        self.criar_matriz(turno='M')
        self.criar_matriz(turno='N')
        self.criar_matriz(turno='T', is_rascunho=True)
        self.criar_matriz(turno='T', is_vigente=False)
        self.criar_matriz(turno='T', unidade=self.outra)
        for compartilhadas in (False, True):
            with self.subTest(compartilhadas=compartilhadas):
                form = OcupacaoEquipeDiretivaUnidadeForm(
                    unidade=self.unidade, cargo=self.cargo,
                    opcoes=OpcoesOcupacaoEquipeDiretiva(self.unidade) if compartilhadas else None,
                )
                choices = dict(form.fields['cursos'].choices)
                self.assertEqual(choices[f'{self.curso.pk}:M'], 'ZCA (Manhã)')
                self.assertEqual(choices[f'{self.curso.pk}:N'], 'ZCA (Noite)')
                self.assertNotIn(f'{self.curso.pk}:T', choices)
                self.assertNotIn(str(self.curso.pk), choices)
                self.assertEqual(choices[str(self.adicional.pk)], 'ACA (Turno não informado)')
                self.assertEqual(len(choices), 3)

    def test_cadastro_e_edicao_preservam_turnos_independentes_nos_dois_perfis(self):
        self.criar_matriz(turno='M')
        self.criar_matriz(turno='N')
        for user, url in (
            (self.coord, reverse('core:ocupacao_diretiva_unidade_create', args=[self.cargo.pk])),
            (self.desup, reverse('core:ocupacao_diretiva_create', args=[self.unidade.pk, self.cargo.pk])),
        ):
            with self.subTest(perfil=user.perfil):
                self.client.force_login(user)
                response = self.enviar(url, self.dados(cursos=[f'{self.curso.pk}:M', f'{self.curso.pk}:N']))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(set(OcupacaoEquipeDiretiva.objects.values_list('turno', flat=True)), {'M', 'N'})
                ocupacao = OcupacaoEquipeDiretiva.objects.get(turno='N')
                form = OcupacaoEquipeDiretivaUnidadeForm(unidade=self.unidade, cargo=self.cargo, instance=ocupacao)
                self.assertEqual(form['cursos'].value(), [f'{self.curso.pk}:N'])
                self.client.force_login(self.coord)
                response = self.enviar(
                    reverse('core:ocupacao_diretiva_unidade_update', args=[ocupacao.pk]),
                    self.dados(cursos=[f'{self.curso.pk}:N'], observacoes='Somente noite'),
                )
                self.assertEqual(response.status_code, 200)
                ocupacao.refresh_from_db()
                self.assertEqual(ocupacao.turno, 'N')
                self.assertEqual(ocupacao.observacoes, 'Somente noite')
                self.assertEqual(OcupacaoEquipeDiretiva.objects.get(turno='M').observacoes, '')
                self.client.force_login(user)
                duplicada = self.enviar(url, self.dados(cursos=[f'{self.curso.pk}:N']))
                self.assertEqual(duplicada.status_code, 422)
                OcupacaoEquipeDiretiva.objects.all().delete()

    def test_todos_os_cursos_inclui_todos_os_turnos(self):
        self.criar_matriz(turno='M')
        self.criar_matriz(turno='N')
        self.client.force_login(self.coord)
        response = self.enviar(
            reverse('core:ocupacao_diretiva_unidade_create', args=[self.cargo.pk]),
            self.dados(abrangencia_cursos='TODOS', cursos=[]),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(OcupacaoEquipeDiretiva.objects.values_list('curso_id', 'turno')),
            {(self.curso.pk, 'M'), (self.curso.pk, 'N'), (self.adicional.pk, '')},
        )

    def test_rejeita_turno_inexistente_e_oferta_de_outra_unidade(self):
        self.criar_matriz(turno='M')
        self.client.force_login(self.coord)
        for chave in (f'{self.curso.pk}:T', f'{self.externo.pk}:M'):
            with self.subTest(chave=chave):
                response = self.enviar(
                    reverse('core:ocupacao_diretiva_unidade_create', args=[self.cargo.pk]),
                    self.dados(cursos=[chave]),
                )
                self.assertEqual(response.status_code, 422)
                self.assertFalse(OcupacaoEquipeDiretiva.objects.exists())

    def test_vinculo_legado_pode_ser_editado_sem_escolher_turno(self):
        ocupacao = self.criar_ocupacao()
        self.criar_matriz(turno='M')
        self.client.force_login(self.coord)
        response = self.enviar(
            reverse('core:ocupacao_diretiva_unidade_update', args=[ocupacao.pk]),
            self.dados(cursos=[str(self.curso.pk)]),
        )
        self.assertEqual(response.status_code, 200)
        ocupacao.refresh_from_db()
        self.assertEqual(ocupacao.turno, '')
        self.assertEqual(ocupacao.carga_reducao_horas, Decimal('7'))
        self.assertEqual(OcupacaoEquipeDiretiva.objects.count(), 1)

    def test_desup_pode_habilitar_multiplos_e_unidade_adicionar_segundo_ocupante(self):
        cargo = TipoCargoDiretivo.objects.create(nome='Cargo com vários ocupantes')
        primeiro = OcupacaoEquipeDiretiva.objects.create(
            unidade=self.unidade, cargo=cargo, professor=self.professor, data_inicio=self.hoje,
        )
        self.client.force_login(self.desup)
        response = self.client.post(
            reverse('core:cargo_diretivo_unidade_update', args=[self.unidade.pk, cargo.pk]),
            {'nome': cargo.nome, 'carga_reducao_unidade': '5', 'permite_multiplos': 'on', 'ativo': 'on'},
        )
        self.assertEqual(response.status_code, 302)
        cargo.refresh_from_db()
        self.assertTrue(cargo.permite_multiplos)
        segundo = Professor.objects.create(
            id_funcional='MODAL-2', rh_matricula='MODAL-2', rh_nome='Segundo ocupante',
            tipo_contrato=self.professor.tipo_contrato, unidade_principal=self.unidade,
        )
        self.client.force_login(self.coord)
        page = self.client.get(reverse('core:equipe_diretiva_unidade'))
        self.assertContains(page, f"modalPreencherUnidade{cargo.pk}")
        response = self.enviar(
            reverse('core:ocupacao_diretiva_unidade_create', args=[cargo.pk]),
            {'professor': segundo.pk, 'data_inicio': self.hoje.isoformat()},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(OcupacaoEquipeDiretiva.objects.filter(cargo=cargo).count(), 2)
        self.assertTrue(OcupacaoEquipeDiretiva.objects.filter(pk=primeiro.pk).exists())

    def test_alerta_sala_com_resumo_curto_e_lista_recolhida(self):
        from apps.allocations.models import AlocacaoCurricular, AlocacaoTurmaDocente
        from apps.courses.models import CurricularComponent, MatrixComponent
        from apps.allocations.services import semestre_atual

        self.criar_ocupacao()
        matriz = self.criar_matriz()
        componente = MatrixComponent.objects.create(
            matriz=matriz,
            componente_curricular=CurricularComponent.objects.create(
                nome='Administração e Gerenciamento de Projetos', carga_horaria_padrao=360,
            ),
            periodo=1, carga_horaria=360,
        )
        alocacao = AlocacaoCurricular.objects.create(
            unidade=self.unidade, curso=self.curso, semestre=semestre_atual(), turno='M',
        )
        AlocacaoTurmaDocente.objects.create(
            alocacao_curricular=alocacao, componente_matriz=componente, docente=self.professor,
        )
        self.client.force_login(self.coord)
        response = self.client.get(reverse('core:equipe_diretiva_unidade'))
        alerta = response.content.decode().split('data-alerta-sala>', 1)[1].split('</details>', 1)[0]
        resumo = alerta.split('</summary>', 1)[0]
        self.assertIn('Docente também alocado em sala de aula (18h/sem).', resumo)
        self.assertNotIn('Administração e Gerenciamento de Projetos', resumo)
        self.assertIn('<li class="break-words">Administração e Gerenciamento de Projetos</li>', alerta)
        self.assertNotIn(' open', response.content.decode().split('data-alerta-sala>', 1)[0].rsplit('<details', 1)[1])
