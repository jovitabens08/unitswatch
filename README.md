# ⚡ UnitsWatch — TNEB Energy Consumption Tracker
**Django + MongoDB Atlas Web Application**

Track your TNEB electricity meter readings, predict your bill mid-cycle, and get alerts before you cross the 100-unit free slab.

---

## 🗂️ Project Structure

```
unitswatch/
├── manage.py
├── Procfile               ← Render: gunicorn start command
├── build.sh               ← Render: install + migrate + collectstatic
├── requirements.txt
├── .env                   ← your secrets (never commit this!)
├── .gitignore
│
├── unitswatch/            ← Django project config
│   ├── settings.py        ← all config including MONGO_URI
│   ├── urls.py
│   └── wsgi.py
│
└── tracker/               ← Main Django app
    ├── db.py              ← MongoDB connection (PyMongo singleton)
    ├── tneb.py            ← TNEB billing logic (slabs, prediction, tips)
    ├── views.py           ← 18 view functions
    ├── urls.py            ← 18 URL routes
    ├── models.py          ← empty (MongoDB used directly)
    └── templates/tracker/
        ├── base.html
        ├── login.html
        ├── register.html
        ├── dashboard.html
        ├── meters.html
        ├── meter_detail.html
        ├── billing_cycles.html
        ├── recommendations.html
        └── history.html
```

---

## ⚙️ Local Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure .env
Create a `.env` file in the project root:
```
SECRET_KEY=any-long-random-string-here
DEBUG=True
MONGO_URI=mongodb+srv://<user>:<password>@cluster0.xxxxx.mongodb.net/unitswatch?retryWrites=true&w=majority
```

### 3. Run migrations (Django auth only)
```bash
python manage.py migrate
```

### 4. Start the server
```bash
python manage.py runserver
```
Open **http://localhost:8000**

---

## 🚀 Deploy to Render (Step by Step)

### Step 1 — MongoDB Atlas
1. Go to [mongodb.com/atlas](https://www.mongodb.com/atlas) → create free cluster
2. Database Access → Add user (username + password)
3. Network Access → Add IP → **0.0.0.0/0** (allow all — needed for Render)
4. Connect → Drivers → copy the `mongodb+srv://...` connection string

### Step 2 — Push to GitHub
```bash
git init
git add .
git commit -m "UnitsWatch complete"
git remote add origin https://github.com/YOUR_USERNAME/unitswatch.git
git push -u origin main
```
> ⚠️ Make sure `.env` is in `.gitignore` — never commit secrets!

### Step 3 — Create Render Web Service
1. Go to [render.com](https://render.com) → New → **Web Service**
2. Connect your GitHub repo
3. Set these fields:
   - **Build Command:** `./build.sh`
   - **Start Command:** `gunicorn unitswatch.wsgi:application --workers 2 --timeout 60`

### Step 4 — Add Environment Variables on Render
In Render → your service → **Environment** tab, add:

| Key | Value |
|-----|-------|
| `SECRET_KEY` | any long random string |
| `MONGO_URI` | your Atlas connection string |
| `DEBUG` | `False` |

### Step 5 — Deploy
Click **Deploy** — Render will run `build.sh` automatically.
Your app will be live at `https://your-app-name.onrender.com` 🎉

---

## 📊 MongoDB Collections

| Collection | Stores |
|---|---|
| `meters` | EB meters added by users |
| `readings` | Individual meter reading logs |
| `bills` | Closed billing cycle records |

---

## 🔌 TNEB Slab Rates (per 2-month cycle)

| Units | Rate |
|---|---|
| 0 – 100 | **FREE** |
| 101 – 200 | ₹1.50 / unit |
| 201 – 500 | ₹3.00 / unit |
| 501+ | ₹5.00 / unit |

Fixed charge: ₹30 (only if bill > ₹0)

---

## 🛠️ Tech Stack

- **Backend:** Python 3, Django 4.2
- **Database:** MongoDB Atlas (PyMongo), SQLite (auth only)
- **Frontend:** HTML5, CSS3, Jinja2, Chart.js
- **Deployment:** Render.com, Gunicorn, WhiteNoise
