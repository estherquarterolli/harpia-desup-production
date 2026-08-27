# Plano de Migração do Admin Django

## Objetivo
Substituir a abordagem atual de `overrides` de templates/CSS por uma solução sustentável (`django-unfold`) que permita customização real.

## Estratégia Escolhida: Opção A (django-unfold)
Modernizar o Admin Django atual mantendo as funcionalidades, mas substituindo a UI por uma baseada em Tailwind.

## Passos de Implementação

1. **Limpeza:**
   - Remover os arquivos de template customizados em `project_root/templates/admin/`.
   - Limpar o `admin_custom.css` (remover o que era *hack* para consertar o admin original).
   
2. **Instalação:**
   - Instalar `django-unfold`.
   - Atualizar `requirements.txt`.
   
3. **Configuração:**
   - Atualizar `settings.py` para incluir `unfold` nas `INSTALLED_APPS`.
   - Configurar o tema e customizações (`unfold.py` nas configurações).
   
4. **Verificação:**
   - Validar se CRUDs, filtros e login continuam funcionando.
   - Ajustar customizações finas via configuração do Unfold (CSS/JS).

## Decisão Necessária
Aprovação do plano para iniciar a limpeza e instalação.
