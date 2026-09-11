from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = "skilling_outcomes_secret"
DATABASE = "skilling.db"


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def now():
    return datetime.now().strftime("%Y-%m-%d")


def init_db():
    conn = get_db()
    cur = conn.cursor()

    def ensure_column(table, column, definition):
        """Add a column when an older skilling.db does not have it."""
        columns = [r[1] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()]
        if column not in columns:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS trainees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trainee_code TEXT UNIQUE,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            district TEXT,
            education TEXT,
            course TEXT,
            skills TEXT DEFAULT '',
            training_center_id INTEGER,
            provider TEXT,
            attendance REAL DEFAULT 0,
            assessment REAL DEFAULT 0,
            certification TEXT DEFAULT 'Not Certified',
            status TEXT DEFAULT 'Training Completed',
            created_at TEXT,
            FOREIGN KEY(training_center_id) REFERENCES training_centers(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS training_centers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            center_code TEXT UNIQUE,
            center_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            address TEXT,
            district TEXT,
            courses TEXT,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS employers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employer_code TEXT UNIQUE,
            company TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            industry TEXT,
            location TEXT,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            trainee_id INTEGER,
            employer_id INTEGER,
            training_center_id INTEGER,
            created_at TEXT,
            FOREIGN KEY (trainee_id) REFERENCES trainees(id),
            FOREIGN KEY (employer_id) REFERENCES employers(id),
            FOREIGN KEY (training_center_id) REFERENCES training_centers(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS training_programs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            training_center_id INTEGER,
            name TEXT NOT NULL,
            provider TEXT,
            duration TEXT,
            seats INTEGER DEFAULT 0,
            skills TEXT,
            eligibility TEXT,
            start_date TEXT,
            status TEXT DEFAULT 'Open',
            enrolled INTEGER DEFAULT 0,
            created_at TEXT,
            FOREIGN KEY(training_center_id) REFERENCES training_centers(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employer_id INTEGER,
            title TEXT NOT NULL,
            skills TEXT,
            location TEXT,
            salary TEXT,
            created_at TEXT,
            FOREIGN KEY(employer_id) REFERENCES employers(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS outcomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trainee_id INTEGER,
            outcome_type TEXT,
            employer TEXT,
            job_role TEXT,
            salary REAL,
            location TEXT,
            joining_date TEXT,
            retention_months INTEGER DEFAULT 0,
            training_relevance INTEGER DEFAULT 0,
            verified TEXT DEFAULT 'Pending',
            FOREIGN KEY(trainee_id) REFERENCES trainees(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS followups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trainee_id INTEGER,
            followup_period TEXT,
            employment_status TEXT,
            salary REAL,
            job_role TEXT,
            difficulties TEXT,
            remarks TEXT,
            followup_date TEXT,
            FOREIGN KEY(trainee_id) REFERENCES trainees(id)
        )
    """)

    # ---------------------------------------------------------
    # Migrate databases created by older versions of the app.
    # CREATE TABLE IF NOT EXISTS does not add new columns to an
    # existing SQLite table, so explicitly add every column used
    # by the current role-based registration/recommendation code.
    # ---------------------------------------------------------
    migrations = {
        "trainees": {
            "trainee_code": "TEXT",
            "skills": "TEXT DEFAULT ''",
            "training_center_id": "INTEGER",
        },
        "training_centers": {
            "center_code": "TEXT",
            "center_name": "TEXT",
            "email": "TEXT",
            "phone": "TEXT",
            "address": "TEXT",
            "district": "TEXT",
            "courses": "TEXT",
            "created_at": "TEXT",
        },
        "employers": {
            "employer_code": "TEXT",
            "company": "TEXT",
            "email": "TEXT",
            "phone": "TEXT",
            "industry": "TEXT",
            "location": "TEXT",
            "created_at": "TEXT",
        },
        "users": {
            "trainee_id": "INTEGER",
            "employer_id": "INTEGER",
            "training_center_id": "INTEGER",
            "created_at": "TEXT",
        },
        "training_programs": {
            "training_center_id": "INTEGER",
            "provider": "TEXT",
            "duration": "TEXT",
            "seats": "INTEGER DEFAULT 0",
            "skills": "TEXT",
            "eligibility": "TEXT",
            "start_date": "TEXT",
            "status": "TEXT DEFAULT 'Open'",
            "enrolled": "INTEGER DEFAULT 0",
            "created_at": "TEXT",
        },
        "jobs": {
            "employer_id": "INTEGER",
            "title": "TEXT",
            "skills": "TEXT",
            "location": "TEXT",
            "salary": "TEXT",
            "created_at": "TEXT",
        },
        "outcomes": {
            "outcome_type": "TEXT",
            "employer": "TEXT",
            "job_role": "TEXT",
            "salary": "REAL",
            "location": "TEXT",
            "joining_date": "TEXT",
            "retention_months": "INTEGER DEFAULT 0",
            "training_relevance": "INTEGER DEFAULT 0",
            "verified": "TEXT DEFAULT 'Pending'",
        },
        "followups": {
            "followup_period": "TEXT",
            "employment_status": "TEXT",
            "salary": "REAL",
            "job_role": "TEXT",
            "difficulties": "TEXT",
            "remarks": "TEXT",
            "followup_date": "TEXT",
        },
    }

    for table, columns in migrations.items():
        for column, definition in columns.items():
            ensure_column(table, column, definition)

    # Demo/admin accounts. Employer and training accounts created by admin
    # are linked to their own organization and receive their own ID.
    defaults = [
        ("admin@skilling.local", "admin123", "admin", None, None, None)
    ]
    for email, password, role, trainee_id, employer_id, center_id in defaults:
        if cur.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone() is None:
            cur.execute("""
                INSERT INTO users(email,password,role,trainee_id,employer_id,training_center_id,created_at)
                VALUES (?,?,?,?,?,?,?)
            """, (email, password, role, trainee_id, employer_id, center_id, now()))

    # Add a few demo organizations only if none exist.
    if cur.execute("SELECT COUNT(*) FROM training_centers").fetchone()[0] == 0:
        cur.execute("""
            INSERT INTO training_centers
            (center_code,center_name,email,phone,address,district,courses,created_at)
            VALUES (?,?,?,?,?,?,?,?)
        """, ("TRN-0001", "SkillTech Academy", "center1@skilling.local",
              "9000000001", "Chennai", "Chennai",
              "Python & Data Analytics, Excel, Power BI", now()))
        center_id = cur.lastrowid
        cur.execute("""
            INSERT INTO users(email,password,role,training_center_id,created_at)
            VALUES (?,?,?,?,?)
        """, ("center1@skilling.local", "center123", "training", center_id, now()))

    if cur.execute("SELECT COUNT(*) FROM employers").fetchone()[0] == 0:
        cur.execute("""
            INSERT INTO employers
            (employer_code,company,email,phone,industry,location,created_at)
            VALUES (?,?,?,?,?,?,?)
        """, ("EMP-0001", "TechNova Solutions", "employer1@skilling.local",
              "9000000011", "IT Services", "Chennai", now()))
        employer_id = cur.lastrowid
        cur.execute("""
            INSERT INTO users(email,password,role,employer_id,created_at)
            VALUES (?,?,?,?,?)
        """, ("employer1@skilling.local", "employer123", "employer", employer_id, now()))

    # Demo programs are owned by the first training center.
    center = cur.execute("SELECT id FROM training_centers ORDER BY id LIMIT 1").fetchone()
    if center and cur.execute("SELECT COUNT(*) FROM training_programs").fetchone()[0] == 0:
        cur.executemany("""
            INSERT INTO training_programs
            (training_center_id,name,provider,duration,seats,skills,eligibility,start_date,status,enrolled,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, [
            (center["id"], "Python & Data Analytics", "SkillTech Academy", "8 Weeks", 30,
             "Python, Excel, SQL, Power BI", "UG / Diploma", "2026-09-15", "Open", 0, now()),
            (center["id"], "Full Stack Development", "SkillTech Academy", "12 Weeks", 25,
             "HTML, CSS, JavaScript, Java, SQL", "UG / Diploma", "2026-09-20", "Upcoming", 0, now()),
            (center["id"], "IoT Data Analytics", "SkillTech Academy", "10 Weeks", 20,
             "Python, IoT, Sensors, SQL, Power BI", "UG / Diploma", "2026-09-25", "Open", 0, now()),
            (center["id"], "Digital Marketing", "SkillTech Academy", "6 Weeks", 25,
             "SEO, Social Media, Content Marketing, Analytics", "UG / Diploma", "2026-10-01", "Upcoming", 0, now()),
        ])

    conn.commit()
    conn.close()


def next_code(prefix, table, column):
    conn = get_db()
    row = conn.execute(f"SELECT {column} FROM {table} WHERE {column} LIKE ? ORDER BY id DESC LIMIT 1",
                       (prefix + "-%",)).fetchone()
    conn.close()
    if not row or not row[column]:
        return f"{prefix}-0001"
    try:
        n = int(row[column].split("-")[-1]) + 1
    except ValueError:
        n = 1
    return f"{prefix}-{n:04d}"



def normalize_skills(text):
    """Convert a comma/semicolon separated skill string into comparable tokens."""
    if not text:
        return []
    cleaned = text.replace(";", ",").replace("/", ",")
    return sorted({part.strip().lower() for part in cleaned.split(",") if part.strip()})


def skill_gap_recommendations(trainee, programs, jobs=None):
    """Rule-based, explainable skill-gap analysis for the prototype.

    The trainee's current skills are compared with skills listed for each program.
    A program gets a higher score when it covers more missing skills. Job skills are
    also used as demand context when available, without hiding the simple reason.
    """
    current = set(normalize_skills(trainee["skills"] if "skills" in trainee.keys() else ""))
    if not current:
        # Course is used only as a fallback signal when the trainee has not entered skills.
        course = (trainee["course"] or "").lower()
        fallback = []
        if "data" in course or "analytics" in course:
            fallback = ["python", "excel"]
        elif "full stack" in course or "web" in course:
            fallback = ["html", "css", "javascript"]
        elif "iot" in course or "embedded" in course:
            fallback = ["iot", "sensors"]
        current.update(fallback)

    demand = set()
    for job in jobs or []:
        demand.update(normalize_skills(job["skills"] if "skills" in job.keys() else ""))

    results = []
    for program in programs:
        required = set(normalize_skills(program["skills"] or ""))
        if not required:
            continue
        matched = sorted(required & current)
        missing = sorted(required - current)
        demand_missing = sorted(set(missing) & demand)
        match_pct = round((len(matched) / len(required)) * 100)
        gap_pct = round((len(missing) / len(required)) * 100)
        # Keep recommendations relevant to the trainee's existing direction.
        # Existing-skill overlap is the main signal; course/domain similarity and
        # employer demand are secondary signals.
        course_text = (trainee["course"] or "").lower()
        program_text = (program["name"] or "").lower()
        domain_words = [
            "data", "analytics", "python", "full stack", "web", "java",
            "iot", "embedded", "digital marketing", "marketing"
        ]
        domain_bonus = 15 if any(w in course_text and w in program_text for w in domain_words) else 0
        demand_bonus = (len(demand_missing) / len(missing) * 15) if missing else 0
        score = round(min(100, (match_pct * 0.65) + (gap_pct * 0.20) + domain_bonus + demand_bonus))
        reason = (
            f"Matches {len(matched)} existing skill(s) and covers {len(missing)} missing skill(s): {', '.join(missing)}."
            if missing else
            "Most listed skills are already present; consider an advanced course or another skill area."
        )
        if demand_missing:
            reason += f" Employer demand also includes: {', '.join(demand_missing)}."
        results.append({
            "program": program,
            "matched": matched,
            "missing": missing,
            "match_pct": match_pct,
            "gap_pct": gap_pct,
            "score": score,
            "reason": reason
        })

    results.sort(key=lambda x: (x["score"], len(x["missing"]), x["match_pct"]), reverse=True)
    return results


def login_required(role=None):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login"))
            if role and session.get("role") != role:
                flash("You do not have access to this page.", "error")
                return redirect(url_for("role_dashboard"))
            return fn(*args, **kwargs)
        return wrapper
    return decorator


@app.context_processor
def inject_user():
    return {
        "current_email": session.get("email", ""),
        "current_role": session.get("role", ""),
        "current_org_code": session.get("org_code", "")
    }


@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("role_dashboard"))
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    conn = get_db()
    centers = conn.execute("SELECT * FROM training_centers ORDER BY center_name").fetchall()
    employers = conn.execute("SELECT * FROM employers ORDER BY company").fetchall()
    conn.close()

    if request.method == "POST":
        account_type = request.form.get("account_type", "trainee").strip().lower()
        email_field = {"trainee": "trainee_email", "training": "training_email", "employer": "employer_email"}.get(account_type, "trainee_email")
        email = request.form.get(email_field, "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not email or not password or password != confirm:
            flash("Please enter a valid email and matching passwords.", "error")
            return render_template("register.html", centers=centers, employers=employers)

        conn = get_db()
        try:
            cur = conn.cursor()
            if cur.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone():
                flash("An account with this email already exists. Please login.", "error")
                return render_template("register.html", centers=centers, employers=employers)

            if account_type == "trainee":
                name = request.form.get("name", "").strip()
                if not name:
                    flash("Trainee name is required.", "error")
                    return render_template("register.html", centers=centers, employers=employers)

                center_code = request.form.get("training_center_code", "").strip().upper()
                center = cur.execute(
                    "SELECT * FROM training_centers WHERE center_code=?",
                    (center_code,)
                ).fetchone() if center_code else None

                if not center:
                    flash("Enter a valid Training Center ID, for example TRN-0001.", "error")
                    return render_template("register.html", centers=centers, employers=employers)

                last = cur.execute("SELECT id FROM trainees ORDER BY id DESC LIMIT 1").fetchone()
                trainee_code = f"TRR-{(last['id'] + 1 if last else 1):04d}"

                cur.execute("""
                    INSERT INTO trainees
                    (trainee_code,name,email,phone,district,education,course,skills,training_center_id,
                     provider,created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    trainee_code, name, email,
                    request.form.get("phone", "").strip(),
                    request.form.get("district", "").strip(),
                    request.form.get("education", "").strip(),
                    request.form.get("course", "").strip(),
                    request.form.get("skills", "").strip(),
                    center["id"], center["center_name"], now()
                ))
                trainee_id = cur.lastrowid

                cur.execute("""
                    INSERT INTO users(email,password,role,trainee_id,created_at)
                    VALUES (?,?,?,?,?)
                """, (email, password, "trainee", trainee_id, now()))

                conn.commit()
                flash(
                    f"Trainee registration successful. Trainee ID: {trainee_code}. "
                    f"Training Center: {center['center_code']}.",
                    "success"
                )
                return redirect(url_for("login"))

            elif account_type == "training":
                center_code = request.form.get("training_center_code", "").strip().upper()
                center = cur.execute(
                    "SELECT * FROM training_centers WHERE center_code=?",
                    (center_code,)
                ).fetchone()

                if not center:
                    flash("Enter a valid Training Center ID.", "error")
                    return render_template("register.html", centers=centers, employers=employers)

                # The center ID must belong to the center's existing email.
                # This creates the account for that exact center, not a new center.
                if center["email"].lower() != email:
                    flash(
                        "For a Training Center account, use the email already registered "
                        "for that Training Center ID. Admin creates new centers.",
                        "error"
                    )
                    return render_template("register.html", centers=centers, employers=employers)

                existing = cur.execute(
                    "SELECT id FROM users WHERE training_center_id=?",
                    (center["id"],)
                ).fetchone()
                if existing:
                    flash("This Training Center already has a login account. Please login.", "error")
                    return render_template("register.html", centers=centers, employers=employers)

                cur.execute("""
                    INSERT INTO users(email,password,role,training_center_id,created_at)
                    VALUES (?,?,?,?,?)
                """, (email, password, "training", center["id"], now()))
                conn.commit()
                flash(f"Training Center account registered for {center['center_code']}.", "success")
                return redirect(url_for("login"))

            elif account_type == "employer":
                employer_code = request.form.get("employer_code", "").strip().upper()
                employer = cur.execute(
                    "SELECT * FROM employers WHERE employer_code=?",
                    (employer_code,)
                ).fetchone()

                if not employer:
                    flash("Enter a valid Employer ID.", "error")
                    return render_template("register.html", centers=centers, employers=employers)

                if employer["email"].lower() != email:
                    flash(
                        "For an Employer account, use the email already registered "
                        "for that Employer ID. Admin creates new employer platforms.",
                        "error"
                    )
                    return render_template("register.html", centers=centers, employers=employers)

                existing = cur.execute(
                    "SELECT id FROM users WHERE employer_id=?",
                    (employer["id"],)
                ).fetchone()
                if existing:
                    flash("This Employer Platform already has a login account. Please login.", "error")
                    return render_template("register.html", centers=centers, employers=employers)

                cur.execute("""
                    INSERT INTO users(email,password,role,employer_id,created_at)
                    VALUES (?,?,?,?,?)
                """, (email, password, "employer", employer["id"], now()))
                conn.commit()
                flash(f"Employer account registered for {employer['employer_code']}.", "success")
                return redirect(url_for("login"))

            else:
                flash("Invalid account type.", "error")
                return render_template("register.html", centers=centers, employers=employers)

        except sqlite3.IntegrityError:
            conn.rollback()
            flash("This email or ID is already registered.", "error")
            return render_template("register.html", centers=centers, employers=employers)
        finally:
            conn.close()

    return render_template("register.html", centers=centers, employers=employers)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE email=? AND password=?", (email, password)
        ).fetchone()

        if user:
            session.clear()
            session["user_id"] = user["id"]
            session["email"] = user["email"]
            session["role"] = user["role"]
            session["trainee_id"] = user["trainee_id"]
            session["employer_id"] = user["employer_id"]
            session["training_center_id"] = user["training_center_id"]

            if user["role"] == "employer":
                org = conn.execute("SELECT employer_code FROM employers WHERE id=?",
                                   (user["employer_id"],)).fetchone()
                session["org_code"] = org["employer_code"] if org else ""
            elif user["role"] == "training":
                org = conn.execute("SELECT center_code FROM training_centers WHERE id=?",
                                   (user["training_center_id"],)).fetchone()
                session["org_code"] = org["center_code"] if org else ""
            elif user["role"] == "trainee":
                tr = conn.execute("SELECT trainee_code FROM trainees WHERE id=?",
                                  (user["trainee_id"],)).fetchone()
                session["org_code"] = tr["trainee_code"] if tr else "Trainee"

            conn.close()
            return redirect(url_for("role_dashboard"))

        conn.close()
        flash("Invalid email or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/dashboard")
@login_required()
def role_dashboard():
    role = session.get("role")
    if role == "trainee":
        return redirect(url_for("trainee_dashboard"))
    if role == "employer":
        return redirect(url_for("employer_dashboard"))
    if role == "training":
        return redirect(url_for("training_dashboard"))
    return redirect(url_for("admin_dashboard"))


@app.route("/trainee/dashboard")
@login_required("trainee")
def trainee_dashboard():
    conn = get_db()
    trainee = conn.execute("""
        SELECT trainees.*, training_centers.center_code, training_centers.center_name
        FROM trainees
        LEFT JOIN training_centers ON trainees.training_center_id=training_centers.id
        WHERE trainees.id=?
    """, (session["trainee_id"],)).fetchone()
    programs = conn.execute("""
        SELECT training_programs.*, training_centers.center_code, training_centers.center_name
        FROM training_programs
        LEFT JOIN training_centers ON training_programs.training_center_id=training_centers.id
        WHERE training_programs.status IN ('Open','Upcoming')
        ORDER BY training_programs.id DESC
    """).fetchall()
    jobs = conn.execute("""
        SELECT jobs.*, employers.company, employers.employer_code
        FROM jobs JOIN employers ON jobs.employer_id=employers.id
        ORDER BY jobs.id DESC
    """).fetchall()
    outcomes = conn.execute("SELECT * FROM outcomes WHERE trainee_id=? ORDER BY id DESC",
                            (session["trainee_id"],)).fetchall()
    followups = conn.execute("SELECT * FROM followups WHERE trainee_id=? ORDER BY id DESC",
                             (session["trainee_id"],)).fetchall()
    recommendations = skill_gap_recommendations(trainee, programs, jobs)
    current_skills = normalize_skills(trainee["skills"] or "")
    conn.close()
    return render_template("trainee_dashboard.html", trainee=trainee, programs=programs,
                           jobs=jobs, outcomes=outcomes, followups=followups,
                           recommendations=recommendations, current_skills=current_skills)


@app.route("/trainee/skill-gap", methods=["POST"])
@login_required("trainee")
def update_skill_profile():
    skills = request.form.get("skills", "").strip()
    conn = get_db()
    conn.execute("UPDATE trainees SET skills=? WHERE id=?", (skills, session["trainee_id"]))
    conn.commit()
    conn.close()
    flash("Your skills were updated. Skill gap analysis has been refreshed.", "success")
    return redirect(url_for("trainee_dashboard"))


@app.route("/trainee/program/<int:program_id>", methods=["POST"])
@login_required("trainee")
def trainee_program(program_id):
    flash("Your interest in this training program has been recorded.", "success")
    return redirect(url_for("trainee_dashboard"))


@app.route("/employer/dashboard")
@login_required("employer")
def employer_dashboard():
    conn = get_db()
    employer = conn.execute("SELECT * FROM employers WHERE id=?",
                            (session["employer_id"],)).fetchone()
    jobs = conn.execute("""
        SELECT * FROM jobs WHERE employer_id=? ORDER BY id DESC
    """, (session["employer_id"],)).fetchall()
    trainees = conn.execute("""
        SELECT id,trainee_code,name,course,district,status,certification
        FROM trainees ORDER BY id DESC
    """).fetchall()
    conn.close()
    return render_template("employer_dashboard.html", employer=employer,
                           jobs=jobs, trainees=trainees)


@app.route("/employer/job/add", methods=["POST"])
@login_required("employer")
def add_job():
    conn = get_db()
    conn.execute("""
        INSERT INTO jobs(employer_id,title,skills,location,salary,created_at)
        VALUES (?,?,?,?,?,?)
    """, (session["employer_id"], request.form["title"], request.form["skills"],
          request.form["location"], request.form["salary"], now()))
    conn.commit()
    conn.close()
    flash("Job opportunity posted under your employer account.", "success")
    return redirect(url_for("employer_dashboard"))


@app.route("/training/dashboard")
@login_required("training")
def training_dashboard():
    conn = get_db()
    center = conn.execute("SELECT * FROM training_centers WHERE id=?",
                          (session["training_center_id"],)).fetchone()
    programs = conn.execute("""
        SELECT * FROM training_programs
        WHERE training_center_id=? ORDER BY id DESC
    """, (session["training_center_id"],)).fetchall()
    trainees = conn.execute("""
        SELECT id,trainee_code,name,email,course,attendance,assessment,status,certification
        FROM trainees WHERE training_center_id=? ORDER BY id DESC
    """, (session["training_center_id"],)).fetchall()
    conn.close()
    return render_template("training_dashboard.html", center=center,
                           programs=programs, trainees=trainees)


@app.route("/training/program/add", methods=["POST"])
@login_required("training")
def add_program():
    conn = get_db()
    conn.execute("""
        INSERT INTO training_programs
        (training_center_id,name,provider,duration,seats,skills,eligibility,start_date,status,enrolled,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (session["training_center_id"], request.form["name"],
          request.form.get("provider", ""), request.form.get("duration", ""),
          request.form.get("seats", 0), request.form.get("skills", ""),
          request.form.get("eligibility", ""), request.form.get("start_date", ""),
          request.form.get("status", "Open"), 0, now()))
    conn.commit()
    conn.close()
    flash("Training program created under your training-center ID.", "success")
    return redirect(url_for("training_dashboard"))


# -------------------- ADMIN --------------------

@app.route("/admin/dashboard")
@login_required("admin")
def admin_dashboard():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM trainees").fetchone()[0]
    employed = conn.execute("SELECT COUNT(*) FROM trainees WHERE status='Employed'").fetchone()[0]
    self_employed = conn.execute("SELECT COUNT(*) FROM trainees WHERE status='Self-employed'").fetchone()[0]
    not_placed = conn.execute("SELECT COUNT(*) FROM trainees WHERE status='Not Placed'").fetchone()[0]
    certified = conn.execute("SELECT COUNT(*) FROM trainees WHERE certification='Certified'").fetchone()[0]

    centers = conn.execute("""
        SELECT tc.*, COUNT(t.id) AS trainee_count, COUNT(tp.id) AS program_count
        FROM training_centers tc
        LEFT JOIN trainees t ON t.training_center_id=tc.id
        LEFT JOIN training_programs tp ON tp.training_center_id=tc.id
        GROUP BY tc.id ORDER BY tc.id DESC
    """).fetchall()

    employers = conn.execute("""
        SELECT e.*, COUNT(j.id) AS job_count
        FROM employers e LEFT JOIN jobs j ON j.employer_id=e.id
        GROUP BY e.id ORDER BY e.id DESC
    """).fetchall()

    trainees = conn.execute("""
        SELECT t.*, tc.center_code, tc.center_name
        FROM trainees t
        LEFT JOIN training_centers tc ON t.training_center_id=tc.id
        ORDER BY t.id DESC
    """).fetchall()
    conn.close()

    placement = round(((employed + self_employed) / total) * 100, 1) if total else 0
    return render_template("admin_dashboard.html", total=total, employed=employed,
                           self_employed=self_employed, not_placed=not_placed,
                           certified=certified, placement=placement,
                           centers=centers, employers=employers, trainees=trainees)


@app.route("/admin/employer/add", methods=["POST"])
@login_required("admin")
def admin_add_employer():
    company = request.form["company"].strip()
    email = request.form["email"].strip().lower()
    password = request.form.get("password", "employer123")
    code = next_code("EMP", "employers", "employer_code")

    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO employers
            (employer_code,company,email,phone,industry,location,created_at)
            VALUES (?,?,?,?,?,?,?)
        """, (code, company, email, request.form.get("phone", ""),
              request.form.get("industry", ""), request.form.get("location", ""), now()))
        employer_id = cur.lastrowid
        cur.execute("""
            INSERT INTO users(email,password,role,employer_id,created_at)
            VALUES (?,?,?,?,?)
        """, (email, password, "employer", employer_id, now()))
        conn.commit()
        flash(f"Employer platform created. Employer ID: {code}", "success")
    except sqlite3.IntegrityError:
        conn.rollback()
        flash("Employer email already exists.", "error")
    finally:
        conn.close()
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/training-center/add", methods=["POST"])
@login_required("admin")
def admin_add_training_center():
    name = request.form["center_name"].strip()
    email = request.form["email"].strip().lower()
    password = request.form.get("password", "center123")
    code = next_code("TRN", "training_centers", "center_code")

    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO training_centers
            (center_code,center_name,email,phone,address,district,courses,created_at)
            VALUES (?,?,?,?,?,?,?,?)
        """, (code, name, email, request.form.get("phone", ""),
              request.form.get("address", ""), request.form.get("district", ""),
              request.form.get("courses", ""), now()))
        center_id = cur.lastrowid
        cur.execute("""
            INSERT INTO users(email,password,role,training_center_id,created_at)
            VALUES (?,?,?,?,?)
        """, (email, password, "training", center_id, now()))
        conn.commit()
        flash(f"Training center created. Training Center ID: {code}", "success")
    except sqlite3.IntegrityError:
        conn.rollback()
        flash("Training center email already exists.", "error")
    finally:
        conn.close()
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/training-center/<int:center_id>")
@login_required("admin")
def training_center_details(center_id):
    conn = get_db()
    center = conn.execute("SELECT * FROM training_centers WHERE id=?", (center_id,)).fetchone()
    trainees = conn.execute("""
        SELECT * FROM trainees WHERE training_center_id=? ORDER BY id DESC
    """, (center_id,)).fetchall()
    programs = conn.execute("""
        SELECT * FROM training_programs WHERE training_center_id=? ORDER BY id DESC
    """, (center_id,)).fetchall()
    account = conn.execute("""
        SELECT email FROM users WHERE training_center_id=? LIMIT 1
    """, (center_id,)).fetchone()
    conn.close()
    if not center:
        return "Training center not found", 404
    return render_template("training_center_details.html",
                           center=center, trainees=trainees, programs=programs, account=account)


@app.route("/admin/employer/<int:employer_id>")
@login_required("admin")
def employer_details(employer_id):
    conn = get_db()
    employer = conn.execute("SELECT * FROM employers WHERE id=?", (employer_id,)).fetchone()
    jobs = conn.execute("SELECT * FROM jobs WHERE employer_id=? ORDER BY id DESC",
                        (employer_id,)).fetchall()
    account = conn.execute("SELECT email FROM users WHERE employer_id=? LIMIT 1",
                           (employer_id,)).fetchone()
    conn.close()
    if not employer:
        return "Employer not found", 404
    return render_template("employer_details.html", employer=employer,
                           jobs=jobs, account=account)


@app.route("/add-trainee", methods=["GET", "POST"])
@login_required("admin")
def add_trainee():
    conn = get_db()
    centers = conn.execute("SELECT * FROM training_centers ORDER BY center_name").fetchall()
    conn.close()

    if request.method == "POST":
        data = {k: request.form.get(k, "").strip() for k in
                ["name", "email", "phone", "district", "education", "course", "skills", "provider",
                 "training_center_id", "attendance", "assessment", "certification", "status"]}
        password = request.form.get("password", "welcome123")

        conn = get_db()
        try:
            cur = conn.cursor()
            last = cur.execute("SELECT id FROM trainees ORDER BY id DESC LIMIT 1").fetchone()
            trainee_code = f"TRR-{(last['id'] + 1 if last else 1):04d}"

            cur.execute("""
                INSERT INTO trainees
                (trainee_code,name,email,phone,district,education,course,skills,training_center_id,
                 provider,attendance,assessment,certification,status,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (trainee_code, data["name"], data["email"], data["phone"], data["district"],
                  data["education"], data["course"], data["skills"], data["training_center_id"] or None,
                  data["provider"], data["attendance"] or 0, data["assessment"] or 0,
                  data["certification"] or "Not Certified", data["status"] or "Training Completed", now()))
            trainee_id = cur.lastrowid
            cur.execute("""
                INSERT INTO users(email,password,role,trainee_id,created_at)
                VALUES (?,?,?,?,?)
            """, (data["email"].lower(), password, "trainee", trainee_id, now()))
            conn.commit()
            flash(f"Trainee created. Trainee ID: {trainee_code}", "success")
        except sqlite3.IntegrityError:
            conn.rollback()
            flash("Email already exists. Use a different email.", "error")
        finally:
            conn.close()
        return redirect(url_for("admin_dashboard"))

    return render_template("add_trainee.html", centers=centers)


@app.route("/trainees")
@login_required()
def trainees():
    conn = get_db()
    search = request.args.get("search", "").strip()

    if session.get("role") == "training":
        base = """
            SELECT t.*, tc.center_code, tc.center_name
            FROM trainees t
            LEFT JOIN training_centers tc ON t.training_center_id=tc.id
            WHERE t.training_center_id=?
        """
        params = [session["training_center_id"]]
    else:
        base = """
            SELECT t.*, tc.center_code, tc.center_name
            FROM trainees t
            LEFT JOIN training_centers tc ON t.training_center_id=tc.id
            WHERE 1=1
        """
        params = []

    if search:
        base += " AND (t.name LIKE ? OR t.district LIKE ? OR t.course LIKE ? OR t.status LIKE ?)"
        params.extend([f"%{search}%"] * 4)

    base += " ORDER BY t.id DESC"
    data = conn.execute(base, params).fetchall()
    conn.close()
    return render_template("trainees.html", trainees=data, search=search)


@app.route("/admin/training-centers")
@login_required("admin")
def training_centers():
    conn = get_db()
    centers = conn.execute("""
        SELECT tc.*, COUNT(t.id) AS trainee_count
        FROM training_centers tc
        LEFT JOIN trainees t ON t.training_center_id=tc.id
        GROUP BY tc.id ORDER BY tc.id DESC
    """).fetchall()
    conn.close()
    return render_template("training_centers.html", centers=centers)


@app.route("/admin/employers")
@login_required("admin")
def admin_employers():
    conn = get_db()
    employers = conn.execute("""
        SELECT e.*, COUNT(j.id) AS job_count
        FROM employers e LEFT JOIN jobs j ON j.employer_id=e.id
        GROUP BY e.id ORDER BY e.id DESC
    """).fetchall()
    conn.close()
    return render_template("admin_employers.html", employers=employers)


@app.route("/trainee/<int:trainee_id>")
@login_required()
def trainee_details(trainee_id):
    role = session.get("role")
    if role == "trainee" and session.get("trainee_id") != trainee_id:
        flash("You can only view your own trainee record.", "error")
        return redirect(url_for("trainee_dashboard"))
    if role == "training":
        conn = get_db()
        allowed = conn.execute("SELECT 1 FROM trainees WHERE id=? AND training_center_id=?",
                               (trainee_id, session["training_center_id"])).fetchone()
        conn.close()
        if not allowed:
            return "Forbidden", 403

    conn = get_db()
    trainee = conn.execute("""
        SELECT t.*, tc.center_code, tc.center_name
        FROM trainees t LEFT JOIN training_centers tc
        ON t.training_center_id=tc.id
        WHERE t.id=?
    """, (trainee_id,)).fetchone()
    outcomes = conn.execute("SELECT * FROM outcomes WHERE trainee_id=?", (trainee_id,)).fetchall()
    followups = conn.execute("SELECT * FROM followups WHERE trainee_id=? ORDER BY id DESC",
                             (trainee_id,)).fetchall()
    programs = conn.execute("""
        SELECT training_programs.*, training_centers.center_code, training_centers.center_name
        FROM training_programs
        LEFT JOIN training_centers ON training_programs.training_center_id=training_centers.id
        WHERE training_programs.status IN ('Open','Upcoming')
        ORDER BY training_programs.id DESC
    """).fetchall()
    jobs = conn.execute("SELECT * FROM jobs ORDER BY id DESC").fetchall()
    conn.close()
    if not trainee:
        return "Trainee not found", 404
    recommendations = skill_gap_recommendations(trainee, programs, jobs)
    current_skills = normalize_skills(trainee["skills"] or "")
    return render_template("trainee_details.html", trainee=trainee,
                           outcomes=outcomes, followups=followups,
                           recommendations=recommendations, current_skills=current_skills)


@app.route("/add-outcome/<int:trainee_id>", methods=["POST"])
@login_required()
def add_outcome(trainee_id):
    if session.get("role") == "trainee" and session.get("trainee_id") != trainee_id:
        return "Forbidden", 403
    conn = get_db()
    conn.execute("""
        INSERT INTO outcomes
        (trainee_id,outcome_type,employer,job_role,salary,location,joining_date,training_relevance)
        VALUES (?,?,?,?,?,?,?,?)
    """, (trainee_id, request.form["outcome_type"], request.form["employer"],
          request.form["job_role"], request.form["salary"] or 0,
          request.form["location"], request.form["joining_date"],
          request.form["relevance"] or 0))
    conn.execute("UPDATE trainees SET status=? WHERE id=?",
                 (request.form["outcome_type"], trainee_id))
    conn.commit()
    conn.close()
    flash("Outcome recorded.", "success")
    return redirect(url_for("trainee_details", trainee_id=trainee_id))


@app.route("/add-followup/<int:trainee_id>", methods=["POST"])
@login_required()
def add_followup(trainee_id):
    if session.get("role") == "trainee" and session.get("trainee_id") != trainee_id:
        return "Forbidden", 403
    conn = get_db()
    conn.execute("""
        INSERT INTO followups
        (trainee_id,followup_period,employment_status,salary,job_role,
         difficulties,remarks,followup_date)
        VALUES (?,?,?,?,?,?,?,?)
    """, (trainee_id, request.form["period"], request.form["employment"],
          request.form["salary"] or 0, request.form["role"],
          request.form["difficulties"], request.form["remarks"], now()))
    conn.commit()
    conn.close()
    flash("Follow-up saved.", "success")
    return redirect(url_for("trainee_details", trainee_id=trainee_id))


@app.route("/analytics")
@login_required("admin")
def analytics():
    conn = get_db()
    courses = conn.execute("SELECT course, COUNT(*) AS total FROM trainees GROUP BY course").fetchall()
    districts = conn.execute("SELECT district, COUNT(*) AS total FROM trainees GROUP BY district").fetchall()
    statuses = conn.execute("SELECT status, COUNT(*) AS total FROM trainees GROUP BY status").fetchall()
    conn.close()
    return render_template("outcomes.html", courses=courses, districts=districts, statuses=statuses)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
