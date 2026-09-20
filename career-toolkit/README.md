# Career Toolkit

A personal dashboard that takes a job role, company, and job description and generates:

- **Interview prep** — general role questions, company-style questions, and scenario/behavioral questions grounded in the actual job description.
- **Resume builder** — an ATS-friendly resume tailored to the job description, written only from the real background you paste in or upload (it's instructed not to invent employers, dates, or achievements). Download the result as `.txt` or a clean `.docx`.
- **Cover letter** — one click from the same form (same role/company/JD/background), no separate inputs.
- **Resume upload** — upload your existing resume as a PDF or Word file and it's read straight into the background box, ready to tailor.
- **Job matching** — after a resume is generated, search live postings for it (via Adzuna) filtered by Remote / Hybrid / On-site, with a salary range estimated from the postings that actually disclosed one.
- **Application tracker** — save a match you're interested in and move it through Applied → Interviewing → Offer/Rejected, with a spot for notes.

Backend: Python/FastAPI. AI: Gemini (`google-genai` SDK, with automatic retry on transient failures). Job data: Adzuna API (optional — everything else works without it). Storage: SQLite (history log + tracker — no external database to run). Single shared password protects the whole thing, with a lockout after repeated wrong attempts, since it's meant for you, reachable from anywhere.

## What was and wasn't tested here

Every Python file is syntax-checked. Both HTML templates were actually rendered with Jinja2 against sample data (including the empty-history state) and came out correctly. Real, executed tests (not just syntax checks) cover: history storage and the application tracker (both round-tripped through real SQLite, including status updates, notes, and delete), prompt building, the job-search helpers (`_infer_work_mode`, `estimate_salary`), the login-lockout counter, and the Gemini retry logic (tested by feeding it a fake function that fails twice then succeeds, and a separate one that fails with a bad-key-shaped error to confirm it does *not* waste retries on that). The CI workflow's own steps (syntax check, template render) are exactly the checks that have been run by hand throughout -- now they'll run on every push automatically.

What couldn't be run here: anything touching `fastapi`, `pydantic`, `google-genai`, `pypdf`, or `python-docx` for real, since those need internet to install and this sandbox doesn't have any. That covers the actual server startup, the live Gemini calls, the live Adzuna calls, and the PDF/DOCX file handling — all written carefully and checked against current docs, but your run in **1. Run it locally** below is the first time any of that code actually executes end-to-end. Watch the terminal the first time you try each feature so anything that needs a fix surfaces immediately.

---

## 1. Run it locally

```bash
cd career-toolkit
chmod +x run.sh
cp .env.example .env
```

Open `.env` and fill in:
- `GEMINI_API_KEY` — get one free at [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey). Sign in, click **Create API key**. When you create it, restrict it to "Gemini API" only.
- `APP_PASSWORD` — any password you'll remember; this locks the dashboard.
- `SECRET_KEY` — run `python3 -c "import secrets; print(secrets.token_hex(32))"` and paste the output.
- `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` — optional, only needed for the "find matching jobs" feature. Free at [developer.adzuna.com/signup](https://developer.adzuna.com/signup) — sign up, create an app, copy the two values. Leave blank and everything else still works; that one feature will just show a clear error if you use it.

Then:

```bash
./run.sh
```

This creates a virtual environment, installs everything in `requirements.txt`, and starts the server. Visit `http://localhost:8000`, log in with your password, and try both modes with a real job posting. Fix anything that looks wrong before moving on — it's much easier to debug on localhost than on a live server.

**A heads-up on the model:** as of today (Sept 2026), `GEMINI_MODEL` defaults to `gemini-3.1-pro-preview`. Google is shutting down all Gemini 2.5 models on **16 October 2026**, and "preview" model names get replaced over time. If generation ever starts failing with a "model not found"-type error, check [ai.google.dev/gemini-api/docs/models](https://ai.google.dev/gemini-api/docs/models) for the current Pro-tier model id and update `GEMINI_MODEL` in `.env` — no code changes needed.

---

## 2. Find your IPs

```bash
hostname -I          # private IP (e.g. 192.168.1.42)
curl ifconfig.me      # public IP, run this ONE FROM THE SERVER ITSELF
```

- **Private IP** reaches the server from other devices on the same network.
- **Public IP** reaches it from anywhere — but only works once the port is actually open to the internet, which depends on what kind of machine this is:
  - **Home server / PC behind a router:** you need to add a port-forwarding rule on the router (forward external port 8000 → the server's private IP, port 8000). Every router's UI is different; search "[your router model] port forwarding."
  - **Cloud VPS (DigitalOcean, AWS EC2, Linode, etc.):** the public IP is already yours — you instead need to open the port in the firewall. On the server: `sudo ufw allow 8000/tcp`. On AWS specifically, also open it in the instance's Security Group.

## 3. About your 1GB server

A few things matter more on a 1GB box than they would on something bigger:

- **Add swap**, or the app risks getting OOM-killed under any real load — Python + FastAPI + the OS itself can use most of 1GB with no room to spare. On Ubuntu:
  ```bash
  sudo fallocate -l 2G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
  ```
- **Run one worker, not several.** `run.sh` and the systemd file below already start a single `uvicorn` process with no `--workers` flag — leave it that way. Each extra worker loads its own copy of everything into RAM.
- **Cloud firewalls are two layers.** `ufw` (or `firewalld`) is the OS-level layer; most cloud providers — Oracle Cloud included — also enforce a network-level firewall in front of the VM (on Oracle this is a Security List / Network Security Group on the VCN). Both have to allow the port or traffic never arrives; forgetting the cloud-level one is the single most common "why can't I reach my server" issue on Oracle's free tier specifically.
- **If the image is Oracle Linux** rather than Ubuntu, swap `apt` → `dnf` and `ufw` → `firewalld` in the commands elsewhere in this file; the systemd steps below are identical either way.

## 4. Run it continuously (systemd)

This is what keeps it running after you log out, and restarts it if it ever crashes.

```bash
# from inside career-toolkit/, with .venv and .env already set up
sudo cp career-toolkit.service /etc/systemd/system/
```

Edit `/etc/systemd/system/career-toolkit.service` first — replace `youruser` and the paths with your real Linux username and the real path to this folder. Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now career-toolkit
sudo systemctl status career-toolkit      # should say "active (running)"
```

Useful commands going forward:

```bash
journalctl -u career-toolkit -f           # live logs (leave this open while you test)
sudo systemctl restart career-toolkit     # after any code change
sudo systemctl stop career-toolkit
```

**The build → test → fix loop you asked for:** edit code → `sudo systemctl restart career-toolkit` → watch `journalctl -u career-toolkit -f` while you use the site → fix what breaks → repeat. That log stream is where you'll see the actual Python tracebacks if something errors.

**Know when it goes down:** `/api/health` returns `{"status": "ok"}` whenever the app is up. Point a free service like [UptimeRobot](https://uptimerobot.com) at `http://your-domain-or-ip:8000/api/health` on a 5-minute interval and you'll get an email/SMS if it ever stops responding. No code needed — just a URL to paste into their dashboard once you have one running.

**Continuous integration:** `.github/workflows/ci.yml` runs on every push to `main` — syntax-checks all the Python, confirms both templates still render, and lints with `ruff` (non-blocking for now, since it's never run against this exact code before; see `ruff.toml`). Nothing to set up — GitHub runs it automatically once this is pushed.

## 5. Put it behind a domain + HTTPS (strongly recommended)

Right now, anyone using `http://your-ip:8000` sends the login password in **plain text**. If you have a domain (even a cheap one), this fixes it:

1. Point an A record at your server's public IP.
2. `sudo apt install nginx certbot python3-certbot-nginx`
3. Use `nginx.example.conf` as a starting point — copy it to `/etc/nginx/sites-available/career-toolkit`, edit `your-domain.com`, then:
   ```bash
   sudo ln -s /etc/nginx/sites-available/career-toolkit /etc/nginx/sites-enabled/
   sudo nginx -t && sudo systemctl reload nginx
   sudo certbot --nginx -d your-domain.com
   ```
4. Now you can close port 8000 to the outside world entirely (only nginx needs to reach it, and it does that over `localhost`) and just open 80/443.

If you don't have a domain yet, the raw `ip:port` setup still works for personal use — just know the password is visible to anyone who can see the network traffic between you and the server.

## 6. Push to GitHub

Don't paste a GitHub password or token into a chat with any AI, including this one — that's exactly the kind of secret that shouldn't leave your machine. Do this instead, from your own terminal:

```bash
cd career-toolkit
git init
git add .
git commit -m "Initial commit: career toolkit"
```

Create an empty repo on github.com (no README/license, so it doesn't conflict), then:

```bash
git remote add origin https://github.com/yourusername/career-toolkit.git
git branch -M main
git push -u origin main
```

Git will prompt for credentials on push. Use a **Personal Access Token**, not your password (GitHub stopped accepting passwords for this): GitHub → Settings → Developer settings → Personal access tokens → generate one with just the `repo` scope, and paste it in when prompted in place of a password. Your `.env` is already in `.gitignore`, so your API key and app password won't get committed — double check with `git status` before your first commit that `.env` isn't listed.

## 7. Back up your history

`data/history.db` is the only real state in this whole app -- every generated resume and question set lives there. A daily copy is cheap insurance:

```bash
crontab -e
# add this line:
0 3 * * * cp /home/youruser/career-toolkit/data/history.db /home/youruser/career-toolkit/data/history-$(date +\%Y\%m\%d).db
```

Delete old copies occasionally (or point that line at a small script that keeps the last 7) so they don't pile up.

## 8. Project layout

```
career-toolkit/
├── .github/workflows/ci.yml  # syntax check + template check + lint, on every push
├── ruff.toml             # minimal lint rules (real bugs only, not style)
├── app/
│   ├── main.py          # FastAPI routes
│   ├── gemini_client.py # Gemini API wrapper, with retry-on-transient-failure
│   ├── job_search.py    # Adzuna job search + salary estimate
│   ├── resume_files.py  # PDF/DOCX upload parsing + .docx export
│   ├── tracker.py       # application tracker (Applied/Interviewing/Offer/Rejected)
│   ├── prompts.py       # prompt templates (edit these to change tone/output)
│   ├── auth.py          # password + session check + login lockout
│   ├── history.py       # SQLite history log
│   ├── models.py        # request validation
│   └── config.py        # reads .env
├── templates/            # HTML pages
├── static/css, static/js # dashboard styling + frontend logic
├── data/history.db       # created automatically on first run (history + tracker tables)
├── career-toolkit.service, nginx.example.conf, run.sh
└── .env                  # you create this, never committed
```

## Ideas for later (not built yet, kept out of v1 on purpose)

- **More job sources** — Adzuna doesn't cover every country (notably not Ireland or the UAE from what's confirmed as of this writing); adding Remotive or Arbeitnow as a second source for remote-heavy searches would be a natural next step, and `job_search.py` is written so a second source can plug in alongside `search_jobs()` without touching the rest of the app.
- **Multiple accounts / signup** — only worth it if this stops being just-for-you.
- **Swap Gemini for a self-hosted Ollama model** — since you already run Private AI Workspaces deployments, `gemini_client.py` is the only file that would need to change; everything else (prompts, routes, history, frontend) is model-agnostic.
- **Drag-and-drop on the tracker board** — right now moving a card between columns is a dropdown, which works fine but isn't as satisfying as dragging it. Purely cosmetic.
