# BarterLink

**Trade skills for stuff. No money required.**

A simple community barter platform where people can:
- Offer **services / skills** in exchange for **goods**
- Offer **goods / products** in exchange for a **specific job or service**

Built with Flask + SQLite. Mobile-friendly.

---

## Quick Start

### 1. Requirements
- Python 3.8+
- Flask (install with `pip install flask`)

### 2. Run the site

```bash
cd barterlink
python app.py
```

Then open in your browser:  
**http://127.0.0.1:5000**

(On a phone on the same network you can use your computer’s local IP.)

### 3. Demo accounts
All use password: `password123`

- `maria_g` – gardener / home cook (Austin)
- `james_r` – handyman / bike repair (Portland)
- `sofia_t` – Spanish tutor / baker (Denver)
- `alex_k` – web designer (Austin)

---

## Features in this version
- User registration & login
- Post listings (Service→Goods or Goods→Service)
- Browse + search + filter by type/category
- Listing detail pages
- Propose a trade (sends a message to the owner)
- Clean, mobile-first design

---

## Project structure
```
barterlink/
├── app.py              # Main application
├── barterlink.db       # SQLite database (created automatically)
├── templates/          # HTML pages
├── static/css/         # Styles
└── README.md
```

---

## Next possible improvements
- Real messaging inbox
- Photo uploads
- Location-based search / map
- Ratings & completed trades
- Email notifications
- Deploy to Render / Railway / PythonAnywhere (free tiers available)

---

Made for people who believe skills and goods have real value.
