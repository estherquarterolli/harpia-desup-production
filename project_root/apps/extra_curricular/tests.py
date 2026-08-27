from django.test import TestCase
from apps.extra_curricular.models import OrientacaoTCC, AtividadeExtensionista, PendenciaExtra
from apps.professors.models import Professor, ContractType
from apps.core.models import Unidade

class ExtraCurricularApprovedTests(TestCase):
    def setUp(self):
        self.unidade = Unidade.objects.create(nome="Unidade Teste", sigla="UT")
        self.contrato = ContractType.objects.create(
            nome="Ensino Superior",
            max_class_hours=20,
            max_classes=10
        )
        self.professor = Professor.objects.create(
            rh_nome="Professor Teste",
            rh_email="teste@teste.com",
            id_funcional="12345",
            rh_matricula="M12345",
            unidade_principal=self.unidade,
            tipo_contrato=self.contrato
        )
        self.pendencia = PendenciaExtra.objects.create(
            professor=self.professor,
            unidade=self.unidade,
            semestre="2026.1"
        )

    def test_orientacao_tcc_approved_calculation(self):
        """Test calculation of approved hours for TCC based on approved students."""
        # 1. Default: approved students is None, use requested students
        tcc = OrientacaoTCC.objects.create(
            pendencia=self.pendencia,
            num_orientandos=4
        )
        # 4 * 0.5 = 2.0
        self.assertEqual(tcc.carga_horaria, 2.0)
        self.assertEqual(tcc.horas_aprovadas, 2.0)
        self.assertEqual(tcc.ch_aprovada, 2.0)

        # 2. Set approved students
        tcc.num_orientandos_aprovados = 2
        tcc.save()
        # 2 * 0.5 = 1.0
        self.assertEqual(tcc.horas_aprovadas, 1.0)
        self.assertEqual(tcc.ch_aprovada, 1.0)

        # 3. Max limit (8 students -> 4h)
        tcc.num_orientandos_aprovados = 10 # Should be capped at 8 if we use logic, but field has validator. 
        # Logic in plan says: min(round(num_orientandos_aprovados * 0.5, 1), 4.0)
        tcc.save()
        self.assertEqual(tcc.horas_aprovadas, 4.0)
        self.assertEqual(tcc.ch_aprovada, 4.0)

    def test_atividade_extensionista_approved_calculation(self):
        """Test calculation of approved hours for Extension based on approved students."""
        # 1. Default
        ext = AtividadeExtensionista.objects.create(
            pendencia=self.pendencia,
            num_estudantes=10
        )
        # 10 * 0.5 = 5.0
        self.assertEqual(ext.carga_horaria, 5.0)
        self.assertEqual(ext.horas_aprovadas, 5.0)
        self.assertEqual(ext.ch_aprovada, 5.0)

        # 2. Set approved students
        ext.num_estudantes_aprovados = 6
        ext.save()
        # 6 * 0.5 = 3.0
        self.assertEqual(ext.horas_aprovadas, 3.0)
        self.assertEqual(ext.ch_aprovada, 3.0)
