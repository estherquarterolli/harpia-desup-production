"""Estados iniciais e carências já persistidas na alocação curricular."""

from django.template.loader import render_to_string
from django.test import override_settings

from apps.allocations.models import AlocacaoTurmaDocente, Carencia
from apps.allocations.services import componente_pendente, definir_escolha
from apps.allocations.tests_e2e import AlocacaoE2EBase


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class EstadosAlocacaoTests(AlocacaoE2EBase):
    def _slot(self, linha=None, **contexto):
        return render_to_string('allocations/partials/_slot_docente.html', {
            'comp': self.comp_algoritmos, 'linha': linha, 'user': self.desup, **contexto,
        })

    def test_inicial_cinza_sem_gravar_alocacao_ou_carencia(self):
        self.client.force_login(self.coord_a)
        for _ in range(2):
            pagina = self.client.get(self.url_tela)
            self.assertContains(pagina, 'data-current-id="NAO_INFORMADO"')
        html = self._slot()
        self.assertIn('placeholder="Não informado"', html)
        self.assertIn('bg-slate-50', html)
        self.assertNotIn('ac-state-carencia', html)
        self.assertNotIn('data-value="NAO_INFORMADO"', html)
        self.assertFalse(AlocacaoTurmaDocente.objects.exists())
        self.assertFalse(Carencia.objects.exists())
        self.assertTrue(componente_pendente(self.comp_algoritmos, []))

    def test_nova_linha_inicia_nao_informada_mesmo_com_componente_nao_oferecido(self):
        self.comp_algoritmos.status = 'NAO_OFERECIDA'
        html = self._slot(nova=True)
        self.assertIn('data-current-id="NAO_INFORMADO"', html)
        self.assertIn('placeholder="Não informado"', html)
        self.assertNotIn('ac-state-carencia', html)

    def test_carencia_explicita_fica_vermelha_e_persiste_ao_recarregar(self):
        self.client.force_login(self.coord_a)
        resposta = self.client.post(self._url_alocar(self.comp_algoritmos), {
            'docente_id': 'SEM_PROFESSOR',
        }, HTTP_ACCEPT='application/json', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resposta.status_code, 200)
        linha = AlocacaoTurmaDocente.objects.get(componente_matriz=self.comp_algoritmos)
        self.assertIsNone(linha.docente_id)
        self.assertEqual(linha.carencia.status, Carencia.StatusChoices.DECLARADA)
        html = self._slot(linha)
        self.assertIn('data-current-id="SEM_PROFESSOR"', html)
        self.assertIn('ac-state-carencia', html)
        self.assertIn('placeholder="Sem professor"', html)
        pagina = self.client.get(self.url_tela)
        self.assertContains(pagina, f'data-linha-id="{linha.pk}"\n       data-current-id="SEM_PROFESSOR"')
        self.assertTrue(componente_pendente(self.comp_algoritmos, [linha]))

    def test_docente_resolve_carencia_e_nao_oferecido_permanece_distinto(self):
        _, linha, _ = definir_escolha(self.comp_algoritmos, self.unidade_a, 'SEM_PROFESSOR')
        definir_escolha(self.comp_algoritmos, self.unidade_a, str(self.prof_a1.pk))
        linha.refresh_from_db()
        self.assertEqual(linha.carencia.status, Carencia.StatusChoices.RESOLVIDA)
        self.assertNotIn('ac-state-carencia', self._slot(linha))
        self.assertFalse(componente_pendente(self.comp_algoritmos, [linha]))
        definir_escolha(self.comp_algoritmos, self.unidade_a, 'NAO_OFERECIDA')
        self.comp_algoritmos.refresh_from_db()
        html = self._slot()
        self.assertIn('data-current-id="NAO_OFERECIDA"', html)
        self.assertIn('placeholder="Não oferecido"', html)
        self.assertFalse(componente_pendente(self.comp_algoritmos, []))
