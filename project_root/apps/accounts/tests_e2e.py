"""
Testes END-TO-END do app `accounts`.

Diferente de `apps/accounts/tests.py` (que valida peças isoladas — modelo,
validador, funções de roteamento, uma view por vez), aqui cada teste percorre
uma **jornada completa** do usuário pelo `self.client`: login, middleware,
templates, e-mail, banco e sessão participam de ponta a ponta.

Notas de ambiente importantes para ler os testes:

* O test runner do Django força `settings.DEBUG = False`. Logo o rate-limit de
  troca de senha (CORR-020, que só é ignorado em DEBUG) está **ativo** aqui.
* O bloqueio por tentativas de login vive no **cache** (LocMemCache), que é
  global ao processo e vaza entre testes — por isso `cache.clear()` no setUp.
* Os e-mails saem dentro de `transaction.on_commit`, então todo POST que dispara
  e-mail precisa de `self.captureOnCommitCallbacks(execute=True)`.
"""

import re
import unittest
from datetime import timedelta

from django.conf import settings
from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import (
    DEFAULT_USER_PASSWORD,
    PasswordResetRequest,
    SelfPasswordChangeRequest,
    User,
)
from apps.core.models import AuditoriaGlobal, Notificacao, Unidade

# URLs usadas nas jornadas (caminhos literais: é assim que o usuário navega).
URL_LOGIN = '/login/'
URL_LOGOUT = '/accounts/logout/'
URL_PERFIL = '/accounts/perfil/'
URL_TROCA_SENHA = '/accounts/password_change/'
URL_ESQUECI_SENHA = '/accounts/forgot-password/'
URL_DASH_DESUP = '/dashboard/desup/'
URL_DASH_UNIDADE = '/dashboard/unidade/'
URL_ADMIN = '/admin/'


class BaseE2ETestCase(TestCase):
    """Infraestrutura comum às jornadas (limpeza de cache + atalhos de navegação)."""

    def setUp(self):
        # O contador de tentativas de login é guardado em cache por e-mail e
        # sobrevive ao rollback da transação do TestCase.
        cache.clear()
        self.addCleanup(cache.clear)

    # ── atalhos de navegação ────────────────────────────────────────
    def fazer_login(self, email, senha, client=None, **extra):
        """POST no formulário de login, exatamente como o navegador faria."""
        client = client or self.client
        return client.post(URL_LOGIN, {'email': email, 'password': senha}, **extra)

    def esta_autenticado(self, client=None):
        client = (client or self.client)
        return '_auth_user_id' in client.session

    # ── asserções de apoio ──────────────────────────────────────────
    def assertMandaParaLogin(self, response, msg=None):
        """A resposta é um redirect para a tela de login (sessão ausente/expirada)."""
        self.assertEqual(response.status_code, 302, msg)
        self.assertTrue(
            response['Location'].startswith(URL_LOGIN),
            msg or f"Esperava redirect para {URL_LOGIN}, veio {response['Location']}",
        )

    @staticmethod
    def extrair_link(corpo, prefixo):
        """Extrai do corpo do e-mail o primeiro link que contenha `prefixo`."""
        achados = re.findall(r'https?://\S+', corpo)
        for link in achados:
            if prefixo in link:
                return link.rstrip('.,')
        raise AssertionError(
            f"Nenhum link contendo {prefixo!r} no corpo do e-mail:\n{corpo}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# Cenário 1 — Primeiro acesso obrigatório
# ══════════════════════════════════════════════════════════════════════════════
class PrimeiroAcessoObrigatorioE2ETests(BaseE2ETestCase):
    """
    Jornada do usuário recém-criado pela DESUP: ele recebe a senha padrão, é
    obrigado a trocá-la antes de usar qualquer tela, e só depois entra no
    sistema normalmente.
    """

    def setUp(self):
        super().setUp()
        self.unidade = Unidade.objects.create(nome="Unidade E2E Primeiro Acesso", sigla="UPA")
        self.senha_inicial = DEFAULT_USER_PASSWORD
        self.senha_nova = "Comeco@2026"
        self.novato = User.objects.create_user(
            email="novato_e2e@teste.com",
            password=self.senha_inicial,
            perfil=User.Perfil.COORDENADOR_UNIDADE,
            unidade=self.unidade,
        )

    def test_jornada_do_primeiro_acesso_ate_o_login_com_a_senha_nova(self):
        """Login -> bloqueio em todas as telas -> troca -> logout -> novo login."""
        self.assertTrue(self.novato.forcar_troca_senha, "Usuário novo nasce com a flag ligada.")

        # 1) Login com a senha padrão funciona e roteia pelo perfil.
        resposta = self.fazer_login(self.novato.email, self.senha_inicial)
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta['Location'], URL_DASH_UNIDADE)
        self.assertTrue(self.esta_autenticado())

        # 2) Qualquer tela do sistema devolve o usuário para a troca de senha.
        for url in (URL_DASH_UNIDADE, URL_PERFIL, '/professores/', '/'):
            with self.subTest(url=url):
                bloqueada = self.client.get(url)
                self.assertEqual(bloqueada.status_code, 302)
                self.assertEqual(bloqueada['Location'], URL_TROCA_SENHA)

        # 3) A tela de troca mostra o formulário (e não o pedido de link por e-mail).
        formulario = self.client.get(URL_TROCA_SENHA)
        self.assertEqual(formulario.status_code, 200)
        self.assertTemplateUsed(formulario, 'registration/password_change_form.html')
        self.assertContains(formulario, 'você deve alterar a sua senha antes de prosseguir')
        self.assertContains(formulario, 'name="new_password1"')

        # 4) Troca efetivada: volta ao login com o aviso de sucesso.
        troca = self.client.post(URL_TROCA_SENHA, {
            'new_password1': self.senha_nova,
            'new_password2': self.senha_nova,
        })
        self.assertEqual(troca.status_code, 302)
        self.assertEqual(troca['Location'], f'{URL_LOGIN}?changed=1')

        self.novato.refresh_from_db()
        self.assertFalse(self.novato.forcar_troca_senha)
        self.assertTrue(self.novato.check_password(self.senha_nova))
        self.assertTrue(
            AuditoriaGlobal.objects.filter(acao="PASSWORD_CHANGED_FIRST_LOGIN").exists()
        )

        # 5) A sessão foi encerrada de verdade pela própria view.
        self.assertFalse(self.esta_autenticado())
        self.assertMandaParaLogin(self.client.get(URL_DASH_UNIDADE))

        # 6) A senha antiga não vale mais.
        recusado = self.fazer_login(self.novato.email, self.senha_inicial)
        self.assertEqual(recusado.status_code, 200)
        self.assertContains(recusado, 'E-mail ou senha inválidos.')
        self.assertFalse(self.esta_autenticado())

        # 7) Com a senha nova ele entra e NÃO é mais forçado a nada.
        entrada = self.fazer_login(self.novato.email, self.senha_nova)
        self.assertEqual(entrada.status_code, 302)
        self.assertEqual(entrada['Location'], URL_DASH_UNIDADE)

        dashboard = self.client.get(URL_DASH_UNIDADE)
        self.assertEqual(dashboard.status_code, 200)
        self.assertContains(dashboard, self.novato.email)

    def test_usuario_forcado_recebe_hx_redirect_em_navegacao_htmx(self):
        """Nas telas carregadas por HTMX o bloqueio vira header `HX-Redirect`."""
        self.fazer_login(self.novato.email, self.senha_inicial)

        resposta = self.client.get(URL_DASH_UNIDADE, HTTP_HX_REQUEST='true')

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta['HX-Redirect'], URL_TROCA_SENHA)

    def test_usuario_forcado_ainda_consegue_sair_do_sistema(self):
        """O 'Cancelar e Sair' da tela de troca precisa funcionar (senão ele fica preso)."""
        self.fazer_login(self.novato.email, self.senha_inicial)

        saida = self.client.post(URL_LOGOUT)

        self.assertEqual(saida.status_code, 302)
        self.assertFalse(self.esta_autenticado())

    def test_senha_fraca_mantem_o_usuario_preso_na_troca(self):
        """Reprovada pelos validadores, a jornada não avança e a flag continua ligada."""
        self.fazer_login(self.novato.email, self.senha_inicial)

        recusa = self.client.post(URL_TROCA_SENHA, {
            'new_password1': 'senha123',
            'new_password2': 'senha123',
        })

        self.assertEqual(recusa.status_code, 200)
        self.novato.refresh_from_db()
        self.assertTrue(self.novato.forcar_troca_senha)
        self.assertTrue(self.novato.check_password(self.senha_inicial))
        # Continua barrado nas demais telas.
        self.assertEqual(self.client.get(URL_DASH_UNIDADE)['Location'], URL_TROCA_SENHA)


