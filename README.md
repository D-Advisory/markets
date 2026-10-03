# D-Advisory Markets & Economy dashboard

A markets and economy page for dinian.ca.

- **Markets tab:** live prices through TradingView's free widgets (ticker tape, market overview, S&P 500 heat map, tech and Canada watchlists, economic calendar, news, and a full market chart).
- **Economy tab:** U.S. vs. Canada head-to-head, inflation and jobs, yield curves, and comparison charts, built from official public data (FRED and the Bank of Canada).
- **Automatic updates:** a free GitHub job refreshes the economic data every 15 minutes on weekdays. TradingView prices update on their own.

## What's in this folder

| File | What it does |
|---|---|
| `index.html` | The dashboard page |
| `data/data.js` | The economic data the page reads (rewritten automatically) |
| `scripts/fetch_data.py` | Downloads fresh data from FRED and the Bank of Canada |
| `.github/workflows/update-data.yml` | The schedule that runs the script every 15 minutes on weekdays |
| `wordpress-embed.html` | The code you paste into your WordPress page |

---

## Setup (about 20 minutes, one time)

### Step 1: Create the repository on GitHub
1. Sign in at **github.com** and click **New** (the green button next to "Top repositories"), or go to github.com/new.
2. Repository name: **markets**
3. Choose **Public**. Free GitHub Pages hosting requires a public repository. Only public data is in it.
4. Tick **Add a README file**, then click **Create repository**.

### Step 2: Upload the files
1. In the new repository, click **Add file → Upload files**.
2. Drag in `index.html`, `README.md`, `wordpress-embed.html`, and the **data** and **scripts** folders. Click **Commit changes**.
3. Add the schedule file, which sits in a hidden folder that drag-and-drop often skips:
   - Click **Add file → Create new file**.
   - In the name box, type exactly: `.github/workflows/update-data.yml` (typing the slashes creates the folders).
   - Open `update-data.yml` from this folder in a text editor (Notepad or TextEdit), copy everything, and paste it in.
   - Click **Commit changes**.

### Step 3: Let the schedule save its updates
1. Go to **Settings → Actions → General**.
2. Under **Workflow permissions**, choose **Read and write permissions** and click **Save**.

### Step 4: Turn on the website
1. Go to **Settings → Pages**.
2. Under **Build and deployment**, set Source to **Deploy from a branch**, Branch to **main**, folder **/ (root)**, then click **Save**.
3. After a minute or two, the page shows your address: `https://YOUR-GITHUB-USERNAME.github.io/markets/`. Open it to check the dashboard.

### Step 5: Run the first update
1. Click the **Actions** tab. If asked, click **I understand my workflows, go ahead and enable them**.
2. Click **Update economic data** on the left, then **Run workflow → Run workflow**.
3. Within a minute you should see a green check. The "Economic data updated" time at the top of the dashboard will change. It may take another minute for GitHub Pages to republish.

From then on, it runs by itself every 15 minutes, Monday to Friday, 8 a.m. to about 8 p.m. Toronto time. It only saves a new version when a number actually changes.

### Step 6: Add it to dinian.ca (WordPress)
1. In WordPress, go to **Pages → Add New**. Title it **Markets & Economy**.
2. Click **+** to add a block, search for **Custom HTML**, and add it.
3. Open `wordpress-embed.html`, replace `YOUR-GITHUB-USERNAME` with your GitHub username, copy everything, and paste it into the block.
4. In the page settings, choose a **full-width** template if your theme offers one, so the dashboard gets the whole width.
5. Click **Publish**.
6. Add it to your menu under **Appearance → Menus**. Putting it under **Resources → Insights** fits your current menu.

The frame resizes itself to fit the dashboard, so visitors see one scroll bar. Links to a specific tab work too, for example `…/markets/#economy`.

---

## Good to know

- **TradingView terms.** The widgets are free with TradingView's logo and link left in place. Don't remove the "Market data by TradingView" credits. Because this is a business site, send TradingView a short note through their contact form to confirm commercial use: tradingview.com/widget → "reach out to us".
- **Disclaimer.** The page shows a short notice at the top and a full disclaimer at the bottom, linked to your existing Disclaimer and Terms pages. Have your lawyer review the wording.
- **If a data source is down,** the script keeps the last good data and the page keeps working. A failed run shows a red X in the Actions tab; the next run normally fixes it.
- **Keeping the schedule alive.** GitHub pauses scheduled jobs in repositories with no activity for 60 days. The automatic data commits count as activity, so this normally won't happen. If it does, the Actions tab shows a button to re-enable it.
- **Changing the watchlists.** In `index.html`, search for `symbolsGroups` and edit the names and symbols (format `EXCHANGE:TICKER`, for example `TSX:RY` or `NASDAQ:AAPL`). You can look up symbols on tradingview.com.
- **Changing colors.** The brand colors are at the top of `index.html` (`--navy`, `--orange`).
- **Testing locally.** You can open `index.html` directly in a browser to preview it. To refresh the data by hand on your computer, install Python 3 and run `python scripts/fetch_data.py`.

## Data sources

- **Market prices:** TradingView widgets, under TradingView's licenses. Some exchanges are delayed.
- **U.S.:** FRED (Federal Reserve Bank of St. Louis), republishing U.S. Treasury (H.15), Federal Reserve, BLS, BEA, Freddie Mac (PMMS) and EIA data.
- **Canada:** Bank of Canada Valet API (policy rate, bond yields, CPI measures, USD/CAD; free use with attribution). Unemployment and long-run rate history come from Statistics Canada and OECD via FRED.
- **Not used:** copyrighted index series such as the S&P 500 and VIX levels on FRED, and Yahoo Finance.
