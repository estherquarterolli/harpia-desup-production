(function() {
    function atualizarCursos(form) {
        const grupo = form.querySelector('fieldset[data-abrangencia-cursos]');
        const checklist = form.querySelector('[data-cursos-especificos]');
        if (!grupo || !checklist) return;
        const selecionado = grupo.querySelector('input:checked');
        checklist.classList.toggle('hidden', !selecionado || selecionado.value !== 'ESPECIFICOS');
    }

    document.querySelectorAll('[data-ocupacao-form]').forEach(function(form) {
        atualizarCursos(form);
        form.addEventListener('change', function() { atualizarCursos(form); });
        form.addEventListener('submit', async function(event) {
            event.preventDefault();
            if (form.dataset.salvando) return;
            form.dataset.salvando = 'true';
            const campos = form.querySelector('[data-ocupacao-campos]');
            const botao = form.querySelector('button[type="submit"]');
            botao.disabled = true;
            try {
                const response = await fetch(form.action, {
                    method: 'POST',
                    body: new FormData(form),
                    headers: {'X-Requested-With': 'XMLHttpRequest'},
                });
                if (response.redirected) {
                    window.location.assign(response.url);
                    return;
                }
                if (!response.ok && response.status !== 422) throw new Error('Falha ao salvar');
                const resultado = await response.json();
                if (resultado.redirect_url) {
                    window.location.assign(resultado.redirect_url);
                } else {
                    campos.innerHTML = resultado.html;
                    atualizarCursos(form);
                    const erro = campos.querySelector('[role="alert"]');
                    if (erro) erro.scrollIntoView({block: 'nearest'});
                }
            } catch (error) {
                let aviso = form.querySelector('[data-erro-envio]');
                if (!aviso) {
                    aviso = document.createElement('p');
                    aviso.dataset.erroEnvio = 'true';
                    aviso.className = 'mb-3 text-sm font-semibold text-red-600';
                    aviso.setAttribute('role', 'alert');
                    campos.prepend(aviso);
                }
                aviso.textContent = 'Não foi possível confirmar o salvamento. Confira sua conexão e tente novamente.';
            } finally {
                delete form.dataset.salvando;
                botao.disabled = false;
            }
        });
    });
})();