# ══════════════════════════════════════════════════════════════════════════════
# Cenário 2 — Bloqueio por tentativas de login
# ══════════════════════════════════════════════════════════════════════════════
class BloqueioPorTentativasE2ETests(BaseE2ETestCase):
    """Regra #10: 5 tentativas erradas bloqueiam a conta por 15 minutos."""

    def setUp(self):
        super().setUp()
        self.senha = "Correta@2026"
        self.alvo = User.objects.create_user(
            email="alvo_bloqueio@teste.com",
            password=self.senha,
            perfil=User.Perfil.DESUP,
            forcar_troca_senha=False,
        )
        self.vizinho = User.objects.create_user(
            email="vizinho_bloqueio@teste.com",
            password=self.senha,
            perfil=User.Perfil.DESUP,
            forcar_troca_senha=False,
        )

    def test_jornada_de_bloqueio_apos_cinco_tentativas(self):
        """Avisos regressivos nas 4 primeiras, silêncio na 5ª, bloqueio na 6ª."""
        avisos_esperados = {
            1: 'mais 4 tentativas',
            2: 'mais 3 tentativas',
            3: 'mais 2 tentativas',
            4: 'mais 1 tentativa antes',   # singular
        }

        for tentativa in range(1, 6):
            with self.subTest(tentativa=tentativa):
                resposta = self.fazer_login(self.alvo.email, 'chute-errado')
                self.assertEqual(resposta.status_code, 200)
                self.assertContains(resposta, 'E-mail ou senha inválidos.')
                if tentativa in avisos_esperados:
                    self.assertContains(resposta, avisos_esperados[tentativa])
                else:
                    # Na 5ª não sobra tentativa nenhuma — nada de aviso regressivo.
                    self.assertNotContains(resposta, 'antes do bloqueio temporário')
                self.assertFalse(self.esta_autenticado())

        # 6ª tentativa: mesmo com a senha CERTA a conta está bloqueada.
        bloqueada = self.fazer_login(self.alvo.email, self.senha)
        self.assertEqual(bloqueada.status_code, 200)
        self.assertContains(bloqueada, 'Conta bloqueada temporariamente por excesso de tentativas.')
        self.assertFalse(self.esta_autenticado())

    def test_bloqueio_e_por_conta_e_nao_derruba_os_demais_usuarios(self):
        for _ in range(5):
            self.fazer_login(self.alvo.email, 'chute-errado')

        entrada = self.fazer_login(self.vizinho.email, self.senha)

        self.assertEqual(entrada.status_code, 302)
        self.assertEqual(entrada['Location'], URL_DASH_DESUP)

    def test_login_bem_sucedido_zera_o_contador(self):
        for _ in range(3):
            self.fazer_login(self.alvo.email, 'chute-errado')

        entrada = self.fazer_login(self.alvo.email, self.senha)
        self.assertEqual(entrada.status_code, 302)

        # O contador voltou do zero: o próximo erro anuncia 4 tentativas restantes.
        recomeco = self.fazer_login(self.alvo.email, 'chute-errado')
        self.assertContains(recomeco, 'mais 4 tentativas')

    def test_bloqueio_tambem_vale_no_login_via_htmx(self):
        for tentativa in range(1, 6):
            resposta = self.fazer_login(self.alvo.email, 'chute-errado', HTTP_HX_REQUEST='true')
            self.assertEqual(resposta.status_code, 200)
            self.assertIn(b'E-mail ou senha inv', resposta.content)
            self.assertNotIn('HX-Redirect', resposta.headers)

        bloqueada = self.fazer_login(self.alvo.email, self.senha, HTTP_HX_REQUEST='true')

        self.assertEqual(bloqueada.status_code, 200)
        self.assertIn('Conta bloqueada temporariamente', bloqueada.content.decode())
        self.assertNotIn('HX-Redirect', bloqueada.headers)
        self.assertFalse(self.esta_autenticado())


