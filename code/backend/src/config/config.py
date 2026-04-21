import os

uploads_directory = os.path.join(os.path.dirname(__file__), '../', os.getenv('UPLOADS_DIRECTORY', 'uploads'))
uploads_backend = os.getenv('UPLOADS_BACKEND', '').lower()
uploads_remote_root = os.getenv('UPLOADS_REMOTE_ROOT', '')

s3_endpoint_url = os.getenv('S3_ENDPOINT_URL', '')
s3_access_key_id = os.getenv('S3_ACCESS_KEY_ID', '')
s3_secret_access_key = os.getenv('S3_SECRET_ACCESS_KEY', '')
s3_session_token = os.getenv('S3_SESSION_TOKEN', '')

log_level = os.getenv('LOG_LEVEL', 'ERROR').upper()
db_log_level = os.getenv('DB_LOG_LEVEL', 'ERROR').upper()
db_string = os.getenv('DB_STRING', 'sqlite:///database.db')

github_repo_url = os.getenv('GITHUB_REPO_URL', '')
github_token = os.getenv('GITHUB_TOKEN', '')