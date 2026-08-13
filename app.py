from flask import Flask, render_template, request, redirect, url_for, flash, session, g
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = "barterlink-dev-secret-change-in-production"

DATABASE = "barterlink.db"

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            location TEXT,
            bio TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            listing_type TEXT NOT NULL,  -- 'service_for_goods' or 'goods_for_service'
            category TEXT,
            location TEXT,
            what_i_offer TEXT,
            what_i_want TEXT,
            status TEXT DEFAULT 'open',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            listing_id INTEGER NOT NULL,
            from_user_id INTEGER NOT NULL,
            to_user_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (listing_id) REFERENCES listings (id),
            FOREIGN KEY (from_user_id) REFERENCES users (id),
            FOREIGN KEY (to_user_id) REFERENCES users (id)
        );
    """)
    db.commit()

    # Seed sample data if empty
    cur = db.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        # Create sample users
        users = [
            ("maria_g", "maria@example.com", generate_password_hash("password123"), "Austin, TX", "Gardener & home cook"),
            ("james_r", "james@example.com", generate_password_hash("password123"), "Portland, OR", "Handyman & bike repair"),
            ("sofia_t", "sofia@example.com", generate_password_hash("password123"), "Denver, CO", "Spanish tutor & baker"),
            ("alex_k", "alex@example.com", generate_password_hash("password123"), "Austin, TX", "Web designer"),
        ]
        db.executemany(
            "INSERT INTO users (username, email, password_hash, location, bio) VALUES (?, ?, ?, ?, ?)",
            users
        )

        listings = [
            (1, "Fresh backyard vegetables + herbs", 
             "I grow organic tomatoes, peppers, basil, cilantro and more. Can deliver weekly boxes of seasonal produce.",
             "goods_for_service", "Food & Produce", "Austin, TX",
             "Weekly box of fresh organic veggies & herbs (5-8 lbs)",
             "Looking for: light home repairs, painting, or help setting up raised beds"),
            
            (2, "Bike repair & tune-up", 
             "I can fix flats, adjust brakes/gears, true wheels, and do full tune-ups. 10+ years experience.",
             "service_for_goods", "Home & Repair", "Portland, OR",
             "Bike repair / full tune-up (1-2 hours)",
             "Looking for: tools, outdoor gear, or good quality used furniture"),
            
            (3, "Spanish conversation lessons", 
             "Native speaker. Friendly 1-hour sessions for beginners or intermediate. Online or in-person.",
             "service_for_goods", "Education", "Denver, CO",
             "1-hour Spanish conversation lesson",
             "Looking for: homemade baked goods, fresh eggs, or small household items"),
            
            (4, "Website or landing page design", 
             "I design clean, mobile-friendly websites and landing pages. Can also do simple updates.",
             "service_for_goods", "Tech & Digital", "Austin, TX",
             "Simple website or landing page (up to 5 pages)",
             "Looking for: quality used laptop, monitor, or camera gear"),
            
            (1, "Homemade sourdough bread & jam", 
             "Fresh sourdough loaves and small-batch strawberry or fig jam. Baked weekly.",
             "goods_for_service", "Food & Produce", "Austin, TX",
             "2 loaves of sourdough + 1 jar of jam",
             "Looking for: help with garden weeding or fence repair"),
            
            (2, "Appliance repair (small appliances)", 
             "I fix toasters, blenders, coffee makers, fans, etc. Usually same-day if parts are simple.",
             "service_for_goods", "Home & Repair", "Portland, OR",
             "Repair of one small appliance",
             "Looking for: tools, camping gear, or bicycle parts"),
        ]
        db.executemany(
            """INSERT INTO listings 
               (user_id, title, description, listing_type, category, location, what_i_offer, what_i_want)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            listings
        )
        db.commit()
        print("Database seeded with sample users and listings.")

@app.before_request
def load_logged_in_user():
    user_id = session.get("user_id")
    if user_id is None:
        g.user = None
    else:
        g.user = get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

@app.route("/")
def index():
    db = get_db()
    listings = db.execute("""
        SELECT l.*, u.username, u.location as user_location
        FROM listings l
        JOIN users u ON l.user_id = u.id
        WHERE l.status = 'open'
        ORDER BY l.created_at DESC
        LIMIT 12
    """).fetchall()
    return render_template("index.html", listings=listings)

