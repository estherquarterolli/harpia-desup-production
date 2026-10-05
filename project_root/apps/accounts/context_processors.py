def superadmin_visualization(request):
    """Informa aos templates quando o superadmin está vendo um perfil operacional."""
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {}

    if not getattr(user, '_harpia_superadmin_original', False):
        return {'is_real_superadmin': bool(user.is_superuser)}

    modo = getattr(user, '_harpia_visualization_mode', '')
    unidade = getattr(user, '_harpia_visualization_unit', None)
    return {
        'is_real_superadmin': True,
        'superadmin_visualizando': True,
        'superadmin_modo': modo,
        'superadmin_modo_label': (
            f'Unidade · {unidade.sigla}' if unidade else 'DESUP'
        ),
        'superadmin_unidade_visualizada': unidade,
    }
