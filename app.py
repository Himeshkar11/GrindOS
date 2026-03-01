import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# ---------------- APP SETUP ----------------
app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///users.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = "dev-secret-key"   # OK for demo / hackathon

db = SQLAlchemy(app)

# ---------------- DATABASE MODELS ----------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

    # RPG STATS
    level = db.Column(db.Integer, default=1)
    xp = db.Column(db.Integer, default=0)


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(200), nullable=False)
    done = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


# ---------------- GAME CONFIG ----------------
XP_PER_TASK = 50

def xp_required(level):
    return level * 200


# ---------------- PAGE ROUTES ----------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login", methods=["GET"])
def login_page():
    return render_template("login.html")

@app.route("/signup", methods=["GET"])
def signup_page():
    return render_template("signup.html")


# ---------------- AUTH ROUTES ----------------
@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"message": "All fields are required"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"message": "User already exists"}), 400

    user = User(
        email=email,
        password=generate_password_hash(password),
        level=1,
        xp=0
    )

    db.session.add(user)
    db.session.commit()

    return jsonify({"message": "Registration successful"})


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    user = User.query.filter_by(email=email).first()

    if user and check_password_hash(user.password, password):
        session["user_id"] = user.id
        return jsonify({"message": "Login successful", "redirect": "/dashboard"})

    return jsonify({"message": "Invalid email or password"}), 401


# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login_page"))

    user = db.session.get(User, session["user_id"])
    return render_template("dashboard.html", user=user)


# ---------------- TASK APIs ----------------
@app.route("/api/tasks", methods=["GET"])
def get_tasks():
    if "user_id" not in session:
        return jsonify([])

    tasks = Task.query.filter_by(user_id=session["user_id"]).all()

    return jsonify([
        {"id": t.id, "text": t.text, "done": t.done}
        for t in tasks
    ])


@app.route("/api/tasks", methods=["POST"])
def add_task():
    if "user_id" not in session:
        return jsonify({"message": "Unauthorized"}), 401

    data = request.get_json()
    text = data.get("text")

    if not text:
        return jsonify({"message": "Task text required"}), 400

    task = Task(text=text, user_id=session["user_id"])
    db.session.add(task)
    db.session.commit()

    return jsonify({"message": "Task added"})


@app.route("/api/tasks/<int:task_id>", methods=["PATCH"])
def toggle_task(task_id):
    if "user_id" not in session:
        return jsonify({"message": "Unauthorized"}), 401

    user = db.session.get(User, session["user_id"])
    task = db.session.get(Task, task_id)

    if not task or task.user_id != user.id:
        return jsonify({"message": "Task not found"}), 404

    # Toggle task
    task.done = not task.done

    # XP logic (only on completion, not undo)
    if task.done:
        user.xp += XP_PER_TASK

        while user.xp >= xp_required(user.level):
            user.xp -= xp_required(user.level)
            user.level += 1

    db.session.commit()

    return jsonify({
        "message": "Task updated",
        "level": user.level,
        "xp": user.xp,
        "xp_required": xp_required(user.level)
    })


# ---------------- USER STATS API ----------------
@app.route("/api/user-stats")
def user_stats():
    if "user_id" not in session:
        return jsonify({"message": "Unauthorized"}), 401

    user = db.session.get(User, session["user_id"])

    return jsonify({
        "level": user.level,
        "xp": user.xp,
        "xp_required": xp_required(user.level)
    })


# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("login_page"))


# ---------------- RUN SERVER (🔥 RAILWAY FIX) ----------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)