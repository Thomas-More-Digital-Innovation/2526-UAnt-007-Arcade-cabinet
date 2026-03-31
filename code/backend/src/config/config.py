import os

uploads_directory =os.path.join(os.path.dirname(__file__), '../', os.getenv('UPLOADS_DIRECTORY', 'uploads'))
log_level = os.getenv('LOG_LEVEL', 'ERROR').upper()
db_log_level = os.getenv('DB_LOG_LEVEL', 'ERROR').upper()