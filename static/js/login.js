// ===== PASSWORD VISIBILITY =====

const passwordInput = document.querySelector(
    'input[name="password"]'
);

const eyeButton = document.querySelector(
    ".eye-button"
);


eyeButton.addEventListener("click", function () {

    // ===== SHOW PASSWORD =====

    if (passwordInput.type === "password") {

        passwordInput.type = "text";

        eyeButton.innerHTML =
            '<i class="bi bi-eye-slash"></i>';

    }

    // ===== HIDE PASSWORD =====

    else {

        passwordInput.type = "password";

        eyeButton.innerHTML =
            '<i class="bi bi-eye"></i>';

    }

});