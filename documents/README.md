# UA documentation

The frontend is built in vue.js with the quasar framework for ease of use. The backend is built in python with FastAPI and sqlalchemy. The database is deployed on neon.tech, a serverless postgresql provider. The authentication is with cloudflare access. 

architecture diagram:

![architecture diagram](./pictures/architecture-diagram-ua.png)

## About the github actions deploy pipeline

The backend contains a reference to a private key, this is generated from the github app that acts to trigger the docker build workflows. The GitHub app needs read-only access to actions (workflows, workflow runs and artifacts), additionally it needs read/write access to contents (Repository contents, commits, branches, downloads, releases, and merges). 
To deploy this the backend needs the aformentioned private key, the app id and the installation id. The app ID can be found at the top of the settings page for the app. The installation id can be found when looking at the url once the app is installed in the organisation (example: https://github.com/organizations/Thomas-More-Digital-Innovation/settings/installations/installations-id-here). 