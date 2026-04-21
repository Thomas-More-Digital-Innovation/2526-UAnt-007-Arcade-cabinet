/**
 * GameWrapper.js
 * Mirrored from frontend/src/components/GameCard.vue
 */

const nativeW = 1280;
const nativeH = 720;
let currentNativeW = nativeW;
let currentNativeH = nativeH;

function computeScale() {
    const scaler = document.getElementById('game-scaler');
    const iframe = document.getElementById('game-iframe');
    
    if (!scaler || !iframe) return;

    const windowWidth = window.innerWidth;
    const windowHeight = window.innerHeight;

    // Independent scale factors (stretching to fill) as per frontend logic
    const scaleX = windowWidth / currentNativeW;
    const scaleY = windowHeight / currentNativeH;

    // Apply native sizing to base elements
    scaler.style.width = `${currentNativeW}px`;
    scaler.style.height = `${currentNativeH}px`;
    iframe.style.width = `${currentNativeW}px`;
    iframe.style.height = `${currentNativeH}px`;

    // Apply transform scaling
    scaler.style.transform = `scale(${scaleX}, ${scaleY})`;
    scaler.style.transformOrigin = 'top left';
}

function onIframeLoad() {
    const iframe = document.getElementById('game-iframe');
    if (!iframe) return;

    try {
        const doc = iframe.contentDocument || iframe.contentWindow.document;
        if (doc) {
            // 1. Force the game content to be truly full-screen within the iframe
            // This removes internal bars often present in fixed-size Phaser/HTML5 games.
            const style = doc.createElement('style');
            style.textContent = `
                html, body {
                    margin: 0 !important;
                    padding: 0 !important;
                    width: 100% !important;
                    height: 100% !important;
                    overflow: hidden !important;
                }
                canvas {
                    width: 100vw !important;
                    height: 100vh !important;
                    object-fit: fill !important;
                }
            `;
            doc.head.appendChild(style);

            // 2. Detect dimensions
            // We search for a canvas first as it's the most reliable "game size" indicator
            const canvas = doc.querySelector('canvas');
            if (canvas) {
                currentNativeW = canvas.width;
                currentNativeH = canvas.height;
            } else {
                const w = doc.documentElement.scrollWidth || doc.body?.scrollWidth;
                const h = doc.documentElement.scrollHeight || doc.body?.scrollHeight;
                if (w > 0) currentNativeW = w;
                if (h > 0) currentNativeH = h;
            }
        }
    } catch (e) {
        // Cross-origin fallback
        console.warn("Could not detect game size or inject styles automatically", e);
    }
    computeScale();
}

window.addEventListener('resize', computeScale);
window.addEventListener('load', () => {
    computeScale();
    
    const iframe = document.getElementById('game-iframe');
    if (iframe) {
        iframe.addEventListener('load', onIframeLoad);
        iframe.focus();
    }
    
    // Listen for keys for navigation
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' || e.key === 'q') {
            window.location.href = '../../index.html';
        }
    });
});
