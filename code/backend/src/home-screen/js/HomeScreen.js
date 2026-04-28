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
    const descriptionOverlay = document.getElementById('descriptionOverlay');
    const overlayTitle = document.getElementById('overlayGameTitle');
    const overlayDescription = document.getElementById('overlayGameDescription');

    let isOverlayOpen = false;
    let selectedIndex = 0;

    homeScreenMenu.innerHTML = ''; // Clear menu

    if (arcadeGames.length === 0) {
        homeScreenMenu.innerHTML = '<div class="game-option">No games found</div>';
        return;
    }

    arcadeGames.forEach((game, index) => {
        const gameOption = document.createElement('div');
        gameOption.className = 'game-option';
        
        const link = document.createElement('a');
        link.href = game.wrapper_url || `games/${game.id}/${game.index_rel}`;
        link.textContent = game.name;
        // Don't navigate automatically on click if we want to show description
        link.addEventListener('click', (e) => {
            e.preventDefault();
            openDescription(index);
        });
        
        gameOption.appendChild(link);
        homeScreenMenu.appendChild(gameOption);
    });

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

    function openDescription(index) {
        const game = arcadeGames[index];
        overlayTitle.textContent = game.name;
        overlayDescription.textContent = game.description || "No description available for this game.";
        descriptionOverlay.classList.remove('hidden');
        isOverlayOpen = true;
    }

    function closeDescription() {
        descriptionOverlay.classList.add('hidden');
        isOverlayOpen = false;
    }

    function launchGame(index) {
        const game = arcadeGames[index];
        const url = game.wrapper_url || `games/${game.id}/${game.index_rel}`;
        window.location.href = url;
    }

    updateSelection();

    document.addEventListener('keydown', (event) => {
        if (isOverlayOpen) {
            if (event.key === 'Enter') {
                launchGame(selectedIndex);
            } else if (event.key === 'Escape' || event.key === 'Backspace' || event.key === 'ArrowLeft') {
                closeDescription();
            }
            return;
        }

        if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
            selectedIndex = (selectedIndex + 1) % gameOptions.length;
            updateSelection();
        } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
            selectedIndex = (selectedIndex - 1 + gameOptions.length) % gameOptions.length;
            updateSelection();
        } else if (event.key === 'Enter') {
            openDescription(selectedIndex);
        }
    });
}

// Initialize on load
window.addEventListener('DOMContentLoaded', showHomeScreen);