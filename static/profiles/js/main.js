document.querySelector(".share-btn").addEventListener('click', e => {
    //document.querySelector("dialog").showModal()
    showAlert("success", "Profile URL copied successfully!")
})
window.addEventListener("load", event => {
    document.querySelectorAll("[data-title='Contact'] .copy-btn").forEach(button => {
        button.addEventListener('click', async e => {
            let copyText = button.dataset.copyText;
            await navigator.clipboard.writeText(copyText);
            showAlert("success", `Copied successfully!`)
        })
    })
})