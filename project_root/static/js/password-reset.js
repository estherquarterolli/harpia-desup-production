document.querySelectorAll('.password-toggle').forEach(function(button) {
    const input = document.getElementById(button.getAttribute('aria-controls'));
    if (!input) return;

    button.addEventListener('click', function() {
        const showPassword = input.type === 'password';
        input.type = showPassword ? 'text' : 'password';
        button.setAttribute('aria-label', showPassword ? 'Ocultar senha' : 'Mostrar senha');
        button.setAttribute('aria-pressed', String(showPassword));
        button.querySelector('.password-visibility-slash').style.display = showPassword ? '' : 'none';
    });
});
