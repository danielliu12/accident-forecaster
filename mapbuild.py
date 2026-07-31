# One-time setup: always-on incident archive + live hosted map (~10 min)

You need: a free GitHub account (github.com → Sign up).

1. On GitHub click **+** (top right) → **New repository**. Name it
   `accident-forecaster`, leave it **Private** if you prefer (Pages works
   on private repos only with paid plans — choose **Public** for the free
   live URL; the repo contains no client data, only public-source counts).
   Click **Create repository**.
2. Click **uploading an existing file** on the new repo's page. Drag the
   ENTIRE unzipped `accident_forecaster` folder's *contents* (not the
   folder itself) into the upload box — including the `.github` folder.
   If your browser won't drag the hidden `.github` folder: upload
   everything else first, then click **Add file → Create new file**, type
   `.github/workflows/forecast.yml` as the name, and paste that file's
   contents in. Click **Commit changes**.
3. Repo **Settings → Pages** → under "Build and deployment", Source =
   **Deploy from a branch**, Branch = **main**, folder = **/docs** → Save.
4. Repo **Settings → Actions → General** → Workflow permissions →
   select **Read and write permissions** → Save.
5. Go to the **Actions** tab → "Poll incidents + publish live forecast
   map" → **Run workflow** (button on the right) to kick off the first
   run. After ~2 minutes it commits the first map.

Done. From then on it runs itself every 20 minutes, forever:
- your live map: `https://YOURUSERNAME.github.io/accident-forecaster/`
- the growing incident archive: `incident_history.json` in the repo

Last step, to let Colab use the machine-built archive: in the notebook's
Config cell area there is a line `INCIDENT_LOG_URL = None` — I will have
already set it for you if you tell me your GitHub username, or you can
edit that one line to:
`INCIDENT_LOG_URL = "https://raw.githubusercontent.com/YOURUSERNAME/accident-forecaster/main/incident_history.json"`

Note: GitHub pauses scheduled workflows on repos with no activity for 60
days — opening the Actions tab and clicking "Enable" resumes it. If the
511 api/v2 endpoint asks for a key, register free at 511in.org (developer
link at page bottom) and put it in config.py as TRAFFICWISE_API_KEY.
