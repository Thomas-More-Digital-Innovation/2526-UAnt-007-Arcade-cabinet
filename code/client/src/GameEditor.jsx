import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import Editor from '@monaco-editor/react';
import axios from 'axios';
import './App.css';

const API_URL = 'http://localhost:3001/api';

const getLanguage = (filename) => {
    const ext = filename.split('.').pop().toLowerCase();
    const map = {
        'js': 'javascript',
        'jsx': 'javascript',
        'ts': 'typescript',
        'tsx': 'typescript',
        'html': 'html',
        'css': 'css',
        'json': 'json',
        'md': 'markdown',
        'txt': 'plaintext',
        'xml': 'xml',
        'yaml': 'yaml',
        'yml': 'yaml'
    };
    return map[ext] || 'plaintext';
};

const isBinaryFile = (filename) => {
    const binaryExtensions = [
        'png', 'jpg', 'jpeg', 'gif', 'bmp', 'ico',
        'mp3', 'wav', 'ogg', 'mp4', 'webm', 'zip', 'pdf', 'ttf', 'woff', 'woff2'
    ];
    const ext = filename.split('.').pop().toLowerCase();
    return binaryExtensions.includes(ext);
};

const isImageFile = (filename) => {
    const imageExtensions = ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'ico', 'svg'];
    const ext = filename.split('.').pop().toLowerCase();
    return imageExtensions.includes(ext);
};

const isAudioFile = (filename) => {
    const audioExtensions = ['mp3', 'wav', 'ogg', 'm4a', 'aac'];
    const ext = filename.split('.').pop().toLowerCase();
    return audioExtensions.includes(ext);
};

const buildFileTree = (files) => {
    const tree = {};
    files.forEach(file => {
        let currentLevel = tree;
        const parts = file.split('/');
        parts.forEach((part, i) => {
            if (!currentLevel[part]) {
                currentLevel[part] = {
                    name: part,
                    path: parts.slice(0, i + 1).join('/'),
                    children: {},
                    isFolder: i < parts.length - 1 // Any path segment before the final filename is a folder
                };
            }
            currentLevel = currentLevel[part].children;
        });
    });
    return tree;
};

const FileTree = ({ tree, onFileClick, onDeleteFile, onRenameFile, onMoveFile, expandedFolders, toggleFolder, depth = 0 }) => {
    const sortedNodes = Object.values(tree).sort((a, b) => {
        const aIsFolder = Object.keys(a.children).length > 0 || a.isFolder;
        const bIsFolder = Object.keys(b.children).length > 0 || b.isFolder;
        if (aIsFolder && !bIsFolder) return -1;
        if (!aIsFolder && bIsFolder) return 1;
        return a.name.localeCompare(b.name);
    });

    return (
        <ul style={{ listStyleType: 'none', paddingLeft: depth === 0 ? '0' : '20px', margin: 0 }}>
            {sortedNodes.map(node => {
                const isFolder = Object.keys(node.children).length > 0 || node.isFolder;
                const isExpanded = expandedFolders.has(node.path);

                return (
                    <li key={node.path} className="file-tree-node" style={{ display: 'block' }}>
                        <div className="file-tree-node-content" style={{ display: 'flex', alignItems: 'center' }}>
                            <span onClick={() => isFolder ? toggleFolder(node.path) : onFileClick(node.path)} className="file-name">
                                {isFolder ? (isExpanded ? '📂' : '📁') : '📄'} {node.name}
                            </span>
                            <div className="file-actions">
                                <button onClick={() => onRenameFile(node.path)} className="action-button" title="Rename">✏️</button>
                                <button onClick={() => onMoveFile(node.path)} className="action-button" title="Move">🚚</button>
                                <button onClick={() => onDeleteFile(node.path)} className="delete-button" title="Delete">🗑️</button>
                            </div>
                        </div>
                        {isFolder && isExpanded && (
                            <FileTree
                                tree={node.children}
                                onFileClick={onFileClick}
                                onDeleteFile={onDeleteFile}
                                onRenameFile={onRenameFile}
                                onMoveFile={onMoveFile}
                                expandedFolders={expandedFolders}
                                toggleFolder={toggleFolder}
                                depth={depth + 1}
                            />
                        )}
                    </li>
                );
            })}
        </ul>
    );
};

