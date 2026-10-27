# Frontend Architecture & Management Portal

The frontend is an administrative web dashboard built with **Vue 3**, the **Quasar Framework**, and **TypeScript**. It is hosted as a Single Page Application (SPA) on **Cloudflare Pages / Workers**.

The management portal provides an interface for arcade administrators and students to manage games, replace individual game assets, test games in an authentic arcade aspect ratio, and trigger releases to the physical arcade cabinet.

---

## 1. Directory Structure

```text
code/frontend/
├── index.html                 # Single page application entrypoint
├── package.json               # Dependencies, scripts, and build tasks
├── quasar.config.ts           # Quasar framework & Vite configuration
├── wrangler.jsonc             # Cloudflare Workers / Pages deployment settings
├── src/
│   ├── App.vue                # Root Vue component with notification dialogs
│   ├── boot/
│   │   └── axios.js           # Axios instance configured with baseURL and X-API-Key
│   ├── components/
│   │   ├── GameCard.vue       # Game card with active toggle, edit, delete, and test overlay
│   │   └── NotificationDialog.vue # Feedback and toast dialogs
│   ├── layouts/
│   │   └── MainLayout.vue     # Application shell, header, and navigation
│   ├── pages/
│   │   ├── IndexPage.vue      # Main dashboard: games grid, modals, and asset inspector
│   │   └── ErrorNotFound.vue  # 404 fallback page
│   ├── stores/
│   │   └── notification.ts    # Pinia notification store
│   └── css/
│       ├── app.css            # Custom Quasar styling
│       └── tailwind.css       # Tailwind CSS utility classes
```

---

## 2. Configuration & Deployment

### Environment Variables
The application uses Vite environment variables configured in `.env`:

| Variable | Description | Example |
| :--- | :--- | :--- |
| `VITE_API_BASE_URL` | Base URL pointing to the FastAPI backend | `https://arcade-backend.onrender.com` or `http://localhost:8000` |
| `VITE_API_KEY` | Shared secret key for API authorization | `your-secret-api-key` |

### Cloudflare Access & Workers Deployment
The application is deployed to **Cloudflare Workers / Pages** and protected behind **Cloudflare Access** (Zero Trust authentication) to ensure only authorized personnel can access the management panel.

The deployment configuration is defined in [`wrangler.jsonc`](../code/frontend/wrangler.jsonc):
```jsonc
{
  "name": "2526-uant-007-arcade-cabinet",
  "compatibility_date": "2026-04-21",
  "compatibility_flags": ["nodejs_compat"],
  "assets": {
    "directory": "dist/spa",
    "not_found_handling": "single-page-application"
  }
}
```
When built with `quasar build`, the SPA artifacts are emitted to `dist/spa` and served globally via Cloudflare Workers assets.

---

## 3. Key Features & Workflows

### 3.1. Game Catalog & Active Toggle
- Displays all registered games in a responsive grid.
- Each game card features an **Active** checkbox.
- Toggling the active state sends a `PUT /games/{id}` request to update the database. Only games marked **Active** will be packaged onto the physical arcade machine during the next build.

### 3.2. Game Upload Wizard
- Clicking **"Add Game"** opens a modal where administrators specify the game title and description.
- A Quasar `q-uploader` accepts the game bundle packaged as a `.zip` archive.
- Uploads the file via `POST /file-uploads/upload-zip`, which automatically unpacks the archive, runs the internet asset localizer, and establishes the game in cloud storage.

### 3.3. Asset Inspector & Replacement Engine
In **Edit Game** mode, the frontend calls `GET /games/{id}/analyzed-assets` to introspect the game package:
- **Media Classification**: Identifies images (`image/*`) and audio files (`audio/*`).
- **Original vs Replacement View**: Displays the original asset alongside any uploaded replacement.
- **Resolution Detection**: Dynamically calculates and renders image dimensions (e.g. `64x64px`, `1280x720px`) for both the original and replacement files. This helps creators match asset pixel dimensions precisely.
- **Audio Playback**: Embeds HTML5 `<audio>` controls to preview sound effects and music tracks.
- **Asset Replacement Upload**: Administrators can click "Upload Replacement" to swap out a texture or sound effect via `POST /games/{id}/upload-asset`.
- **Reversion**: Clicking "Revert to Original" deletes the override via `DELETE /games/{id}/asset-override`.

### 3.4. In-Browser Game Tester & Auto-Scaler (`GameCard.vue`)
To verify game functionality before pushing to the physical cabinet, users can click **"Test"**:
- Opens a fullscreen modal running the game inside an `<iframe>` targeting `/games/{id}/test`.
- **Dynamic Viewport Scaling**:
  - Arcade games are often developed for fixed canvas resolutions (e.g., 800x600, 1280x720).
  - The component inspects the iframe's internal `<canvas>` or document scroll dimensions upon loading.
  - It calculates independent horizontal (`scaleX`) and vertical (`scaleY`) scale factors based on the current window size:
    ```typescript
    scaleX = window.innerWidth / nativeW;
    scaleY = window.innerHeight / nativeH;
    ```
  - Applies a CSS transform `scale(scaleX, scaleY)` from `top left`, ensuring games fill the screen without letterboxing.

### 3.5. Remote Cabinet Update ("Update Pi")
- Located at the top of the dashboard, the **"Update Pi"** button initiates a synchronized deployment:
  1. Calls `POST /trigger-build/trigger-workflow`.
  2. Opens a status dialog showing the current deployment phase.
  3. Begins polling `GET /trigger-build/workflow-status` every 500ms.
  4. Displays real-time GitHub Actions step progress:
     - `Total Steps`
     - `Completed Steps`
     - `Current Step Name` (e.g., "Build Static Site", "Build and push Docker image").
  5. Notifies the user upon successful completion or provides actionable error details if permissions or network errors occur.

