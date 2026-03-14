import React, { useState, useEffect } from 'react';
import { Routes, Route, Link } from 'react-router-dom';
import axios from 'axios';
import GamePlayer from './GamePlayer';
import GameEditor from './GameEditor';

const API_URL = 'http://localhost:3001/api';

function GameLobby() {
  const [games, setGames] = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);

  useEffect(() => {
    fetchGames();
  }, []);

  const fetchGames = async () => {
    try {
      const response = await axios.get(`${API_URL}/games`);
      setGames(response.data);
    } catch (error) {
      console.error('Error fetching games:', error);
    }
  };

  const handleFileChange = (event) => {
    setSelectedFile(event.target.files[0]);
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      alert('Please select a file to upload.');
      return;
    }

    const formData = new FormData();
    formData.append('game', selectedFile);

    try {
      await axios.post(`${API_URL}/upload`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      fetchGames();
    } catch (error) {
      console.error('Error uploading game:', error);
    }
  };

  const handleDeleteGame = async (gameName) => {
    if (window.confirm('Are you sure you want to delete this game?')) {
      try {
        await axios.delete(`${API_URL}/games/${gameName}`);
        fetchGames();
      } catch (error) {
        console.error('Error deleting game:', error);
      }
    }
  };

  return (
    <div>
      <h1>Game Lobby</h1>
      <div>
        <input type="file" onChange={handleFileChange} />
        <button onClick={handleUpload}>Upload Game</button>
      </div>
      <h2>Available Games:</h2>
      <ul>
        {games.map((game) => (
          <li key={game}>
            <Link to={`/play/${game}`}>{game}</Link> -{' '}
            <Link to={`/edit/${game}`}>Edit</Link> -{' '}
            <button onClick={() => handleDeleteGame(game)}>Delete</button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function App() {
  return (
    <Routes>
      <Route path="/" element={<GameLobby />} />
      <Route path="/play/:gameName" element={<GamePlayer />} />
      <Route path="/edit/:gameName" element={<GameEditor />} />
    </Routes>
  );
}

export default App;
