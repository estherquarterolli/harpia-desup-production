import os
import sys
from pathlib import Path
import django

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")
django.setup()

from apps.core.models import Unidade
from apps.professors.models import Professor
from apps.extra_curricular.models import PendenciaExtra, OrientacaoTCC, AtividadeExtensionista, ReducaoCargaHoraria, ParecerChoices
from apps.accounts.models import User

def run():
    print("Iniciando seed de alocações extracurriculares para FAETERJ Paracambi...")

    # 1. Buscar unidade e criador (coordenador ou administrador)
    unidade = Unidade.objects.get(nome="FAETERJ Paracambi")
    criador = User.objects.filter(unidade=unidade, perfil="COORDENADOR_UNIDADE").first()
    if not criador:
        criador = User.objects.filter(perfil="DESUP").first()

    # Limpar dados antigos para ter um estado limpo para testes
    PendenciaExtra.objects.filter(unidade=unidade, semestre="2026.1").delete()
    print("Dados antigos de 2026.1 deletados.")

    # 2. Buscar professores específicos
    prof_adilson = Professor.objects.filter(unidade_principal=unidade, rh_nome__icontains="ADILSON RICARDO").first()
    prof_alessandro = Professor.objects.filter(unidade_principal=unidade, rh_nome__icontains="ALESSANDRO").first()
    prof_andre = Professor.objects.filter(unidade_principal=unidade, rh_nome__icontains="ANDRE LUIS").first()
    prof_artur = Professor.objects.filter(unidade_principal=unidade, rh_nome__icontains="ARTUR SERGIO").first()

    # --- CASO 1: ADILSON (Rascunho) ---
    if prof_adilson:
        pe_adilson = PendenciaExtra.objects.create(
            professor=prof_adilson,
            unidade=unidade,
            semestre="2026.1",
            sei_numero="SEI-123456/123456/2026",
            status=PendenciaExtra.StatusChoices.RASCUNHO,
            criado_por=criador
        )
        # TCC
        OrientacaoTCC.objects.create(
            pendencia=pe_adilson,
            num_orientandos=4,
            parecer_desup=ParecerChoices.PENDENTE
        )
        # Extensão
        AtividadeExtensionista.objects.create(
            pendencia=pe_adilson,
            num_estudantes=10,
            parecer_desup=ParecerChoices.PENDENTE
        )
        print(f"Criado Rascunho para {prof_adilson.rh_nome}")

    # --- CASO 2: ALESSANDRO (Enviado para DESUP) ---
    if prof_alessandro:
        pe_alessandro = PendenciaExtra.objects.create(
            professor=prof_alessandro,
            unidade=unidade,
            semestre="2026.1",
            sei_numero="SEI-654321/654321/2026",
            status=PendenciaExtra.StatusChoices.ENVIADO,
            criado_por=criador
        )
        # TCC
        OrientacaoTCC.objects.create(
            pendencia=pe_alessandro,
            num_orientandos=6,
            parecer_desup=ParecerChoices.PENDENTE
        )
        # Redução
        ReducaoCargaHoraria.objects.create(
            pendencia=pe_alessandro,
            motivo_reducao="Redução de carga horária para Coordenador Adjunto de ADS conforme Resolução Interna.",
            horas_reduzidas=4.0,
            parecer_desup=ParecerChoices.PENDENTE
        )
        print(f"Criada Pendência Enviada para {prof_alessandro.rh_nome}")

    # --- CASO 3: ANDRE (Finalizado / Aprovado) ---
    if prof_andre:
        pe_andre = PendenciaExtra.objects.create(
            professor=prof_andre,
            unidade=unidade,
            semestre="2026.1",
            sei_numero="SEI-111111/111111/2026",
            status=PendenciaExtra.StatusChoices.APROVADO,
            criado_por=criador
        )
        # TCC
        OrientacaoTCC.objects.create(
            pendencia=pe_andre,
            num_orientandos=8,
            parecer_desup=ParecerChoices.APROVADO,
            motivo_parecer="Documentação de orientação anexada corretamente e homologada."
        )
        # Redução
        ReducaoCargaHoraria.objects.create(
            pendencia=pe_andre,
            motivo_reducao="Redução de carga horária de 8h autorizada para Direção Adjunta de Unidade.",
            horas_reduzidas=8.0,
            parecer_desup=ParecerChoices.APROVADO,
            motivo_parecer="Designação oficial anexada e conferida."
        )
        print(f"Criada Pendência Finalizada/Aprovada para {prof_andre.rh_nome}")

    # --- CASO 4: ARTUR (Rejeitado) ---
    if prof_artur:
        pe_artur = PendenciaExtra.objects.create(
            professor=prof_artur,
            unidade=unidade,
            semestre="2026.1",
            sei_numero="SEI-222222/222222/2026",
            status=PendenciaExtra.StatusChoices.REJEITADO,
            motivo_status_desup="Justificativas rejeitadas devido à falta de comprovação legal.",
            criado_por=criador
        )
        # TCC
        OrientacaoTCC.objects.create(
            pendencia=pe_artur,
            num_orientandos=2,
            parecer_desup=ParecerChoices.REJEITADO,
            motivo_parecer="O docente não informou os nomes dos alunos nem apresentou os planos de orientação."
        )
        # Redução
        ReducaoCargaHoraria.objects.create(
            pendencia=pe_artur,
            motivo_reducao="Redução solicitada para projeto de pesquisa científica.",
            horas_reduzidas=6.0,
            parecer_desup=ParecerChoices.REJEITADO,
            motivo_parecer="Não há portaria ou aprovação do projeto anexada no processo SEI."
        )
        print(f"Criada Pendência Rejeitada para {prof_artur.rh_nome}")

    print("Seed de alocações extracurriculares concluído com sucesso!")

if __name__ == "__main__":
    run()
