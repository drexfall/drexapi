const changeListeners = {
    '.df-block': ['data-title']
}

window.addEventListener("load", (event) => {
    const observer = new MutationObserver((mutations, observer) => {
        mutations.forEach((mutation) => {
            console.log(mutation);
        });
    })
    Object.entries(changeListeners).forEach(item => {

        document.querySelectorAll(item[0]).forEach(node => {

            observer.observe(node, {
                attributes: true, // this can be omitted
                attributeFilter: item[1]
            });
            switch (item[0]) {
                case '.df-block':
                    node.style.setProperty('--word-length', node.dataset.title.length)
            }
        })

    })
})