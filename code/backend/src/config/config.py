"""
Configuration module for the application.
"""
import json
import os

uploads_directory = os.path.join(
    os.path.dirname(__file__),
    '../',
    os.getenv('UPLOADS_DIRECTORY', 'uploads')
)
uploads_backend = os.getenv('UPLOADS_BACKEND', '').lower()
uploads_remote_root = os.getenv('UPLOADS_REMOTE_ROOT', '')

s3_endpoint_url = os.getenv('S3_ENDPOINT_URL', '')
s3_access_key_id = os.getenv('S3_ACCESS_KEY_ID', '')
s3_secret_access_key = os.getenv('S3_SECRET_ACCESS_KEY', '')
s3_session_token = os.getenv('S3_SESSION_TOKEN', '')

log_level = os.getenv('LOG_LEVEL', 'ERROR').upper()
db_log_level = os.getenv('DB_LOG_LEVEL', 'ERROR').upper()
db_string = os.getenv('DB_STRING', 'sqlite:///database.db')

github_app_id = os.getenv('GITHUB_APP_ID', '')

_src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
github_private_key_path = os.getenv('GITHUB_PRIVATE_KEY_PATH', '')
if github_private_key_path and not os.path.isabs(github_private_key_path):
    github_private_key_path = os.path.join(_src_dir, github_private_key_path)

github_installation_id = os.getenv('GITHUB_INSTALLATION_ID', '')
github_repo_owner = os.getenv('GITHUB_REPO_OWNER', '')
github_repo_name = os.getenv('GITHUB_REPO_NAME', '')
api_key = os.getenv('API_KEY', '')

cors_env = os.getenv('CORS_ALLOWED_ORIGINS', '[]')
try:
    cors = json.loads(cors_env)
except json.JSONDecodeError:
    cors = [origin.strip() for origin in cors_env.split(',') if origin.strip()]
