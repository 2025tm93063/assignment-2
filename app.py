import os
import sqlite3
from datetime import datetime, date
from flask import Flask, request, jsonify, render_template_string, redirect, url_for, session

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "aceest-secret-2026")

DB_PATH = os.environ.get("DB_PATH", "aceest_fitness.db")

APP_VERSION = "3.2.4"

PROGRAMS = {
    "Fat Loss (FL)": {
        "factor": 22,
        "workout": "Mon: Back Squat 5x5\nTue: EMOM Assault Bike 20min\nWed: Bench Press + 21-15-9\nThu: Deadlift + Box Jumps\nFri: Zone 2 Cardio 30min",
        "diet": "Breakfast: Egg Whites + Oats\nLunch: Grilled Chicken + Brown Rice\nDinner: Fish Curry + Millet Roti\nTarget: ~2000 kcal",
    },
    "Muscle Gain (MG)": {
        "factor": 35,
        "workout": "Mon: Squat 5x5\nTue: Bench 5x5\nWed: Deadlift 4x6\nThu: Front Squat 4x8\nFri: Incline Press 4x10\nSat: Barbell Rows 4x10",
        "diet": "Breakfast: Eggs + Peanut Butter Oats\nLunch: Chicken Biryani\nDinner: Mutton Curry + Rice\nTarget: ~3200 kcal",
    },
    "Beginner (BG)": {
        "factor": 26,
        "workout": "Full Body Circuit: Air Squats, Ring Rows, Push-ups\nFocus: Technique & Consistency",
        "diet": "Balanced Meals: Idli/Dosa/Rice + Dal\nProtein Target: 120g/day",
    },
}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            age INTEGER,
            height REAL,
            weight REAL,
            program TEXT,
            calories INTEGER,
            target_weight REAL,
            target_adherence INTEGER,
            membership_status TEXT DEFAULT 'Active',
            membership_end TEXT
        );
        CREATE TABLE IF NOT EXISTS progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT,
            week TEXT,
            adherence INTEGER
        );
        CREATE TABLE IF NOT EXISTS workouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT,
            date TEXT,
            workout_type TEXT,
            duration_min INTEGER,
            notes TEXT
        );
    """)
    cur.execute("SELECT username FROM users WHERE username='admin'")
    if not cur.fetchone():
        cur.execute("INSERT INTO users VALUES ('admin','admin123','Admin')")
    conn.commit()
    conn.close()


# ── health ──────────────────────────────────────────────────────────────────

@app.route("/health")
def health():
    return jsonify({"status": "ok", "version": APP_VERSION}), 200


@app.route("/version")
def version():
    return jsonify({"version": APP_VERSION}), 200


# ── auth ─────────────────────────────────────────────────────────────────────

@app.route("/", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        conn = get_db()
        row = conn.execute(
            "SELECT role FROM users WHERE username=? AND password=?", (username, password)
        ).fetchone()
        conn.close()
        if row:
            session["user"] = username
            session["role"] = row["role"]
            return redirect(url_for("dashboard"))
        error = "Invalid credentials"
    return render_template_string(LOGIN_HTML, error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ── dashboard ────────────────────────────────────────────────────────────────

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    conn = get_db()
    clients = conn.execute("SELECT name FROM clients ORDER BY name").fetchall()
    conn.close()
    return render_template_string(DASHBOARD_HTML, clients=clients, user=session["user"], role=session["role"])


# ── clients API ──────────────────────────────────────────────────────────────

@app.route("/clients", methods=["GET"])
def list_clients():
    conn = get_db()
    rows = conn.execute("SELECT * FROM clients ORDER BY name").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows]), 200


@app.route("/clients", methods=["POST"])
def add_client():
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name required"}), 400
    program = data.get("program", "")
    weight = float(data.get("weight", 0) or 0)
    age = int(data.get("age", 0) or 0)
    height = float(data.get("height", 0) or 0)
    calories = int(weight * PROGRAMS.get(program, {}).get("factor", 0)) if program and weight else 0
    try:
        conn = get_db()
        conn.execute(
            "INSERT INTO clients (name, age, height, weight, program, calories, membership_status) VALUES (?,?,?,?,?,?,'Active')",
            (name, age, height, weight, program, calories),
        )
        conn.commit()
        conn.close()
        return jsonify({"message": "client added", "name": name}), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": "client already exists"}), 409


@app.route("/clients/<name>", methods=["GET"])
def get_client(name):
    conn = get_db()
    row = conn.execute("SELECT * FROM clients WHERE name=?", (name,)).fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "not found"}), 404
    return jsonify(dict(row)), 200


@app.route("/clients/<name>", methods=["DELETE"])
def delete_client(name):
    conn = get_db()
    conn.execute("DELETE FROM clients WHERE name=?", (name,))
    conn.commit()
    conn.close()
    return jsonify({"message": "deleted"}), 200


# ── progress API ─────────────────────────────────────────────────────────────

@app.route("/clients/<name>/progress", methods=["GET"])
def get_progress(name):
    conn = get_db()
    rows = conn.execute(
        "SELECT week, adherence FROM progress WHERE client_name=? ORDER BY id", (name,)
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows]), 200


@app.route("/clients/<name>/progress", methods=["POST"])
def add_progress(name):
    data = request.get_json(force=True)
    adherence = int(data.get("adherence", 0))
    week = data.get("week") or datetime.now().strftime("Week %U - %Y")
    conn = get_db()
    conn.execute(
        "INSERT INTO progress (client_name, week, adherence) VALUES (?,?,?)", (name, week, adherence)
    )
    conn.commit()
    conn.close()
    return jsonify({"message": "progress saved"}), 201


# ── workouts API ─────────────────────────────────────────────────────────────

@app.route("/clients/<name>/workouts", methods=["GET"])
def get_workouts(name):
    conn = get_db()
    rows = conn.execute(
        "SELECT date, workout_type, duration_min, notes FROM workouts WHERE client_name=? ORDER BY date DESC",
        (name,),
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows]), 200


@app.route("/clients/<name>/workouts", methods=["POST"])
def add_workout(name):
    data = request.get_json(force=True)
    conn = get_db()
    conn.execute(
        "INSERT INTO workouts (client_name, date, workout_type, duration_min, notes) VALUES (?,?,?,?,?)",
        (name, data.get("date", date.today().isoformat()), data.get("workout_type", ""), int(data.get("duration_min", 0)), data.get("notes", "")),
    )
    conn.commit()
    conn.close()
    return jsonify({"message": "workout saved"}), 201


# ── programs reference ────────────────────────────────────────────────────────

@app.route("/programs", methods=["GET"])
def list_programs():
    return jsonify({k: {"factor": v["factor"]} for k, v in PROGRAMS.items()}), 200


@app.route("/programs/<name>", methods=["GET"])
def get_program(name):
    prog = PROGRAMS.get(name)
    if not prog:
        return jsonify({"error": "program not found"}), 404
    return jsonify(prog), 200


# ── minimal HTML templates ────────────────────────────────────────────────────

LOGIN_HTML = """
<!DOCTYPE html><html><head><title>ACEest Login</title>
<style>body{font-family:Arial;background:#1a1a1a;color:white;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;}
form{background:#333;padding:40px;border-radius:8px;min-width:300px;}
h2{color:#d4af37;text-align:center;}input{width:100%;padding:8px;margin:8px 0;background:#555;border:none;color:white;border-radius:4px;}
button{width:100%;padding:10px;background:#d4af37;color:black;font-weight:bold;border:none;border-radius:4px;cursor:pointer;}
.err{color:#e74c3c;text-align:center;}</style></head>
<body><form method="POST"><h2>ACEest Fitness</h2>
{% if error %}<p class="err">{{ error }}</p>{% endif %}
<input name="username" placeholder="Username" required>
<input name="password" type="password" placeholder="Password" required>
<button type="submit">Login</button></form></body></html>
"""

DASHBOARD_HTML = """
<!DOCTYPE html><html><head><title>ACEest Dashboard</title>
<style>body{font-family:Arial;background:#1a1a1a;color:white;margin:0;}
header{background:#d4af37;color:black;padding:16px 24px;font-size:20px;font-weight:bold;display:flex;justify-content:space-between;}
.container{padding:24px;}.card{background:#333;border-radius:8px;padding:20px;margin-bottom:16px;}
h3{color:#d4af37;}a{color:#d4af37;}ul{list-style:none;padding:0;}li{padding:4px 0;}</style></head>
<body>
<header><span>ACEest Dashboard — {{ role }}</span><a href="/logout" style="color:black;">Logout ({{ user }})</a></header>
<div class="container">
  <div class="card"><h3>Clients</h3>
    <ul>{% for c in clients %}<li><a href="/clients/{{ c.name }}">{{ c.name }}</a></li>{% else %}<li>No clients yet.</li>{% endfor %}</ul>
  </div>
  <div class="card"><h3>API Endpoints</h3>
    <ul>
      <li>GET /health — health check</li>
      <li>GET /clients — list all clients</li>
      <li>POST /clients — add client (JSON)</li>
      <li>GET /clients/&lt;name&gt; — client detail</li>
      <li>GET /programs — list programs</li>
      <li>GET /version — app version</li>
    </ul>
  </div>
</div></body></html>
"""

# ── bootstrap ─────────────────────────────────────────────────────────────────

init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081, debug=False)