# ══════════════════════════════════════════════════════════════════════════════
# Cenário 3, 4 e 5 — Troca de senha voluntária por link de e-mail
# ══════════════════════════════════════════════════════════════════════════════
class TrocaSenhaVoluntariaE2ETests(BaseE2ETestCase):
    """
    Usuário já ambientado (`forcar_troca_senha=False`) pede o link, recebe o
    e-mail, abre o link e define a nova senha.
    """

    def setUp(self):
        super().setUp()
        self.senha_atual = "Atual@2026"
        self.senha_nova = "Renovada@2026"
        self.usuario = User.objects.create_user(
            email="voluntario_e2e@teste.com",
            password=self.senha_atual,
            perfil=User.Perfil.DESUP,
            forcar_troca_senha=False,
        )
        self.fazer_login(self.usuario.email, self.senha_atual)

    def _pedir_link(self):
        """Executa o POST que dispara o e-mail e devolve a resposta."""
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(URL_TROCA_SENHA, {})

    def test_ambiente_de_teste_roda_com_debug_desligado(self):
        """Guarda-chuva: o rate-limit CORR-020 só existe porque DEBUG é False aqui."""
        self.assertFalse(settings.DEBUG)

    def test_jornada_completa_do_link_ate_o_login_com_a_senha_nova(self):
        # 1) A tela pede confirmação, sem campo de senha e sem campo de e-mail.
        prompt = self.client.get(URL_TROCA_SENHA)
        self.assertEqual(prompt.status_code, 200)
        self.assertTemplateUsed(prompt, 'registration/password_change_email_prompt.html')
        self.assertContains(prompt, self.usuario.email)
        self.assertNotContains(prompt, 'name="new_password1"')

        # 2) Pedido do link -> e-mail na caixa do próprio usuário.
        pedido = self._pedir_link()
        self.assertEqual(pedido.status_code, 200)
        self.assertContains(pedido, 'Enviamos um link de troca de senha para')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.usuario.email])

        token_db = SelfPasswordChangeRequest.objects.get(user=self.usuario)
        self.assertFalse(token_db.usado)

        # 3) O usuário abre o link do e-mail — de outro navegador, sem sessão.
        link = self.extrair_link(mail.outbox[0].body, '/accounts/password_change/confirm/')
        self.assertIn(str(token_db.token), link)

        navegador_do_email = self.client_class()
        abertura = navegador_do_email.get(link)
        self.assertEqual(abertura.status_code, 200)
        self.assertTemplateUsed(abertura, 'registration/password_change_form.html')

        # 4) Define a nova senha.
        confirmacao = navegador_do_email.post(link, {
            'new_password1': self.senha_nova,
            'new_password2': self.senha_nova,
        })
        self.assertEqual(confirmacao.status_code, 302)
        self.assertIn(f'{URL_LOGIN}?changed=1', confirmacao['Location'])

        # 5) Token consumido e auditado.
        token_db.refresh_from_db()
        self.assertTrue(token_db.usado)
        self.assertIsNotNone(token_db.usado_em)
        self.assertTrue(
            AuditoriaGlobal.objects.filter(acao="PASSWORD_CHANGED_BY_EMAIL_TOKEN").exists()
        )

        # 6) A sessão antiga (aberta antes da troca) morre junto com a senha.
        self.assertMandaParaLogin(self.client.get(URL_DASH_DESUP))

        # 7) Senha velha recusada, senha nova aceita.
        novo_navegador = self.client_class()
        recusa = self.fazer_login(self.usuario.email, self.senha_atual, client=novo_navegador)
        self.assertEqual(recusa.status_code, 200)
        self.assertContains(recusa, 'E-mail ou senha inválidos.')

        entrada = self.fazer_login(self.usuario.email, self.senha_nova, client=novo_navegador)
        self.assertEqual(entrada.status_code, 302)
        self.assertEqual(entrada['Location'], URL_DASH_DESUP)

    def test_segundo_pedido_no_mesmo_dia_e_bloqueado_mas_o_primeiro_link_segue_valido(self):
        """CORR-020 ativo (DEBUG=False): o rate-limit não pode invalidar o link já enviado."""
        self._pedir_link()
        link = self.extrair_link(mail.outbox[0].body, '/accounts/password_change/confirm/')

        segundo = self._pedir_link()
        self.assertEqual(segundo.status_code, 200)
        self.assertContains(segundo, 'nas últimas 24 horas')
        self.assertEqual(SelfPasswordChangeRequest.objects.filter(user=self.usuario).count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(
            AuditoriaGlobal.objects.filter(acao="PASSWORD_CHANGE_RATE_LIMITED").exists()
        )

        # O link do primeiro pedido continua funcionando normalmente.
        conclusao = self.client_class().post(link, {
            'new_password1': self.senha_nova,
            'new_password2': self.senha_nova,
        })
        self.assertEqual(conclusao.status_code, 302)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password(self.senha_nova))

    def test_link_expirado_nao_troca_a_senha(self):
        """O token vale 1 hora; depois disso só sobra a mensagem de erro."""
        self._pedir_link()
        link = self.extrair_link(mail.outbox[0].body, '/accounts/password_change/confirm/')
        SelfPasswordChangeRequest.objects.filter(user=self.usuario).update(
            criado_em=timezone.now() - timedelta(hours=1, minutes=1)
        )

        navegador = self.client_class()
        abertura = navegador.get(link)
        self.assertEqual(abertura.status_code, 200)
        self.assertContains(abertura, 'Este link de troca de senha expirou ou ja foi utilizado.')

        tentativa = navegador.post(link, {
            'new_password1': self.senha_nova,
            'new_password2': self.senha_nova,
        })
        self.assertEqual(tentativa.status_code, 200)
        self.assertContains(tentativa, 'Este link de troca de senha expirou ou ja foi utilizado.')

        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password(self.senha_atual))
        self.assertTrue(
            AuditoriaGlobal.objects.filter(acao="PASSWORD_CHANGE_TOKEN_INVALID").exists()
        )

    def test_link_reutilizado_nao_troca_a_senha_de_novo(self):
        """Depois de consumido, o mesmo link não pode servir para uma segunda troca."""
        self._pedir_link()
        link = self.extrair_link(mail.outbox[0].body, '/accounts/password_change/confirm/')
        navegador = self.client_class()

        primeira = navegador.post(link, {
            'new_password1': self.senha_nova,
            'new_password2': self.senha_nova,
        })
        self.assertEqual(primeira.status_code, 302)

        senha_do_invasor = "Sequestro@2026"
        segunda = navegador.post(link, {
            'new_password1': senha_do_invasor,
            'new_password2': senha_do_invasor,
        })

        self.assertEqual(segunda.status_code, 200)
        self.assertContains(segunda, 'Este link de troca de senha expirou ou ja foi utilizado.')
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password(self.senha_nova))
        self.assertFalse(self.usuario.check_password(senha_do_invasor))

    def test_token_inexistente_ou_malformado_nao_abre_a_tela(self):
        casos = {
            'inexistente': '/accounts/password_change/confirm/11111111-2222-3333-4444-555555555555/',
            'malformado': '/accounts/password_change/confirm/nao-e-um-uuid/',
        }
        for nome, url in casos.items():
            with self.subTest(caso=nome):
                self.assertEqual(self.client.get(url).status_code, 404)

    def test_pedido_de_link_exige_sessao(self):
        """Sem login o fluxo inteiro é inacessível — ninguém pede link para terceiros."""
        anonimo = self.client_class()

        self.assertMandaParaLogin(anonimo.get(URL_TROCA_SENHA))
        with self.captureOnCommitCallbacks(execute=True):
            self.assertMandaParaLogin(anonimo.post(URL_TROCA_SENHA, {}))
        self.assertEqual(SelfPasswordChangeRequest.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)


