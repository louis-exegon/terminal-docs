# HY Credit Screener — Documentation

MkDocs (Material) site documenting every issuer-level field in the yfinance-based
high-yield credit screener.

## Preview locally
```bash
pip install -r requirements.txt
mkdocs serve            # http://127.0.0.1:8000
```

## Push to your repo (currently empty)
```bash
git init
git add .
git commit -m "Initial field-reference docs"
git branch -M main
git remote add origin <YOUR-REPO-.git-URL>
git push -u origin main
```

## Publishing to GitHub Pages
On every push to `main`, the workflow in `.github/workflows/deploy.yml` runs
`mkdocs gh-deploy`, which builds the site and pushes it to a `gh-pages` branch.

One-time setup: **repo → Settings → Pages → Build and deployment → Source: Deploy
from a branch → Branch: `gh-pages` / `/ (root)`**. The site then lives at
`https://<user>.github.io/<repo>/`.
