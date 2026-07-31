name: Poll incidents + publish live forecast map
on:
  schedule:
    - cron: "*/20 * * * *"   # every 20 minutes
  workflow_dispatch: {}       # also allows manual "Run workflow" button
permissions:
  contents: write
concurrency:
  group: forecast
  cancel-in-progress: false
jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install pandas numpy requests openpyxl
      - name: Run forecaster (polls 511, updates archive, rebuilds map)
        run: python run.py --hours 48
        env:
          HISTORY_PATH: incident_history.json
      - name: Publish map + CSVs to docs/ (served by GitHub Pages)
        run: |
          mkdir -p docs
          touch docs/.nojekyll
          cp output/risk_map.html docs/index.html
          cp output/*.csv docs/
      - name: Commit archive + published outputs
        run: |
          git config user.name "forecast-bot"
          git config user.email "bot@users.noreply.github.com"
          git add incident_history.json docs/
          git diff --cached --quiet || git commit -m "forecast update $(date -u +%FT%TZ)"
          git push
