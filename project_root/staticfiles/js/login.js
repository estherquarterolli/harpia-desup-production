function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) {
        return decodeURIComponent(parts.pop().split(";").shift());
    }
    return null;
}

function syncCsrfToken() {
    const token = getCookie("csrftoken");
    const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    if (token && input) {
        input.value = token;
    }
}

document.addEventListener("DOMContentLoaded", function() {
    syncCsrfToken();

    if (window.lucide) {
        lucide.createIcons();
    }

    const passwordInput = document.getElementById("password");
    const toggleButton = document.querySelector(".login-password-toggle");
    if (passwordInput && toggleButton) {
        toggleButton.addEventListener("click", function() {
            const isHidden = passwordInput.type === "password";
            passwordInput.type = isHidden ? "text" : "password";
            toggleButton.setAttribute("aria-label", isHidden ? "Ocultar senha" : "Mostrar senha");

            if (window.lucide) {
                toggleButton.innerHTML = `<i data-lucide="${isHidden ? "eye" : "eye-off"}" class="w-5 h-5"></i>`;
                lucide.createIcons();
            }
        });
    }
});

window.addEventListener("pageshow", syncCsrfToken);

document.body.addEventListener("htmx:configRequest", function(event) {
    syncCsrfToken();

    const token = getCookie("csrftoken");
    if (token) {
        event.detail.headers["X-CSRFToken"] = token;
    }
});
