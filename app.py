from flask import Flask, render_template, request, redirect, url_for, flash, g, session
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = "change-this-to-a-real-secret-key-later"
app.config["UPLOAD_FOLDER"] = "static/uploads"
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB max upload

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

DATABASE = "barterlink.db"


def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def init_db():
    with app.app_context():
        db = get_db()
        db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                bio TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS listings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                looking_for TEXT,
                image TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            );
        """)
        db.commit()


@app.before_request
def load_logged_in_user():
    user_id = session.get("user_id")
    if user_id is None:
        g.user = None
    else:
        db = get_db()
        g.user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


# ---------- Auth ----------

@app.route("/register", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(url_for("browse"))

    if request.method == "POST":
        username = request.form["username"].strip()
        email = request.form["email"].strip()
        password = request.form["password"]
        confirm = request.form["confirm"]
        bio = request.form.get("bio", "").strip()

        if not username or not email or not password:
            flash("All fields are required.", "error")
        elif password != confirm:
            flash("Passwords do not match.", "error")
        elif len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
        else:
            db = get_db()
            try:
                db.execute(
                    "INSERT INTO users (username, email, password, bio) VALUES (?, ?, ?, ?)",
                    (username, email, generate_password_hash(password), bio),
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
        return redirect(url_for("browse"))

    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

        if user is None or not check_password_hash(user["password"], password):
            flash("Invalid username or password.", "error")
        else:
            session.clear()
            session["user_id"] = user["id"]
            flash(f"Welcome back, {user['username']}!", "success")
            return redirect(url_for("browse"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("browse"))


# ---------- Listings ----------

@app.route("/")
@app.route("/browse")
def browse():
    db = get_db()
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()

    query = """
        SELECT listings.*, users.username
        FROM listings
        JOIN users ON listings.user_id = users.id
        WHERE 1=1
    """
    params = []

    if q:
        query += " AND (listings.title LIKE ? OR listings.description LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%"])
    if category:
        query += " AND listings.category = ?"
        params.append(category)

    query += " ORDER BY listings.created_at DESC"

    listings = db.execute(query, params).fetchall()
    return render_template("browse.html", listings=listings, q=q, category=category)


@app.route("/listing/<int:listing_id>")
def listing(listing_id):
    db = get_db()
    listing = db.execute("""
        SELECT listings.*, users.username, users.bio
        FROM listings
        JOIN users ON listings.user_id = users.id
        WHERE listings.id = ?
    """, (listing_id,)).fetchone()

    if listing is None:
        flash("Listing not found.", "error")
        return redirect(url_for("browse"))

    return render_template("listing.html", listing=listing)


@app.route("/create", methods=["GET", "POST"])
def create():
    if not g.user:
        flash("You must be logged in to create a listing.", "error")
        return redirect(url_for("login"))

    if request.method == "POST":
        title = request.form["title"].strip()
        description = request.form["description"].strip()
        category = request.form["category"]
        looking_for = request.form.get("looking_for", "").strip()

        if not title or not description or not category:
            flash("Title, description, and category are required.", "error")
        else:
            image_filename = None
            if "image" in request.files:
                file = request.files["image"]
                if file and file.filename:
                    filename = secure_filename(file.filename)
                    # Make filename unique
                    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                    image_filename = f"{timestamp}_{filename}"
                    file.save(os.path.join(app.config["UPLOAD_FOLDER"], image_filename))

            db = get_db()
            db.execute(
                """INSERT INTO listings (user_id, title, description, category, looking_for, image)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (g.user["id"], title, description, category, looking_for, image_filename),
            )
            db.commit()
            flash("Listing created!", "success")
            return redirect(url_for("browse"))

    return render_template("create.html")


@app.route("/edit/<int:listing_id>", methods=["GET", "POST"])
def edit(listing_id):
    if not g.user:
        flash("You must be logged in.", "error")
        return redirect(url_for("login"))

    db = get_db()
    listing = db.execute("SELECT * FROM listings WHERE id = ?", (listing_id,)).fetchone()

    if listing is None or listing["user_id"] != g.user["id"]:
        flash("You cannot edit this listing.", "error")
        return redirect(url_for("browse"))

    if request.method == "POST":
        title = request.form["title"].strip()
        description = request.form["description"].strip()
        category = request.form["category"]
        looking_for = request.form.get("looking_for", "").strip()

        image_filename = listing["image"]
        if "image" in request.files:
            file = request.files["image"]
            if file and file.filename:
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                image_filename = f"{timestamp}_{filename}"
                file.save(os.path.join(app.config["UPLOAD_FOLDER"], image_filename))

        db.execute(
            """UPDATE listings
               SET title = ?, description = ?, category = ?, looking_for = ?, image = ?
               WHERE id = ?""",
            (title, description, category, looking_for, image_filename, listing_id),
        )
        db.commit()
        flash("Listing updated!", "success")
        return redirect(url_for("listing", listing_id=listing_id))

    return render_template("edit.html", listing=listing)


@app.route("/profile/<username>")
def profile(username):
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

    if user is None:
        flash("User not found.", "error")
        return redirect(url_for("browse"))

    listings = db.execute(
        "SELECT * FROM listings WHERE user_id = ? ORDER BY created_at DESC",
        (user["id"],),
    ).fetchall()

    return render_template("profile.html", user=user, listings=listings)


# ---------- Run ----------
__name__ == "__main__":
init_db()
port = int(os.environ.get("port", 5000))
app.run(host="0.0.0.0", port=port)

