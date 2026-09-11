document.addEventListener("DOMContentLoaded", function () {

    // Add small interaction to buttons

    const buttons = document.querySelectorAll(".primary-btn");

    buttons.forEach(function (button) {

        button.addEventListener("click", function () {

            button.style.transform = "scale(0.98)";

            setTimeout(function () {

                button.style.transform = "";

            }, 120);

        });

    });


    // Automatically hide alerts

    const alerts = document.querySelectorAll(".alert");

    alerts.forEach(function (alert) {

        setTimeout(function () {

            alert.style.opacity = "0";

            alert.style.transition = "opacity .5s";

            setTimeout(function () {

                alert.remove();

            }, 500);

        }, 3500);

    });

});