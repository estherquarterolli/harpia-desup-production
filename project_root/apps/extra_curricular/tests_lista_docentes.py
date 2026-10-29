"""Listagem extracurricular: todos os docentes aparecem; quem tem pendência fica no topo."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import (
    OcupacaoEquipeDiretiva,
    ReadaptacaoProfessor,
    TipoCargoDiretivo,
    Unidade,
)
from apps.extra_curricular.services import (
    get_pendencias_data,
    get_professores_com_pendencia,
)
from apps.extra_curricular.utils import semestre_atual
from apps.professors.models import ContractType, Professor


class ListaTodosOsDocentesTests(TestCase):
    def setUp(self):
        self.hoje = timezone.localdate()
        self.unidade = Unidade.objects.create(nome="Unidade Lista", sigla="UL")
        self.contrato = ContractType.objects.create(
            nome="Superior", max_class_hours=20, max_classes=10,
        )
        self.coord = User.objects.create_user(
            email="coord.lista@teste.com", perfil="COORDENADOR_UNIDADE",
            unidade=self.unidade, forcar_troca_senha=False,
        )

    def _prof(self, nome, matricula):
        return Professor.objects.create(
            rh_nome=nome, rh_email=f"{matricula}@teste.com", id_funcional=matricula,
            rh_matricula=matricula, unidade_principal=self.unidade,
            tipo_contrato=self.contrato,
        )

    def test_readaptado_aparece_sem_cobranca(self):
        pendente = self._prof("Zeca Pendente", "1")
        readaptado = self._prof("Ana Readaptada", "2")
        ReadaptacaoProfessor.objects.create(
            professor=readaptado, data_inicio=self.hoje - timedelta(days=3),
        )

        profs = get_professores_com_pendencia(self.unidade.pk, semestre_atual())

        self.assertEqual({p.pk for p in profs}, {pendente.pk, readaptado.pk})
        self.assertEqual(profs[0].pk, pendente.pk)  # pendência no topo, apesar da ordem alfabética
        self.assertFalse(profs[1].tem_pendencia_ch)

        linhas = {l["professor"].pk: l for l in get_pendencias_data(self.unidade.pk, semestre_atual())}
        self.assertEqual(linhas[readaptado.pk]["meta_horas"], 0)
        self.assertEqual(linhas[readaptado.pk]["ch_faltante"], 0)
        self.assertEqual(linhas[pendente.pk]["ch_faltante"], 20)

    def test_reducao_da_equipe_diretiva_abate_a_meta(self):
        cargo = TipoCargoDiretivo.objects.create(nome="Direção Lista", codigo="DIRECAO_LISTA")
        diretor = self._prof("Beto Diretor", "3")
        OcupacaoEquipeDiretiva.objects.create(
            unidade=self.unidade, cargo=cargo, professor=diretor,
            data_inicio=self.hoje - timedelta(days=5), carga_reducao_horas=Decimal("20.00"),
        )
        linhas = get_pendencias_data(self.unidade.pk, semestre_atual())
        linha = next(l for l in linhas if l["professor"].pk == diretor.pk)
        self.assertEqual(linha["meta_horas"], 0)
        self.assertEqual(linha["ch_faltante"], 0)

    def test_estagio_vigente_conta_como_ch_justificada(self):
        from apps.core.models import AtividadeEstagioSupervisao

        prof = self._prof("Caio Estagio", "4")
        AtividadeEstagioSupervisao.objects.create(
            unidade=self.unidade, professor=prof, semestre=semestre_atual(),
            data_inicio=self.hoje - timedelta(days=5), carga_horaria_semanal=Decimal("20.00"),
        )
        linhas = get_pendencias_data(self.unidade.pk, semestre_atual())
        linha = next(l for l in linhas if l["professor"].pk == prof.pk)
        self.assertEqual(linha["ch_faltante"], 0)

    def test_tela_de_nova_justificativa_lista_readaptado(self):
        readaptado = self._prof("Ana Readaptada", "2")
        ReadaptacaoProfessor.objects.create(
            professor=readaptado, data_inicio=self.hoje - timedelta(days=3),
        )
        self.client.force_login(self.coord)
        resp = self.client.get(reverse("extra_curricular:pendencia_create"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Docentes com Pendência (Semestre:")
        self.assertContains(resp, "ANA READAPTADA")
        self.assertContains(resp, "Readaptado")
