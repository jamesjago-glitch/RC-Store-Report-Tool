# State of DTC Storefronts — runs itself on GitHub

No Colab. No tab to keep open. It runs on GitHub's servers, so your Mac can sleep or be shut. You start it, walk away, come back to the files.

## One-time setup (about 5 minutes)

1. **Sign in at github.com.** If you don't have an account, create one (free).
2. **Make a new repository.** Top-right **+** → **New repository**. Name it `storefront-benchmark`, leave it Private, click **Create repository**.
3. **Upload these two files** (keep the folders). On the new repo page click **uploading an existing file**, then drag in:
   - `storefront_discover_score.py`
   - the `.github` folder (with `workflows/run.yml` inside it)
   Click **Commit changes**.
4. **Add your PageSpeed key as a secret.** In the repo: **Settings → Secrets and variables → Actions → New repository secret**.
   - Name: `PSI_API_KEY`
   - Secret: paste your key
   - **Add secret**

## Run it (any time, 10 seconds)

1. Go to the **Actions** tab. If it asks, click **I understand my workflows, enable them**.
2. Click **Storefront Benchmark** on the left, then **Run workflow** (right).
3. Leave `pool` and `per_niche` as they are for the first run. Click the green **Run workflow**.
4. Close the tab. Go do something else. It runs on GitHub, not your machine.

## Get the results

1. Come back to the **Actions** tab in an hour or so. The run shows a green tick when done.
2. Click into the run, scroll to **Artifacts** at the bottom, download **storefront-benchmark**.
3. It's a zip containing `dashboard.html` (open in any browser), `ranking.csv`, `leads_migrate.csv`, `leads_upgrade_plus.csv`.

## Making it bigger later

On the Run workflow screen, raise `pool` (e.g. 60000 or 120000) for wider coverage. Higher = more stores and a longer run, but it still runs unattended.
