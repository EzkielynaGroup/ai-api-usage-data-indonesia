# Publishing notes (owner)

**GitHub description (<= 120 chars):**
Daily open data (CC BY 4.0): which AI models Indonesian developers use, uptime, latency and list prices. One gateway.

**Topics:** dataset, open-data, ai, llm, llm-pricing, ai-models, leaderboard, indonesia, deepseek, api-usage, github-actions, cc-by

**Homepage:** https://ezkielyna.store/peringkat?utm_source=github&utm_medium=repo&utm_campaign=ai-api-usage-data-indonesia

**Owner actions (not done, build was local only):**
1. Create the public repo `EzkielynaGroup/ai-api-usage-data-indonesia`, push `main`.
2. Settings → Actions → General: allow actions and "Read and write permissions" for `GITHUB_TOKEN` (the workflow also asks for `contents: write`). Then run the workflow once by hand (Actions → Update data → Run workflow) to confirm it commits.
3. GitHub disables scheduled workflows after 60 days without repository activity; the daily data commits count as activity, but if the source stops changing, re-enable the workflow from the Actions tab.
4. Optional: list on Kaggle Datasets / Hugging Face Datasets (mirror `latest/`), awesome-public-datasets, and link from https://ezkielyna.store/peringkat.
5. Each month: add a new recap under `reports/` (copy the published text, drop draft banners, link the published post) with its snapshot data in `reports/data/<date>/`.
