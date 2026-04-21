import os
import json
import shutil
import logging
from pathlib import Path
from dotenv import load_dotenv
import s3fs

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Load configuration from common locations
_current_dir = Path(__file__).resolve().parent
_env_locations = [
    _current_dir / ".env",
    _current_dir / "src" / ".env"
]
for _env_path in _env_locations:
    if _env_path.exists():
        logger.info(f"Loading environment from {_env_path}")
        load_dotenv(_env_path)
        break

S3_REMOTE_ROOT = os.getenv('UPLOADS_REMOTE_ROOT', '').rstrip('/')
S3_ENDPOINT = os.getenv('S3_ENDPOINT_URL', '')
S3_KEY = os.getenv('S3_ACCESS_KEY_ID', '')
S3_SECRET = os.getenv('S3_SECRET_ACCESS_KEY', '')
S3_TOKEN = os.getenv('S3_SESSION_TOKEN', '')

# Validation
if not S3_KEY or not S3_SECRET:
    logger.warning("S3 credentials (SECRET/KEY) not found in environment!")
S3_TOKEN = os.getenv('S3_SESSION_TOKEN', '')

class StaticBuildOrchestrator:
    def __init__(self, payload_path='workflow_payload.json', dist_dir='dist'):
        self.payload_path = payload_path
        self.dist_dir = Path(dist_dir)
        self.games_dir = self.dist_dir / 'games'
        
        if not os.path.exists(payload_path):
            logger.error(f"Payload file not found at {payload_path}")
            exit(1)
            
        with open(payload_path, 'r') as f:
            self.payload = json.load(f)
        
        # Initialize S3 filesystem
        client_kwargs = {}
        if S3_ENDPOINT:
            client_kwargs['endpoint_url'] = S3_ENDPOINT
            # R2 often needs region_name='auto'
            if 'cloudflarestorage.com' in S3_ENDPOINT:
                client_kwargs['region_name'] = 'auto'
            
        self.fs = s3fs.S3FileSystem(
            key=S3_KEY,
            secret=S3_SECRET,
            token=S3_TOKEN,
            client_kwargs=client_kwargs,
            default_fill_cache=False,
            anon=False
        )

    def download_s3_dir(self, s3_path, local_path):
        """Recursively downloads a directory from S3."""
        # Ensure path doesn't have double slashes
        s3_path = s3_path.replace('//', '/')
        if s3_path.startswith('s3:/'):
             s3_path = 's3://' + s3_path[4:].lstrip('/')

        logger.info(f"Downloading {s3_path} to {local_path}...")
        local_path.mkdir(parents=True, exist_ok=True)
        self.fs.get(s3_path, str(local_path), recursive=True)

    def find_index_html(self, directory):
        """Recursively search for index.html or any .html file."""
        for root, _, files in os.walk(directory):
            if 'index.html' in files:
                return Path(root) / 'index.html'
        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith('.html'):
                    return Path(root) / file
        return None

    def flatten_directory(self, directory):
        """
        If the directory contains a single subfolder that contains the game, 
        or if content is nested, moves everything to the root.
        This is necessary because absolute paths like /games/<id>/_downloaded_assets/
        depend on a flat structure.
        """
        logger.info(f"Flattening directory {directory}...")
        
        # Check if there's only one child and it's a directory
        # OR if there's a child folder that matches the zip name
        items = list(directory.iterdir())
        
        # If we have a structure like <id>/<zip_name>/...
        # we move everything from <zip_name> up.
        for item in items:
            if item.is_dir() and (item.name.endswith('.zip') or len(items) == 1):
                logger.info(f"  Moving contents of {item.name} up to {directory.name}")
                for subitem in item.iterdir():
                    dest = directory / subitem.name
                    if dest.exists():
                        if dest.is_dir():
                            shutil.rmtree(dest)
                        else:
                            dest.unlink()
                    shutil.move(str(subitem), str(dest))
                item.rmdir()

    def apply_overrides(self, game_id, game_local_root):
        """Downloads and applies asset overrides for a game."""
        assets = [a for a in self.payload.get('assets', []) if a['game_id'] == game_id]
        if not assets:
            return

        logger.info(f"Applying {len(assets)} overrides for game {game_id}...")
        
        # We need to find the actual game folder (e.g. 'unikong') inside game_local_root
        # to apply overrides correctly to its subfolders.
        game_subfolders = [d for d in game_local_root.iterdir() if d.is_dir() and d.name != '_downloaded_assets']
        
        for asset in assets:
            original_path = asset['original_path']
            s3_path = asset['path']
            
            # Try applying to root or to the specific game subfolder
            targets = [game_local_root / original_path]
            for sub in game_subfolders:
                targets.append(sub / original_path)
            
            # We apply it to the FIRST target that "makes sense" (its parent exists)
            # or just all of them if we are unsure.
            applied = False
            for target_path in targets:
                if target_path.parent.exists():
                    logger.info(f"  Overwriting {target_path.relative_to(self.dist_dir)} with {s3_path}")
                    try:
                        self.fs.get(s3_path, str(target_path))
                        applied = True
                    except Exception as e:
                        logger.error(f"  Failed to apply override to {target_path}: {e}")
            
            if not applied:
                # Fallback to creating the path in game_local_root
                target_path = game_local_root / original_path
                target_path.parent.mkdir(parents=True, exist_ok=True)
                self.fs.get(s3_path, str(target_path))

    def generate_selection_screen(self):
        """Generates the main index.html for the selection screen."""
        games = self.payload.get('games', [])
        
        # Build the HTML
        html_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Arcade Cabinet</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #050b18;
            --card-bg: rgba(255, 255, 255, 0.05);
            --accent-color: #4f46e5;
            --text-color: #f8fafc;
            --glass-border: rgba(255, 255, 255, 0.1);
        }

        body {
            margin: 0;
            padding: 0;
            font-family: 'Outfit', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            background-image: 
                radial-gradient(circle at 20% 20%, rgba(79, 70, 229, 0.15) 0%, transparent 40%),
                radial-gradient(circle at 80% 80%, rgba(139, 92, 246, 0.15) 0%, transparent 40%);
            min-height: 100vh;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 4rem 2rem;
        }

        header {
            text-align: center;
            margin-bottom: 4rem;
            animation: fadeInDown 1s ease-out;
        }

        h1 {
            font-size: 3.5rem;
            margin: 0;
            text-transform: uppercase;
            letter-spacing: 0.2rem;
            background: linear-gradient(to right, #818cf8, #c084fc);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 700;
        }

        .subtitle {
            color: #94a3b8;
            font-size: 1.1rem;
            margin-top: 0.5rem;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 2rem;
        }

        .game-card {
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            border: 1px solid var(--glass-border);
            border-radius: 1.5rem;
            padding: 2.5rem;
            text-decoration: none;
            color: inherit;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            aspect-ratio: 1 / 1;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
            opacity: 0;
            transform: translateY(20px);
            animation: fadeInUp 0.6s forwards;
        }

        .game-card:hover {
            transform: translateY(-10px) scale(1.02);
            background: rgba(255, 255, 255, 0.08);
            border-color: rgba(129, 140, 248, 0.5);
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.2), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
        }

        .game-card h2 {
            margin: 0;
            font-size: 1.75rem;
            font-weight: 600;
            text-align: center;
            letter-spacing: 0.05rem;
        }

        .btn-play {
            margin-top: 1.5rem;
            padding: 0.75rem 2rem;
            background: var(--accent-color);
            border: none;
            border-radius: 9999px;
            color: white;
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.875rem;
            letter-spacing: 0.1rem;
            transition: all 0.3s ease;
        }

        .game-card:hover .btn-play {
            background: #6366f1;
            box-shadow: 0 0 20px rgba(79, 70, 229, 0.4);
        }

        @keyframes fadeInDown {
            from { opacity: 0; transform: translateY(-30px); }
            to { opacity: 1; transform: translateY(0); }
        }

        @keyframes fadeInUp {
            to { opacity: 1; transform: translateY(0); }
        }

        /* Staggered animation for cards */
        .game-card:nth-child(1) { animation-delay: 0.1s; }
        .game-card:nth-child(2) { animation-delay: 0.2s; }
        .game-card:nth-child(3) { animation-delay: 0.3s; }
        .game-card:nth-child(4) { animation-delay: 0.4s; }
        .game-card:nth-child(5) { animation-delay: 0.5s; }

        /* Custom Scrollbar */
        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-track { background: var(--bg-color); }
        ::-webkit-scrollbar-thumb { background: #1e293b; border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: #334155; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Select Game</h1>
            <div class="subtitle">Experience the classic arcade legends</div>
        </header>
        <div class="grid">
            {cards_html}
        </div>
    </div>
</body>
</html>
"""
        card_template = """
            <a href="games/{game_id}/{index_rel}" class="game-card">
                <h2>{name}</h2>
                <button class="btn-play">Play Now</button>
            </a>
"""
        cards_html = ""
        for game in games:
            game_id = game['id']
            name = game['name']
            
            local_game_dir = self.games_dir / game_id
            index_path = self.find_index_html(local_game_dir)
            
            if index_path:
                index_rel = index_path.relative_to(local_game_dir).as_posix()
                cards_html += card_template.format(game_id=game_id, name=name, index_rel=index_rel)
            else:
                logger.warning(f"Could not find index.html for game {name} ({game_id})")

        with open(self.dist_dir / 'index.html', 'w') as f:
            f.write(html_template.replace('{cards_html}', cards_html))

    def build(self):
        """Main orchestrator function."""
        logger.info("Starting static build...")
        
        if self.dist_dir.exists():
            shutil.rmtree(self.dist_dir)
        self.dist_dir.mkdir(parents=True, exist_ok=True)
        self.games_dir.mkdir(parents=True, exist_ok=True)
        
        for game in self.payload.get('games', []):
            game_id = game['id']
            game_name = game['name']
            
            # S3 source for the "extracted" game directory
            # Clean up base remote root
            base_remote = S3_REMOTE_ROOT.rstrip('/')
            
            s3_candidates = []
            
            # According to file_uploads.py, the folder name is stored in zip_uploads.name 
            # and is typically in the format "<uuid>.zip".
            zips = game.get('zip_uploads', [])
            for zip_rec in zips:
                zip_name = zip_rec['name']
                s3_candidates.append(f"{base_remote}/extracted_games/{zip_name}")
            
            # Fallback to game_id
            s3_candidates.append(f"{base_remote}/extracted_games/{game_id}")

            found_s3_path = None
            for cand in s3_candidates:
                # Normalize candidate path
                cand = cand.replace('//', '/')
                if cand.startswith('s3:/'):
                    cand = 's3://' + cand[4:].lstrip('/')
                    
                try:
                    if self.fs.exists(cand):
                        found_s3_path = cand
                        break
                except Exception as e:
                    logger.debug(f"Checked {cand} - Error: {e}")
            
            if not found_s3_path:
                logger.error(f"Could not find S3 directory for game {game_name} ({game_id})")
                continue
            
            # Download game content
            local_game_dir = self.games_dir / game_id
            try:
                self.download_s3_dir(found_s3_path, local_game_dir)
                
                # Flatten the directory structure to handle absolute asset paths
                self.flatten_directory(local_game_dir)
                
                # Apply asset overrides
                self.apply_overrides(game_id, local_game_dir)
            except Exception as e:
                logger.error(f"Failed to process game {game_name}: {e}")

        # Generate the main selection screen
        self.generate_selection_screen()
        
        logger.info(f"Build complete! Output in {self.dist_dir}/")

if __name__ == '__main__':
    orchestrator = StaticBuildOrchestrator()
    orchestrator.build()
