from github import Github, Auth
from config import config
import os

def check():
    with open(config.github_private_key_path, 'r') as f:
        private_key = f.read()
    
    auth = Auth.AppAuth(int(config.github_app_id), private_key).get_installation_auth(int(config.github_installation_id))
    g = Github(auth=auth)
    
    repo_name = f"{config.github_repo_owner}/{config.github_repo_name}"
    repo = g.get_repo(repo_name)
    runs = repo.get_workflow_runs(event="repository_dispatch")
    
    if runs.totalCount > 0:
        run = runs[0]
        print(f"Attributes: {dir(run)}")
    else:
        print("No runs found to check")

if __name__ == "__main__":
    try:
        check()
    except Exception as e:
        print(f"Error: {e}")
