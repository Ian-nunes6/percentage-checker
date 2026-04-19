from functools import wraps
import csv
import io
import sqlite3

from flask import Flask, Response, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.secret_key = "secret123"
app.config["SESSION_COOKIE_HTTPONLY"] = True

DB_PATH = "users.db"
DEV_PASSWORD = "Ian123"
WIPE_KEY = "ian123"


# -------------------- DB SETUP --------------------
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS users (username TEXT NOT NULL, score REAL NOT NULL)"
        )
        conn.commit()


# Reuse one helper so every route opens the database the same way.
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# Keep route protection in one place so redirects stay consistent.
def login_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    return wrapped_view


init_db()


# -------------------- ENTRY --------------------
@app.route("/")
def root():
    # Always start the app from the login page.
    return redirect(url_for("login"))


# -------------------- HOME --------------------
@app.route("/home", methods=["GET", "POST"])
@login_required
def home():
    result = ""
    error = ""
    color = ""
    percentage_value = ""
    developer_error = ""

    if request.method == "POST":
        percentage_value = request.form.get("percentage", "").strip()

        if not percentage_value:
            error = "Please enter a percentage."
            color = "red"
        else:
            try:
                percentage = float(percentage_value)
            except ValueError:
                error = "Invalid input. Please enter a valid number."
                color = "red"
            else:
                if percentage < 0 or percentage > 100:
                    error = "Enter a valid percentage (0-100)."
                    color = "red"
                else:
                    with get_db_connection() as conn:
                        conn.execute(
                            "INSERT INTO users (username, score) VALUES (?, ?)",
                            (session["user"], percentage),
                        )
                        conn.commit()

                    if percentage <= 55:
                        result = "One exam can't measure your full potential."
                        color = "red"
                    elif percentage <= 75:
                        result = "Good marks are proof you can do even more."
                        color = "yellow"
                    elif percentage < 95:
                        result = "Education is the key to success."
                        color = "green"
                    else:
                        result = "LEGEND! 95+"
                        color = "gold"

    if "developer_error" in session:
        developer_error = session.pop("developer_error")

    return render_template(
        "index.html",
        result=result,
        error=error,
        color=color,
        percentage_value=percentage_value,
        username=session.get("user", ""),
        developer_unlocked=session.get("developer_access", False),
        developer_error=developer_error,
    )


# -------------------- LOGIN --------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""

    if request.method == "POST":
        username = request.form.get("username", "").strip()

        if not username:
            error = "Username is required."
        else:
            session.clear()
            session["user"] = username
            session["developer_access"] = False
            return redirect(url_for("home"))

    return render_template("login.html", error=error)


# -------------------- DEVELOPER PANEL LOCK --------------------
@app.route("/developer-login", methods=["POST"])
@login_required
def developer_login():
    password = request.form.get("developer_password", "").strip()

    if password == DEV_PASSWORD:
        session["developer_access"] = True
    else:
        session["developer_error"] = "Wrong developer password."

    return redirect(url_for("home"))


# -------------------- LOGOUT --------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# -------------------- LEADERBOARD --------------------
@app.route("/leaderboard")
@login_required
def leaderboard():
    with get_db_connection() as conn:
        data = conn.execute(
            """
            SELECT username, MAX(score) AS best_score
            FROM users
            GROUP BY username
            ORDER BY best_score DESC
            LIMIT 10
            """
        ).fetchall()

    return render_template("leaderboard.html", data=data)


# -------------------- CSV EXPORT --------------------
@app.route("/export")
@login_required
def export():
    if not session.get("developer_access"):
        return redirect(url_for("home"))

    with get_db_connection() as conn:
        data = conn.execute(
            "SELECT username, score FROM users ORDER BY username, score DESC"
        ).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["username", "score"])
    for row in data:
        writer.writerow([row["username"], row["score"]])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=data.csv"},
    )


# -------------------- DEV WIPE (SECRET) --------------------
@app.route("/wipe")
@login_required
def wipe():
    if not session.get("developer_access"):
        return redirect(url_for("home"))

    key = request.args.get("key", "").strip()

    if key == WIPE_KEY:
        with get_db_connection() as conn:
            conn.execute("DELETE FROM users")
            conn.commit()
        return "Database wiped."

    return "Access denied"


# -------------------- RUN --------------------
if __name__ == "__main__":
    app.run(debug=True)