const getAllFolders = (tree, folders = []) => {
    Object.values(tree).forEach(node => {
        const isFolder = Object.keys(node.children).length > 0 || node.isFolder;
        if (isFolder) {
            folders.push(node.path);
            getAllFolders(node.children, folders);
        }
    });
    return folders;
};

const GameEditor = () => {
    const { gameName } = useParams();
    const [files, setFiles] = useState({});
    const [selectedFile, setSelectedFile] = useState(null);
    const [code, setCode] = useState('');
    const [language, setLanguage] = useState('javascript');
    const [isBinary, setIsBinary] = useState(false);
    const [isImage, setIsImage] = useState(false);
    const [isAudio, setIsAudio] = useState(false);
    const [selectedFileUpload, setSelectedFileUpload] = useState(null);
    const [expandedFolders, setExpandedFolders] = useState(new Set());
    const [isMoveModalOpen, setIsMoveModalOpen] = useState(false);
    const [movingPath, setMovingPath] = useState('');
    const [selectedDest, setSelectedDest] = useState('');

    useEffect(() => {
        fetchFiles();
    }, [gameName]);

    const fetchFiles = async () => {
        try {
            const response = await axios.get(`${API_URL}/games/${gameName}/files`);
            setFiles(buildFileTree(response.data));
        } catch (error) {
            console.error('Error fetching files:', error);
            setFiles({});
        }
    };

    const handleFileClick = async (file) => {
        const isImg = isImageFile(file);
        const isAud = isAudioFile(file);
        const isBin = isBinaryFile(file);

        if (isBin || isImg || isAud) {
            setIsBinary(true);
            setIsImage(isImg);
            setIsAudio(isAud);
            setSelectedFile(file);
            setCode('');
            return;
        }

        setIsBinary(false);
        setIsImage(false);
        setIsAudio(false);
        try {
            const response = await axios.get(`${API_URL}/games/${gameName}/files/${file}`);
            setCode(response.data);
            setSelectedFile(file);
            setLanguage(getLanguage(file));
        } catch (error) {
            console.error('Error fetching file content:', error);
        }
    };

    const handleSave = async () => {
        if (!selectedFile) {
            alert('No file selected');
            return;
        }
        try {
            await axios.put(`${API_URL}/games/${gameName}/files/${selectedFile}`, code, {
                headers: { 'Content-Type': 'text/plain' }
            });
            alert('File saved successfully');
        } catch (error) {
            console.error('Error saving file:', error);
        }
    };

    const handleDeleteFile = async (file) => {
        if (window.confirm(`Are you sure you want to delete ${file}?`)) {
            try {
                await axios.delete(`${API_URL}/games/${gameName}/files/${file}`);
                fetchFiles();
                if (selectedFile === file) {
                    setSelectedFile(null);
                    setCode('');
                }
            } catch (error) {
                console.error('Error deleting file:', error);
            }
        }
    };

    const handleRenameFile = async (oldPath) => {
        const newPath = prompt('Enter the new name or path for the file:', oldPath);
        if (newPath && newPath !== oldPath) {
            try {
                await axios.patch(`${API_URL}/games/${gameName}/files/${oldPath}`, { newPath });
                fetchFiles();
                if (selectedFile === oldPath) {
                    handleFileClick(newPath);
                }
            } catch (error) {
                console.error('Error renaming file:', error);
            }
        }
    };

    const handleMoveFile = async (oldPath, newParentFolder) => {
        const fileName = oldPath.split('/').pop();
        const newPath = newParentFolder ? `${newParentFolder}/${fileName}` : fileName;
        if (newPath === oldPath) return;
        try {
            await axios.patch(`${API_URL}/games/${gameName}/files/${oldPath}`, { newPath });
            fetchFiles();
            if (selectedFile === oldPath) {
                handleFileClick(newPath);
            }
        } catch (error) {
            console.error('Error moving file:', error);
        }
    };

    const handleMoveClick = async (oldPath) => {
        setMovingPath(oldPath);
        setSelectedDest('');
        setIsMoveModalOpen(true);
    };

    const handleFileUploadChange = (event) => {
        setSelectedFileUpload(event.target.files[0]);
    };

    const handleFileUpload = async () => {
        if (!selectedFileUpload) {
            alert('Please select a file to upload.');
            return;
        }

        const formData = new FormData();
        formData.append('file', selectedFileUpload);

        try {
            await axios.post(`${API_URL}/games/${gameName}/files`, formData, {
                headers: {
                    'Content-Type': 'multipart/form-data',
                },
            });
            alert('File uploaded successfully!');
            fetchFiles();
        } catch (error) {
            console.error('Error uploading file:', error);
            alert('Error uploading file.');
        }
    };

    const toggleFolder = (path) => {
        setExpandedFolders(prev => {
            const newSet = new Set(prev);
            if (newSet.has(path)) {
                newSet.delete(path);
            } else {
                newSet.add(path);
            }
            return newSet;
        });
    };

    const handlePlay = () => {
        window.open(`/play/${gameName}`, '_blank');
    };

    return (
        <div style={{ display: 'flex', height: '100vh' }}>
            {isMoveModalOpen && (
                <div style={{
                    position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
                    backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex',
                    alignItems: 'center', justifyContent: 'center', zIndex: 1000
                }}>
                    <div style={{
                        backgroundColor: 'white', padding: '20px', borderRadius: '8px',
                        minWidth: '300px', color: '#333'
                    }}>
                        <h4>Move to...</h4>
                        <p style={{ fontSize: '0.9em', color: '#666' }}>Moving: {movingPath}</p>
                        <select 
                            value={selectedDest} 
                            onChange={(e) => setSelectedDest(e.target.value)}
                            style={{ width: '100%', padding: '8px', margin: '15px 0' }}
                        >
                            <option value="">(Root Directory)</option>
                            {getAllFolders(files)
                                .filter(path => path !== movingPath && !path.startsWith(movingPath + '/'))
                                .map(path => (
                                    <option key={path} value={path}>{path}</option>
                                ))
                            }
                        </select>
                        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                            <button onClick={() => setIsMoveModalOpen(false)}>Cancel</button>
                            <button onClick={() => {
                                handleMoveFile(movingPath, selectedDest);
                                setIsMoveModalOpen(false);
                            }} className="save-button" style={{ margin: 0 }}>Move</button>
                        </div>
                    </div>
                </div>
            )}
            <div className="file-list-container">
                <h3 className="file-list-header">Files</h3>
                <div className="upload-container">
                    <input type="file" onChange={handleFileUploadChange} />
                    <button onClick={handleFileUpload}>Upload File</button>
                </div>
                <FileTree
                    tree={files}
                    onFileClick={handleFileClick}
                    onDeleteFile={handleDeleteFile}
                    onRenameFile={handleRenameFile}
                    onMoveFile={handleMoveClick}
                    expandedFolders={expandedFolders}
                    toggleFolder={toggleFolder}
                />
            </div>
            <div className="editor-panel">
                <div className="editor-controls" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <button onClick={handlePlay} className="save-button">Play Game</button>
                    <button onClick={handleSave} className="save-button" disabled={!selectedFile || isBinary}>Save</button>
                </div>
                <div className="editor-wrapper">
                    {!selectedFile ? (
                        <div style={{ padding: '20px', color: '#2f2b2b', textAlign: 'center' }}>
                            Select a file to start editing.
                        </div>
                    ) : isImage ? (
                        <div style={{ padding: '20px', textAlign: 'center', height: '100%', overflow: 'auto' }}>
                            <h4 style={{ color: '#2f2b2b' }}>Image Preview: {selectedFile}</h4>
                            <img 
                                src={`http://localhost:3001/games/${gameName}/${selectedFile}`} 
                                alt={selectedFile} 
                                style={{ maxWidth: '100%', maxHeight: '90%', objectFit: 'contain', border: '1px solid #ccc' }} 
                            />
                        </div>
                    ) : isAudio ? (
                        <div style={{ padding: '20px', textAlign: 'center' }}>
                            <h4 style={{ color: '#2f2b2b' }}>Audio Preview: {selectedFile}</h4>
                            <audio 
                                controls 
                                src={`http://localhost:3001/games/${gameName}/${selectedFile}`} 
                                style={{ width: '100%', marginTop: '20px' }}
                            >
                                Your browser does not support the audio element.
                            </audio>
                        </div>
                    ) : isBinary ? (
                        <div style={{ padding: '20px', color: '#2f2b2b', textAlign: 'center' }}>
                            <h4>Binary File Detected</h4>
                            <p>The file "{selectedFile}" cannot be edited in the browser.</p>
                        </div>
                    ) : (
                        <Editor
                            language={language}
                            value={code}
                            onChange={(value) => setCode(value)}
                        />
                    )}
                </div>
            </div>
        </div>
    );
};

export default GameEditor;