# ══════════════════════════════════════════════════════════════════════════════
# Cenário 6 — Esqueci minha senha + aprovação da DESUP
# ══════════════════════════════════════════════════════════════════════════════
class EsqueciMinhaSenhaE2ETests(BaseE2ETestCase):
    """
    Fluxo de quem perdeu o acesso: o pedido é feito sem sessão e alguém com
    poder de aprovação (DESUP, superusuário ou coordenador da mesma unidade)
    reseta a senha para o padrão do sistema.
    """

    def setUp(self):
        super().setUp()
        self.senha = "Aprova@2026"
        self.unidade = Unidade.objects.create(nome="Unidade E2E Reset", sigla="URS")
        self.outra_unidade = Unidade.objects.create(nome="Unidade E2E Reset Alheia", sigla="URA")

        self.esquecido = User.objects.create_user(
            email="esquecido_e2e@teste.com",
            password="SenhaPerdida@2026",
            perfil=User.Perfil.COORDENADOR_UNIDADE,
            unidade=self.unidade,
            forcar_troca_senha=False,
        )
        self.desup = User.objects.create_user(
            email="desup_reset_e2e@teste.com",
            password=self.senha,
            perfil=User.Perfil.DESUP,
            forcar_troca_senha=False,
        )
        self.colega_da_unidade = User.objects.create_user(
            email="colega_reset_e2e@teste.com",
            password=self.senha,
            perfil=User.Perfil.COORDENADOR_UNIDADE,
            unidade=self.unidade,
            forcar_troca_senha=False,
        )
        self.coord_de_fora = User.objects.create_user(
            email="forasteiro_reset_e2e@teste.com",
            password=self.senha,
            perfil=User.Perfil.COORDENADOR_UNIDADE,
            unidade=self.outra_unidade,
            forcar_troca_senha=False,
        )

    def _pedir_reset(self, email=None):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client_class().post(
                URL_ESQUECI_SENHA, {'email': email or self.esquecido.email}
            )

    def test_jornada_completa_do_esqueci_senha_ate_o_novo_primeiro_acesso(self):
        # 1) Tela pública acessível sem sessão.
        tela = self.client_class().get(URL_ESQUECI_SENHA)
        self.assertEqual(tela.status_code, 200)
        self.assertTemplateUsed(tela, 'registration/forgot_password.html')

        # 2) Pedido registrado + notificação + e-mail para quem aprova.
        pedido = self._pedir_reset()
        self.assertEqual(pedido.status_code, 200)
        self.assertContains(pedido, 'Sua solicitação foi enviada para o administrador do DESUP')

        solicitacao = PasswordResetRequest.objects.get(user=self.esquecido)
        self.assertFalse(solicitacao.finalizado)

        self.assertEqual(len(mail.outbox), 1)
        destinatarios = set(mail.outbox[0].to)
        self.assertIn(self.desup.email, destinatarios)
        self.assertIn(self.colega_da_unidade.email, destinatarios)
        self.assertNotIn(self.coord_de_fora.email, destinatarios)

        self.assertTrue(
            Notificacao.objects.filter(
                destinatario=self.desup, titulo="Solicitação de Reset de Senha"
            ).exists()
        )

        # 3) A DESUP abre o link de aprovação que veio no e-mail.
        link = self.extrair_link(mail.outbox[0].body, '/accounts/reset/aprovar/')
        navegador_desup = self.client_class()
        self.fazer_login(self.desup.email, self.senha, client=navegador_desup)

        revisao = navegador_desup.get(link)
        self.assertEqual(revisao.status_code, 200)
        self.assertContains(revisao, self.esquecido.email)
        self.assertContains(revisao, 'APROVAR E RESETAR AGORA')

        # 4) Aprovação: senha volta ao padrão e o usuário vira "primeiro acesso".
        aprovacao = navegador_desup.post(link)
        self.assertEqual(aprovacao.status_code, 200)
        self.assertContains(aprovacao, 'resetada com sucesso')

        self.esquecido.refresh_from_db()
        solicitacao.refresh_from_db()
        self.assertTrue(self.esquecido.check_password(DEFAULT_USER_PASSWORD))
        self.assertTrue(self.esquecido.forcar_troca_senha)
        self.assertTrue(solicitacao.finalizado)
        self.assertIsNotNone(solicitacao.finalizado_em)
        self.assertEqual(solicitacao.aprovado_por, self.desup)

        # 5) O usuário entra com a senha padrão e cai no fluxo de troca obrigatória.
        navegador_usuario = self.client_class()
        entrada = self.fazer_login(
            self.esquecido.email, DEFAULT_USER_PASSWORD, client=navegador_usuario
        )
        self.assertEqual(entrada.status_code, 302)
        self.assertEqual(navegador_usuario.get(URL_DASH_UNIDADE)['Location'], URL_TROCA_SENHA)

    def test_quem_pode_e_quem_nao_pode_aprovar_o_reset(self):
        self._pedir_reset()
        solicitacao = PasswordResetRequest.objects.get(user=self.esquecido)
        url = f'/accounts/reset/aprovar/{solicitacao.token}/'

        # Anônimo: nem chega a ver a tela.
        self.assertMandaParaLogin(self.client_class().get(url))

        # Coordenador de outra unidade: 403 explícito.
        navegador_forasteiro = self.client_class()
        self.fazer_login(self.coord_de_fora.email, self.senha, client=navegador_forasteiro)
        negado = navegador_forasteiro.get(url)
        self.assertEqual(negado.status_code, 403)
        # SEC-002: mensagem única para todos os casos de recusa.
        self.assertIn('não tem permissão', negado.content.decode())

        # E o POST também é barrado (não basta esconder a tela).
        negado_post = navegador_forasteiro.post(url)
        self.assertEqual(negado_post.status_code, 403)
        self.esquecido.refresh_from_db()
        self.assertFalse(self.esquecido.check_password(DEFAULT_USER_PASSWORD))

        # Coordenador da mesma unidade: pode aprovar.
        navegador_colega = self.client_class()
        self.fazer_login(self.colega_da_unidade.email, self.senha, client=navegador_colega)
        permitido = navegador_colega.get(url)
        self.assertEqual(permitido.status_code, 200)
        self.assertContains(permitido, self.esquecido.email)

    def test_token_de_aprovacao_inexistente_retorna_404(self):
        navegador_desup = self.client_class()
        self.fazer_login(self.desup.email, self.senha, client=navegador_desup)

        resposta = navegador_desup.get(
            '/accounts/reset/aprovar/99999999-8888-7777-6666-555555555555/'
        )

        self.assertEqual(resposta.status_code, 404)

    def test_solicitacao_ja_aprovada_nao_reseta_a_senha_de_novo(self):
        self._pedir_reset()
        solicitacao = PasswordResetRequest.objects.get(user=self.esquecido)
        url = f'/accounts/reset/aprovar/{solicitacao.token}/'

        navegador_desup = self.client_class()
        self.fazer_login(self.desup.email, self.senha, client=navegador_desup)
        navegador_desup.post(url)

        # O usuário troca a senha depois do reset; um replay do POST não pode desfazer isso.
        self.esquecido.set_password("DepoisDoReset@2026")
        self.esquecido.save()

        replay = navegador_desup.post(url)
        self.assertEqual(replay.status_code, 200)
        self.assertContains(replay, 'já foi processada')

        self.esquecido.refresh_from_db()
        self.assertTrue(self.esquecido.check_password("DepoisDoReset@2026"))

    def test_solicitacao_expirada_nao_pode_ser_aprovada(self):
        self._pedir_reset()
        solicitacao = PasswordResetRequest.objects.get(user=self.esquecido)
        PasswordResetRequest.objects.filter(pk=solicitacao.pk).update(
            criado_em=timezone.now() - timedelta(hours=24, minutes=1)
        )
        url = f'/accounts/reset/aprovar/{solicitacao.token}/'

        navegador_desup = self.client_class()
        self.fazer_login(self.desup.email, self.senha, client=navegador_desup)
        resposta = navegador_desup.post(url)

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'expirou')
        self.esquecido.refresh_from_db()
        self.assertFalse(self.esquecido.check_password(DEFAULT_USER_PASSWORD))
        self.assertFalse(PasswordResetRequest.objects.get(pk=solicitacao.pk).finalizado)

    def test_email_desconhecido_nao_cria_solicitacao_nem_notificacao(self):
        resposta = self._pedir_reset(email='ninguem_aqui@teste.com')

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Não foi encontrado nenhum usuário com o e-mail informado.')
        self.assertEqual(PasswordResetRequest.objects.count(), 0)
        self.assertEqual(Notificacao.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    # ── Regressão do escalonamento por unidade nula (CORRIGIDO em SEC-002) ──
    def test_coordenador_sem_unidade_nao_deveria_aprovar_reset_de_superusuario(self):
        """
        # CORRIGIDO (SEC-002, 2026-08-01) — este teste virou regressão.
        #
        # Era: escalonamento de privilégio via unidade nula.
        #
        # `ApprovePasswordResetView` (apps/accounts/views.py:489 no GET e :501 no
        # POST) autoriza o coordenador comparando `reset_req.user.unidade !=
        # request.user.unidade`. Quando as DUAS unidades são `None` a comparação
        # dá False e a checagem passa — ou seja, um COORDENADOR_UNIDADE sem
        # unidade vinculada pode aprovar o reset de QUALQUER conta sem unidade,
        # inclusive superusuários, DESUP e ADMIN (TI).
        #
        # O impacto é total: a senha do alvo vira `DEFAULT_USER_PASSWORD`
        # ("Faetec@123"), valor que o próprio template de aprovação exibe na tela
        # (templates/registration/approve_reset.html), então quem aprovou já sai
        # sabendo a senha e entra na conta do superusuário.
        #
        # Reproduzir:
        #   1. Crie um COORDENADOR_UNIDADE com `unidade=None` (é o default do
        #      modelo — acontece em toda conta criada sem vincular a unidade).
        #   2. POST em /accounts/forgot-password/ com o e-mail do superusuário
        #      (endpoint público, não exige sessão).
        #   3. Logue como o coordenador sem unidade e faça POST em
        #      /accounts/reset/aprovar/<token>/.
        #   4. A senha do superusuário passa a ser "Faetec@123".
        #
        # Correção aplicada: `_pode_aprovar_reset()` exige unidade não nula nos
        # dois lados, compara por id e recusa que coordenador aprove conta
        # administrativa. Ver `CadeiaTakeoverResetSenhaTests` em tests.py.
        """
        superusuario = User.objects.create_superuser(
            email="super_alvo_e2e@teste.com",
            password="SuperSegura@2026",
        )
        coord_sem_unidade = User.objects.create_user(
            email="coord_sem_unidade_e2e@teste.com",
            password=self.senha,
            perfil=User.Perfil.COORDENADOR_UNIDADE,
            forcar_troca_senha=False,
        )
        self.assertIsNone(coord_sem_unidade.unidade)
        self.assertIsNone(superusuario.unidade)

        self._pedir_reset(email=superusuario.email)
        solicitacao = PasswordResetRequest.objects.get(user=superusuario)
        url = f'/accounts/reset/aprovar/{solicitacao.token}/'

        navegador = self.client_class()
        self.fazer_login(coord_sem_unidade.email, self.senha, client=navegador)
        resposta = navegador.post(url)

        # Esperado: barrado como qualquer aprovação fora do escopo do coordenador.
        superusuario.refresh_from_db()
        self.assertFalse(superusuario.check_password(DEFAULT_USER_PASSWORD))
        self.assertEqual(resposta.status_code, 403)

    def test_esqueci_senha_deveria_limitar_pedidos_repetidos(self):
        """
        # CORRIGIDO (SEC-004): `ForgotPasswordView` (apps/accounts/views.py:411) é
        # pública, não exige sessão e NÃO tem rate-limit nenhum. Cada POST cria
        # um `PasswordResetRequest`, uma `Notificacao` por destinatário e dispara
        # um e-mail para toda a DESUP + superusuários + coordenação da unidade.
        #
        # É exatamente o problema que o CORR-020 corrigiu no fluxo autenticado de
        # troca de senha (1 link por dia, apps/accounts/views.py:217-252) e que
        # ficou sem tratamento aqui, no endpoint mais exposto dos dois.
        #
        # Reproduzir (sem nenhuma credencial):
        #   for _ in range(20):
        #       POST /accounts/forgot-password/ {'email': '<qualquer e-mail válido>'}
        #   -> 20 solicitações no banco, 20 e-mails para a DESUP e 20 notificações
        #      por destinatário. Repetindo em laço, vira e-mail bombing + inflação
        #      da tabela de notificações (a caixa de entrada do DESUP fica inútil,
        #      e no meio do ruído a aprovação legítima passa despercebida).
        #
        # Correção sugerida: reaproveitar a ideia do CORR-020 — cooldown por
        # usuário/IP antes de criar a solicitação e enviar o e-mail.
        """
        for _ in range(6):
            self._pedir_reset()

        # Esperado: pedidos repetidos em sequência não podem gerar N solicitações
        # nem N e-mails para a coordenação.
        self.assertEqual(PasswordResetRequest.objects.filter(user=self.esquecido).count(), 1)
        self.assertEqual(len(mail.outbox), 1)


# ══════════════════════════════════════════════════════════════════════════════
# Cenário 7 — Roteamento pós-login por perfil (os três perfis, com e sem HTMX)
# ══════════════════════════════════════════════════════════════════════════════
class RoteamentoPosLoginE2ETests(BaseE2ETestCase):
    """Cada perfil aterrissa na sua própria tela inicial, inclusive via HTMX."""

    def setUp(self):
        super().setUp()
        self.senha = "Rota@2026"
        self.unidade = Unidade.objects.create(nome="Unidade E2E Rota", sigla="URT")
        self.admin = User.objects.create_user(
            email="admin_rota_e2e@teste.com", password=self.senha,
            perfil=User.Perfil.ADMIN, forcar_troca_senha=False,
        )
        self.desup = User.objects.create_user(
            email="desup_rota_e2e@teste.com", password=self.senha,
            perfil=User.Perfil.DESUP, forcar_troca_senha=False,
        )
        self.coordenador = User.objects.create_user(
            email="coord_rota_e2e@teste.com", password=self.senha,
            perfil=User.Perfil.COORDENADOR_UNIDADE, unidade=self.unidade,
            forcar_troca_senha=False,
        )
        self.rotas = {
            'ADMIN': (self.admin, URL_ADMIN),
            'DESUP': (self.desup, URL_DASH_DESUP),
            'COORDENADOR_UNIDADE': (self.coordenador, URL_DASH_UNIDADE),
        }

    def test_cada_perfil_cai_na_sua_tela_inicial(self):
        for perfil, (usuario, destino) in self.rotas.items():
            with self.subTest(perfil=perfil):
                navegador = self.client_class()
                resposta = self.fazer_login(usuario.email, self.senha, client=navegador)

                self.assertEqual(resposta.status_code, 302)
                self.assertEqual(resposta['Location'], destino)

                # E a tela de destino realmente abre para esse perfil.
                self.assertEqual(navegador.get(destino).status_code, 200)

    def test_cada_perfil_cai_na_sua_tela_inicial_via_htmx(self):
        for perfil, (usuario, destino) in self.rotas.items():
            with self.subTest(perfil=perfil):
                navegador = self.client_class()
                resposta = self.fazer_login(
                    usuario.email, self.senha, client=navegador, HTTP_HX_REQUEST='true'
                )

                self.assertEqual(resposta.status_code, 200)
                self.assertEqual(resposta['HX-Redirect'], destino)
                # O htmx só olha o header: o corpo tem que vir vazio.
                self.assertEqual(resposta.content, b'')
                self.assertTrue(self.esta_autenticado(navegador))

    def test_raiz_do_site_leva_cada_perfil_para_o_seu_dashboard(self):
        """'/' redireciona para 'dashboard', que reroteia conforme o perfil."""
        for perfil, (usuario, destino) in self.rotas.items():
            with self.subTest(perfil=perfil):
                navegador = self.client_class()
                self.fazer_login(usuario.email, self.senha, client=navegador)

                resposta = navegador.get('/', follow=True)

                self.assertEqual(resposta.status_code, 200)
                self.assertEqual(resposta.redirect_chain[-1][0], destino)


# ══════════════════════════════════════════════════════════════════════════════
# Cenário 8 — Isolamento entre perfis
# ══════════════════════════════════════════════════════════════════════════════
class IsolamentoEntrePerfisE2ETests(BaseE2ETestCase):
    """Cada perfil enxerga apenas o seu território; o ADMIN é desviado ao /admin/."""

    def setUp(self):
        super().setUp()
        self.senha = "Isola@2026"
        self.unidade = Unidade.objects.create(nome="Unidade E2E Isolamento", sigla="UIS")
        self.admin = User.objects.create_user(
            email="admin_iso_e2e@teste.com", password=self.senha,
            perfil=User.Perfil.ADMIN, forcar_troca_senha=False,
        )
        self.desup = User.objects.create_user(
            email="desup_iso_e2e@teste.com", password=self.senha,
            perfil=User.Perfil.DESUP, forcar_troca_senha=False,
        )
        self.coordenador = User.objects.create_user(
            email="coord_iso_e2e@teste.com", password=self.senha,
            perfil=User.Perfil.COORDENADOR_UNIDADE, unidade=self.unidade,
            forcar_troca_senha=False,
        )

    def test_coordenador_de_unidade_recebe_403_nas_telas_da_desup(self):
        """Nas telas gateadas só pelo `PerfilRequiredMixin` a recusa é 403 seco."""
        navegador = self.client_class()
        self.fazer_login(self.coordenador.email, self.senha, client=navegador)

        for url in (URL_DASH_DESUP, '/core/unidades/', '/core/unidades/add/'):
            with self.subTest(url=url):
                self.assertEqual(navegador.get(url).status_code, 403)

    def test_coordenador_e_desviado_da_area_de_janelas_de_entrega(self):
        """
        `/core/entregas/` não usa o 403 do mixin: o `JanelaEntregaBaseView`
        (apps/core/views.py:407) intercepta antes e devolve o usuário ao
        dashboard com uma mensagem. O importante para o isolamento é que ele
        NÃO chegue à tela — aqui só registramos qual das duas formas é usada.
        """
        navegador = self.client_class()
        self.fazer_login(self.coordenador.email, self.senha, client=navegador)

        resposta = navegador.get('/core/entregas/')

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta['Location'], '/dashboard/')
        # E seguindo o desvio ele acaba no dashboard da própria unidade.
        self.assertEqual(
            navegador.get('/core/entregas/', follow=True).redirect_chain[-1][0],
            URL_DASH_UNIDADE,
        )

    def test_coordenador_recebe_403_amigavel_em_requisicao_htmx(self):
        navegador = self.client_class()
        self.fazer_login(self.coordenador.email, self.senha, client=navegador)

        resposta = navegador.get(URL_DASH_DESUP, HTTP_HX_REQUEST='true')

        self.assertEqual(resposta.status_code, 403)
        self.assertIn('Acesso negado', resposta.content.decode())

    def test_desup_nao_entra_na_tela_exclusiva_de_unidade(self):
        navegador = self.client_class()
        self.fazer_login(self.desup.email, self.senha, client=navegador)

        self.assertEqual(navegador.get(URL_DASH_DESUP).status_code, 200)
        self.assertEqual(navegador.get(URL_DASH_UNIDADE).status_code, 403)

    def test_admin_e_desviado_para_o_admin_do_django_nas_telas_operacionais(self):
        navegador = self.client_class()
        self.fazer_login(self.admin.email, self.senha, client=navegador)

        for url in (URL_DASH_DESUP, URL_DASH_UNIDADE, '/core/unidades/', '/alocacao-curricular/'):
            with self.subTest(url=url):
                resposta = navegador.get(url)
                self.assertEqual(resposta.status_code, 302)
                self.assertEqual(resposta['Location'], URL_ADMIN)

        # Em HTMX o desvio vira 204 + header, para o htmx trocar a página.
        htmx = navegador.get(URL_DASH_UNIDADE, HTTP_HX_REQUEST='true')
        self.assertEqual(htmx.status_code, 204)
        self.assertEqual(htmx['HX-Redirect'], URL_ADMIN)

    def test_visitante_anonimo_nao_alcanca_nenhuma_tela_interna(self):
        anonimo = self.client_class()

        for url in (URL_DASH_DESUP, URL_DASH_UNIDADE, URL_PERFIL, '/core/unidades/'):
            with self.subTest(url=url):
                self.assertMandaParaLogin(anonimo.get(url))