@app.route("/browse")
def browse():
    db = get_db()
    listing_type = request.args.get("type")
    category = request.args.get("category")
    q = request.args.get("q", "").strip()

    query = """
        SELECT l.*, u.username, u.location as user_location
        FROM listings l
        JOIN users u ON l.user_id = u.id
        WHERE l.status = 'open'
    """
    params = []

    if listing_type in ("service_for_goods", "goods_for_service"):
        query += " AND l.listing_type = ?"
        params.append(listing_type)
    if category:
        query += " AND l.category = ?"
        params.append(category)
    if q:
        query += " AND (l.title LIKE ? OR l.description LIKE ? OR l.what_i_offer LIKE ? OR l.what_i_want LIKE ?)"
        like = f"%{q}%"
        params.extend([like, like, like, like])

    query += " ORDER BY l.created_at DESC"
    listings = db.execute(query, params).fetchall()

    categories = db.execute("SELECT DISTINCT category FROM listings WHERE category IS NOT NULL ORDER BY category").fetchall()
    return render_template("browse.html", listings=listings, categories=categories,
                           current_type=listing_type, current_category=category, q=q)

@app.route("/listing/<int:listing_id>")
def listing_detail(listing_id):
    db = get_db()
    listing = db.execute("""
        SELECT l.*, u.username, u.location as user_location, u.bio, u.id as owner_id
        FROM listings l
        JOIN users u ON l.user_id = u.id
        WHERE l.id = ?
    """, (listing_id,)).fetchone()
    if not listing:
        flash("Listing not found.", "error")
        return redirect(url_for("browse"))
    return render_template("listing.html", listing=listing)

@app.route("/post", methods=["GET", "POST"])
def post_listing():
    if g.user is None:
        flash("Please log in to post a listing.", "error")
        return redirect(url_for("login"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        listing_type = request.form.get("listing_type")
        category = request.form.get("category", "").strip()
        location = request.form.get("location", "").strip() or g.user["location"]
        what_i_offer = request.form.get("what_i_offer", "").strip()
        what_i_want = request.form.get("what_i_want", "").strip()

        if not all([title, description, listing_type, what_i_offer, what_i_want]):
            flash("Please fill in all required fields.", "error")
            return render_template("post.html")

        db = get_db()
        db.execute("""
            INSERT INTO listings (user_id, title, description, listing_type, category, location, what_i_offer, what_i_want)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (g.user["id"], title, description, listing_type, category, location, what_i_offer, what_i_want))
        db.commit()
        flash("Listing posted successfully!", "success")
        return redirect(url_for("browse"))

    return render_template("post.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        location = request.form.get("location", "").strip()
        bio = request.form.get("bio", "").strip()

        if not username or not email or not password:
            flash("Username, email and password are required.", "error")
            return render_template("register.html")

        db = get_db()
        try:
            db.execute(
                "INSERT INTO users (username, email, password_hash, location, bio) VALUES (?, ?, ?, ?, ?)",
                (username, email, generate_password_hash(password), location, bio)
            )
            db.commit()
            flash("Account created! Please log in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Username or email already taken.", "error")

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            flash(f"Welcome back, {user['username']}!", "success")
            return redirect(url_for("index"))
        flash("Invalid username or password.", "error")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))

@app.route("/propose/<int:listing_id>", methods=["POST"])
def propose_trade(listing_id):
    if g.user is None:
        flash("Please log in to propose a trade.", "error")
        return redirect(url_for("login"))

    content = request.form.get("message", "").strip()
    if not content:
        flash("Please write a message.", "error")
        return redirect(url_for("listing_detail", listing_id=listing_id))

    db = get_db()
    listing = db.execute("SELECT * FROM listings WHERE id = ?", (listing_id,)).fetchone()
    if not listing:
        flash("Listing not found.", "error")
        return redirect(url_for("browse"))

    if listing["user_id"] == g.user["id"]:
        flash("You cannot propose a trade on your own listing.", "error")
        return redirect(url_for("listing_detail", listing_id=listing_id))

    db.execute("""
        INSERT INTO messages (listing_id, from_user_id, to_user_id, content)
        VALUES (?, ?, ?, ?)
    """, (listing_id, g.user["id"], listing["user_id"], content))
    db.commit()
    flash("Your trade proposal has been sent!", "success")
    return redirect(url_for("listing_detail", listing_id=listing_id))

if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)
