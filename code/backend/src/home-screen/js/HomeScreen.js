// Read game data from the injected script block
const gameDataElement = document.getElementById('game-data');
let arcadeGames = [];

try {
    // In the build script, we replace {{GAMES_JSON}} with the actual JSON
    // If running with the placeholder, use an empty array
    const rawData = gameDataElement.textContent.trim();
    if (rawData && rawData !== '{{GAMES_JSON}}') {
        arcadeGames = JSON.parse(rawData);
    }
} catch (e) {
    console.error("Failed to parse game data", e);
}

function showHomeScreen() {
    const homeScreenMenu = document.querySelector('.menu');
    const homeScreenTitle = document.getElementById("projectTitle");

    homeScreenMenu.innerHTML = ''; // Clear menu

    if (arcadeGames.length === 0) {
        homeScreenMenu.innerHTML = '<div class="game-option">No games found</div>';
        return;
    }

    arcadeGames.forEach((game, index) => {
        const gameOption = document.createElement('div');
        gameOption.className = 'game-option';
        
        const link = document.createElement('a');
        // Point to the wrapper or fallback to raw index
        link.href = game.wrapper_url || `games/${game.id}/${game.index_rel}`;
        link.textContent = game.name;
        
        gameOption.appendChild(link);
        homeScreenMenu.appendChild(gameOption);
    });

    let selectedIndex = 0;
    const gameOptions = document.querySelectorAll('.game-option');
    
    function updateSelection() {
        gameOptions.forEach((opt, idx) => {
            if (idx === selectedIndex) {
                opt.classList.add('selected');
            } else {
                opt.classList.remove('selected');
            }
        });
    }

    updateSelection();

    document.addEventListener('keydown', (event) => {
        if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
            selectedIndex = (selectedIndex + 1) % gameOptions.length;
            updateSelection();
        } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
            selectedIndex = (selectedIndex - 1 + gameOptions.length) % gameOptions.length;
            updateSelection();
        } else if (event.key === 'Enter') {
            const link = gameOptions[selectedIndex].querySelector('a');
            if (link) window.location.href = link.href;
        }
    });
}

// Initialize on load
window.addEventListener('DOMContentLoaded', showHomeScreen);