import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import './App.css';

const GamePlayer = () => {
  const { gameName } = useParams();
  const gameUrl = `http://localhost:3001/games/${gameName}/index.html`;

  const [scale, setScale] = useState(1);

  // Native resolution of the game (e.g., Unikong is 810x700)
  const baseWidth = 810;
  const baseHeight = 700;

  useEffect(() => {
    const updateScale = () => {
      // Use a 0.995 multiplier to provide a tiny safety buffer against sub-pixel rounding scrollbars
      const scaleX = (window.innerWidth * 0.995) / baseWidth;
      const scaleY = (window.innerHeight * 0.995) / baseHeight;
      
      // Use Math.min to fit the game to the screen while preserving aspect ratio (letterboxing)
      setScale(Math.min(scaleX, scaleY));
    };

    // Ensure the body doesn't have default margins or scrollbars that interfere with the layout
    document.body.style.margin = '0';
    document.body.style.overflow = 'hidden';

    window.addEventListener('resize', updateScale);
    updateScale();

    return () => {
      window.removeEventListener('resize', updateScale);
      document.body.style.margin = '';
      document.body.style.overflow = '';
    };
  }, []);

  return (
    <div style={{
      width: '100vw',
      height: '100vh',
      backgroundColor: '#000',
      margin: 0,
      padding: 0,
      overflow: 'hidden',
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      position: 'fixed',
      inset: 0, // Shorthand for top/right/bottom/left: 0
      zIndex: 9999
    }}>
      <iframe
        src={gameUrl}
        title={gameName}
        scrolling="no"
        style={{
          width: `${baseWidth}px`,
          height: `${baseHeight}px`,
          border: 'none',
          display: 'block',
          transform: `scale(${scale})`,
          transformOrigin: 'center',
          flexShrink: 0
        }}
        allowFullScreen
      />
    </div>
  );
};

export default GamePlayer;
