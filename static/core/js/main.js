let html = document.documentElement
html.updateSetting = (type, value) => {
    localStorage.setItem(type, value)
}
html.setTheme = (mode, source) => {
    switch (mode) {
        case "auto":
            let darkMode = window.matchMedia('(prefers-color-scheme: dark)')
            darkMode.addEventListener("change", (event) => {
                html.setTheme(event.matches ? "dark" : "light")
            })
            html.setTheme(darkMode ? "dark" : "light")
            //html.updateSetting("theme", mode)
            break
        case "light":
        case "dark":
            document.documentElement.dataset.bsTheme = mode
            //html.updateSetting("theme", mode)
            break
        default:
            html.setTheme("auto")
    }
}

function showAlert(method, message) {
    let alert = document.createElement("div")
    document.querySelector("#alertContainer").append(alert)
    alert.outerHTML = `
    <div class="alert alert-${method} alert-dismissible fade show m-4" role="alert">
         ${message}
          <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>`
}

window.addEventListener('load', (event => {

    let storedTheme = localStorage.getItem("theme")
    switch (storedTheme) {
        case null:
        case "auto":
            html.setTheme("auto", "load")
            break
        case "dark":
        case "light":
            html.setTheme(storedTheme, "load")
    }
    gsap.to(".df-loader", {
        'opacity': 0,
        y: "-2em",
        zIndex: -6,
        filter: "blur(3em)"
    })
}))

if (/Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent)) {
    gsap.fromTo("body", {
        '--radius': "20%",
        'repeat': -1,
        'yoyo': true,
        'yoyoEase': "circ.in",
        duration: 5
    }, {
        '--radius': "50%",
        'repeat': -1,
        'yoyo': true,
        'yoyoEase': "circ.out",
        duration: 5
    })
} else {
    window.addEventListener('mousemove', event => {
        document.body.style.setProperty("--grad-x", event.clientX + "px")
        document.body.style.setProperty("--grad-y", event.clientY + "px")
    })
}

document.querySelectorAll(".copy-input").forEach(e => {
    e.addEventListener("focus", async () => {
        let copyText = e.value;
        await navigator.clipboard.writeText(copyText);
        e.classList.add("is-valid")
    })
    e.addEventListener("blur", () => {
        e.classList.remove("is-valid")
    })
})