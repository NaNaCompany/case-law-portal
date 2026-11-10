# Case-law portal maintenance

Preserve the site as a static, independently deployed GitHub Pages project. The canonical base is https://nanalab.kr/case-law-portal/. Keep one stable HTML page per judgment. Do not rename existing judgment IDs or claim exhaustive/current coverage.

Change templates in scripts/build.py, styling in assets/style.css and search behavior in assets/app.js, then rebuild generated pages. Keep NaNa Lab's existing publisher tags and common banner unless asked to change them.

Only import official public judgments after reviewing the actual original source, access terms, reproduction restrictions, metadata, anonymization and every judgment section. Never substitute an editorial summary for a judgment. Preserve all anonymized labels. Do not import private publisher notes, prohibited judgments, secrets or unreviewed personal identifiers.

The current renderer handles text-only Korean law.go.kr judgment sections. If a source contains a table, image, formula or attachment, inspect it and extend the renderer or clearly delimit the reproduced scope before publication. Do not silently discard non-text content. New jurisdictions require separately reviewed source conditions and implemented validation.

Use scripts/import_reviewed.py with the adjacent original HTML; original evidence stays outside the public repository. Do not bypass CAPTCHA, authentication, WAF, robots restrictions or rate limits. Registered API credentials must remain outside Git and be used only with their issuing service. Never use documentation example credentials in production.

Run python scripts/build.py --check, python scripts/validate.py, python -m unittest discover -s tests and node --check assets/app.js. Test real search results, no results, clearing the search, keyboard access, case navigation and mobile layout. Preserve original text hashes. Reimporting an unchanged case must be a no-op; conflicting source versions require explicit review.

Before publishing, compare remote main, preserve concurrent work, and push only authorized changes. Check the exact commit's GitHub Pages build and live page/sitemap content. Root discovery is managed separately in NaNaCompany/NaNaCompany.github.io; do not overwrite that repository or its existing sitemaps. If the portal exceeds its current sitemap/list limits, partition leaf sitemaps and update root registrations together.