# ══════════════════════════════════════════════════════════════════════════════
# Cenário 9 — Página "Meu Perfil" nos três perfis
# ══════════════════════════════════════════════════════════════════════════════
class MeuPerfilE2ETests(BaseE2ETestCase):
    """O que cada perfil enxerga na tela somente-leitura de perfil (CORR-017)."""

    def setUp(self):
        super().setUp()
        self.senha = "Perfil@2026"
        self.unidade = Unidade.objects.create(nome="Unidade E2E Perfil", sigla="UPF")
        self.admin = User.objects.create_user(
            email="admin_perfil_e2e@teste.com", password=self.senha,
            perfil=User.Perfil.ADMIN, forcar_troca_senha=False,
        )
        self.desup = User.objects.create_user(
            email="desup_perfil_e2e@teste.com", password=self.senha,
            perfil=User.Perfil.DESUP, forcar_troca_senha=False,
        )
        self.coordenador = User.objects.create_user(
            email="coord_perfil_e2e@teste.com", password=self.senha,
            perfil=User.Perfil.COORDENADOR_UNIDADE, unidade=self.unidade,
            forcar_troca_senha=False,
        )

    def test_cada_perfil_ve_o_seu_rotulo_e_so_a_unidade_faz_diferenca(self):
        casos = [
            (self.admin, 'Administrador (TI DESUP)', False),
            (self.desup, 'Coordenador DESUP', False),
            (self.coordenador, 'Coordenador de Unidade', True),
        ]

        for usuario, rotulo, mostra_unidade in casos:
            with self.subTest(perfil=usuario.perfil):
                navegador = self.client_class()
                self.fazer_login(usuario.email, self.senha, client=navegador)

                resposta = navegador.get(URL_PERFIL)

                self.assertEqual(resposta.status_code, 200)
                self.assertTemplateUsed(resposta, 'accounts/profile.html')
                self.assertContains(resposta, usuario.email)
                self.assertContains(resposta, rotulo)
                # O bloco de unidade só existe para o coordenador de unidade.
                if mostra_unidade:
                    self.assertContains(resposta, self.unidade.sigla)
                    self.assertContains(resposta, self.unidade.nome)
                else:
                    self.assertNotContains(resposta, 'Unidade</dt>')
                # Somente leitura: a única ação oferecida é ir para a troca de senha.
                self.assertContains(resposta, f'href="{URL_TROCA_SENHA}"')
                self.assertNotContains(resposta, '<input type="text"')

    def test_do_perfil_o_usuario_chega_a_troca_de_senha(self):
        """O botão "Alterar senha" precisa levar a uma tela funcional."""
        navegador = self.client_class()
        self.fazer_login(self.desup.email, self.senha, client=navegador)

        perfil = navegador.get(URL_PERFIL)
        self.assertContains(perfil, 'Alterar senha')

        destino = navegador.get(URL_TROCA_SENHA)
        self.assertEqual(destino.status_code, 200)
        self.assertContains(destino, self.desup.email)

    def test_perfil_exige_sessao(self):
        self.assertMandaParaLogin(self.client_class().get(URL_PERFIL))


