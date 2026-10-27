# UAntwerpen Arcade Cabinet

Interactive retro arcade cabinet running web-based games, created for the **University of Antwerp** by the **Thomas More Digital Innovation** team.

- **Frontend (`code/frontend`)**: Vue 3 + Quasar administrative management portal deployed on Cloudflare Pages / Workers with Cloudflare Access.
- **Backend (`code/backend`)**: FastAPI REST API on Render.com, Neon.tech serverless PostgreSQL database, Cloudflare R2 object storage, and automated offline asset localization engine.
- **Client (`code/client`)**: Raspberry Pi 5 operating system configured with NixOS, Sway Wayland kiosk, and Ultimarc I-PAC 2 arcade hardware controls.
- **CI/CD (`.github/workflows`)**: Automated static build pipeline producing multi-arch Docker images on GitHub Container Registry (GHCR).

---

## Documentation

Full architectural specifications, data flows, and subsystem guides are located in the [`documents/`](documents/README.md) directory:

- **[Master Documentation Hub](documents/README.md)**
- **[System Architecture](documents/ARCHITECTURE.md)**
- **[Backend & Storage Specification](documents/BACKEND.md)**
- **[Frontend Management Portal](documents/FRONTEND.md)**
- **[Raspberry Pi Client & NixOS](documents/CLIENT_PI_NIXOS.md)**
- **[Static Build & Container Deployment](documents/BUILD_AND_DEPLOYMENT.md)**
- **[Architecture Diagram](documents/pictures/architecture-diagram-ua.png)**
