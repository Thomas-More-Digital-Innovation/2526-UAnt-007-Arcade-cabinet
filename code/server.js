const express = require('express');
const cors = require('cors');
const fs = require('fs/promises');
const path = require('path');
const multer = require('multer');
const AdmZip = require('adm-zip');
const fse = require('fs-extra');

const app = express();
const port = 3001;

const upload = multer({ dest: 'uploads/' });

app.use(cors());
app.use(express.json());

// Serve the games
app.use('/games', express.static(path.join(__dirname, 'games')));

// Endpoint to get the list of games
app.get('/api/games', async (req, res) => {
  try {
    const gamesDir = path.join(__dirname, 'games');
    const files = await fs.readdir(gamesDir, { withFileTypes: true });
    const games = files
      .filter(dirent => dirent.isDirectory())
      .map(dirent => dirent.name);
    res.json(games);
  } catch (error) {
    console.error('Error reading games directory:', error);
    res.status(500).send('Error reading games directory');
  }
});

// Endpoint to delete a game
app.delete('/api/games/:gameName', async (req, res) => {
  const gameName = req.params.gameName;
  const gameDir = path.join(__dirname, 'games', gameName);
  try {
    await fse.remove(gameDir);
    res.status(200).send('Game deleted successfully');
  } catch (error) {
    console.error('Error deleting game:', error);
    res.status(500).send('Error deleting game');
  }
});

// Endpoint to upload a game
app.post('/api/upload', upload.single('game'), async (req, res) => {
    if (!req.file) {
        return res.status(400).send('No file uploaded.');
    }

    const zipFilePath = req.file.path;
    const gameName = path.basename(req.file.originalname, '.zip');
    const extractPath = path.join(__dirname, 'games', gameName);

    try {
        // Extract the zip file
        const zip = new AdmZip(zipFilePath);
        zip.extractAllTo(extractPath, /*overwrite*/ true);

        // Clean up the uploaded zip file
        await fs.unlink(zipFilePath);

        res.status(200).send({ message: 'Game uploaded successfully', gameName });
    } catch (error) {
        console.error('Error uploading game:', error);
        res.status(500).send('Error uploading game');
    }
});

// Endpoint to get the file tree for a game
app.get('/api/games/:gameName/files', async (req, res) => {
    const gameName = req.params.gameName;
    const gameDir = path.join(__dirname, 'games', gameName);

    try {
        const absoluteFiles = await getFileTree(gameDir);
        const relativeFiles = absoluteFiles.map(file => path.relative(gameDir, file));
        res.json(relativeFiles);
    } catch (error) {
        console.error('Error reading game file tree:', error);
        res.status(500).send('Error reading game file tree');
    }
});

// Endpoint to upload a single file to a game
app.post('/api/games/:gameName/files', upload.single('file'), async (req, res) => {
    if (!req.file) {
        return res.status(400).send('No file uploaded.');
    }
    const gameName = req.params.gameName;
    const tempPath = req.file.path;
    const targetPath = path.join(__dirname, 'games', gameName, req.file.originalname);

    try {
        await fse.ensureDir(path.dirname(targetPath));
        await fse.move(tempPath, targetPath, { overwrite: true });
        res.status(200).send({ message: 'File uploaded successfully' });
    } catch (error) {
        console.error('Error uploading file to game:', error);
        // Clean up temp file on error
        await fs.unlink(tempPath).catch(() => {});
        res.status(500).send('Error uploading file to game');
    }
});

// Endpoint to get the content of a file
app.get('/api/games/:gameName/files/*', async (req, res) => {
    const gameName = req.params.gameName;
    const filePath = req.params[0];
    const fullPath = path.join(__dirname, 'games', gameName, filePath);

    try {
        const content = await fs.readFile(fullPath, 'utf-8');
        res.send(content);
    } catch (error) {
        console.error('Error reading file content:', error);
        res.status(500).send('Error reading file content');
    }
});

// Endpoint to delete a file or folder
app.delete('/api/games/:gameName/files/*', async (req, res) => {
    const gameName = req.params.gameName;
    const filePath = req.params[0];
    const fullPath = path.join(__dirname, 'games', gameName, filePath);
    try {
        await fse.remove(fullPath);
        res.status(200).send('File or folder deleted successfully');
    } catch (error) {
        console.error('Error deleting file:', error);
        res.status(500).send('Error deleting file');
    }
});

// Endpoint to rename or move a file or folder
app.patch('/api/games/:gameName/files/*', async (req, res) => {
    const gameName = req.params.gameName;
    const oldPath = req.params[0];
    const { newPath } = req.body;
    const fullOldPath = path.join(__dirname, 'games', gameName, oldPath);
    const fullNewPath = path.join(__dirname, 'games', gameName, newPath);
    try {
        await fse.ensureDir(path.dirname(fullNewPath));
        await fse.move(fullOldPath, fullNewPath);
        res.status(200).send('File or folder renamed/moved successfully');
    } catch (error) {
        console.error('Error renaming file:', error);
        res.status(500).send('Error renaming file');
    }
});

// Endpoint to save the content of a file
app.put('/api/games/:gameName/files/*', express.text(), async (req, res) => {
    const gameName = req.params.gameName;
    const filePath = req.params[0];
    const fullPath = path.join(__dirname, 'games', gameName, filePath);
    const content = req.body;

    try {
        await fs.writeFile(fullPath, content, 'utf-8');
        res.status(200).send('File saved successfully');
    } catch (error) {
        console.error('Error saving file content:', error);
        res.status(500).send('Error saving file content');
    }
});

async function getFileTree(dir) {
    const dirents = await fs.readdir(dir, { withFileTypes: true });
    const files = await Promise.all(dirents.map((dirent) => {
        const res = path.resolve(dir, dirent.name);
        return dirent.isDirectory() ? getFileTree(res) : res;
    }));
    return Array.prototype.concat(...files);
}


app.listen(port, () => {
  console.log(`Server listening at http://localhost:${port}`);
});