# ══════════════════════════════════════════════════════════════════════════════
# Cenário 10 — Logout
# ══════════════════════════════════════════════════════════════════════════════
class LogoutE2ETests(BaseE2ETestCase):
    """Sair do sistema tem que encerrar a sessão de verdade, não só redirecionar."""

    def setUp(self):
        super().setUp()
        self.senha = "Saida@2026"
        self.usuario = User.objects.create_user(
            email="saida_e2e@teste.com", password=self.senha,
            perfil=User.Perfil.DESUP, forcar_troca_senha=False,
        )

    def test_jornada_de_saida_encerra_a_sessao(self):
        self.fazer_login(self.usuario.email, self.senha)
        self.assertEqual(self.client.get(URL_DASH_DESUP).status_code, 200)

        saida = self.client.post(URL_LOGOUT)

        self.assertEqual(saida.status_code, 302)
        self.assertFalse(self.esta_autenticado())
        # A tela protegida volta a exigir login.
        self.assertMandaParaLogin(self.client.get(URL_DASH_DESUP))
        self.assertMandaParaLogin(self.client.get(URL_PERFIL))

    def test_logout_por_get_nao_encerra_a_sessao(self):
        """Proteção contra logout via link/prefetch: só POST derruba a sessão."""
        self.fazer_login(self.usuario.email, self.senha)

        resposta = self.client.get(URL_LOGOUT)

        self.assertEqual(resposta.status_code, 405)
        self.assertTrue(self.esta_autenticado())
        self.assertEqual(self.client.get(URL_DASH_DESUP).status_code, 200)

    def test_apos_sair_e_possivel_entrar_de_novo(self):
        self.fazer_login(self.usuario.email, self.senha)
        self.client.post(URL_LOGOUT)

        reentrada = self.fazer_login(self.usuario.email, self.senha)

        self.assertEqual(reentrada.status_code, 302)
        self.assertEqual(reentrada['Location'], URL_DASH_DESUP)
        self.assertEqual(self.client.get(URL_DASH_DESUP).status_code, 200)
