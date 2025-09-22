// Archivo: static/js/resguardos.js

async function loadMoreResguardos() {
    if (isLoading || allDataLoaded) return;

    isLoading = true;
    loadingIndicator.style.display = 'block';
    currentPage++;

    const searchParams = new URLSearchParams(window.location.search);
    searchParams.set('page', currentPage);
    
    const url = `${window.location.pathname}?${searchParams.toString()}`;

    try {
        // --- ESTE ES EL CAMBIO CLAVE ---
        // Añadimos el objeto 'headers' a la petición fetch.
        // Esta es la "seña secreta" que Python buscará.
        const response = await fetch(url, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const newRowsHtml = await response.text();

        if (newRowsHtml.trim() !== '') {
            tableBody.insertAdjacentHTML('beforeend', newRowsHtml);
        } else {
            allDataLoaded = true;
            noMoreDataIndicator.style.display = 'block';
        }
    } catch (error) {
        console.error("Error al cargar más resguardos:", error);
    } finally {
        isLoading = false;
        loadingIndicator.style.display = 'none';
    }
}

// Asegúrate de que el resto de tu archivo JS (event listeners, etc.) esté presente.
// Por ejemplo:
document.addEventListener('DOMContentLoaded', function() {
    // ... tu código existente para ordenar la tabla y el evento de scroll ...
    // El código del event listener del scroll debe llamar a la función loadMoreResguardos de arriba.
});