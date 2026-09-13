from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory
from database import init_db, get_db
import hashlib, csv, io
from datetime import datetime, timedelta

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.secret_key = "evacuai-secret-2024"
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

init_db()

def hp(p): return hashlib.sha256(p.encode()).hexdigest()
def uid(): return session.get("user")
def now(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ── Pages ─────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    if uid():
        return redirect(url_for("admin_page") if session.get("role")=="admin" else url_for("student_page"))
    return render_template("index.html")

@app.route("/student")
def student_page():
    if not uid() or session.get("role")!="student": return redirect(url_for("index"))
    return render_template("student.html", name=session.get("name"))

@app.route("/admin")
def admin_page():
    if not uid() or session.get("role")!="admin": return redirect(url_for("index"))
    return render_template("admin.html", name=session.get("name"))

@app.route("/logout")
def logout_page():
    session.clear(); session.modified=True
    return redirect(url_for("index"))

# ── Auth ──────────────────────────────────────────────────────────────────────
@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()
    sid  = data.get("student_id","").strip().upper()
    pw   = data.get("password","")
    if not sid or not pw: return jsonify({"error":"Please enter Student ID and password."}),400
    db   = get_db()
    user = db.execute("SELECT * FROM users WHERE student_id=?", (sid,)).fetchone()
    if not user:
        return jsonify({"error":"Student ID not found. Please contact your department registrar."}),404
    if user["password"] != hp(pw):
        return jsonify({"error":"Incorrect password."}),401
    session.update({"user":user["id"],"name":user["name"],"role":user["role"],"sid":sid})
    return jsonify({"role":user["role"],"name":user["name"],"must_change_pw":bool(user["must_change_pw"])})

@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear(); session.modified=True
    return jsonify({"message":"Logged out."})

@app.route("/api/me")
def me():
    if not uid(): return jsonify({"error":"Not logged in"}),401
    return jsonify({"id":uid(),"name":session.get("name"),"role":session.get("role")})

@app.route("/api/change-password", methods=["POST"])
def change_password():
    if not uid(): return jsonify({"error":"Unauthorized"}),401
    data   = request.get_json()
    old_pw = data.get("old_password","")
    new_pw = data.get("new_password","")
    if not new_pw or len(new_pw)<6: return jsonify({"error":"New password must be at least 6 characters."}),400
    db   = get_db()
    user = db.execute("SELECT * FROM users WHERE id=?", (uid(),)).fetchone()
    if user["password"] != hp(old_pw): return jsonify({"error":"Current password is incorrect."}),401
    db.execute("UPDATE users SET password=?, must_change_pw=0 WHERE id=?", (hp(new_pw), uid()))
    db.commit()
    return jsonify({"message":"Password changed successfully."})

# ── Student management (admin) ────────────────────────────────────────────────
@app.route("/api/users", methods=["GET"])
def get_users():
    if not uid() or session.get("role")!="admin": return jsonify({"error":"Unauthorized"}),401
    db   = get_db()
    rows = db.execute("SELECT id,name,email,student_id,role,must_change_pw FROM users ORDER BY role,name").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/users", methods=["POST"])
def add_user():
    if not uid() or session.get("role")!="admin": return jsonify({"error":"Unauthorized"}),401
    data = request.get_json()
    name = data.get("name","").strip()
    sid  = data.get("student_id","").strip()
    role = data.get("role","student")
    if not name or not sid: return jsonify({"error":"Name and Student ID are required."}),400
    if not sid.isdigit() or len(sid) != 8:
        return jsonify({"error":"Student ID must be exactly 8 digits."}),400
    # Auto-generate password from ID
    pw   = data.get("password","").strip() or gen_password(sid)
    db   = get_db()
    if db.execute("SELECT id FROM users WHERE student_id=?", (sid,)).fetchone():
        return jsonify({"error":"Student ID already exists."}),409
    db.execute("INSERT INTO users (name,student_id,password,role,must_change_pw) VALUES (?,?,?,?,1)",
               (name, sid, hp(pw), role))
    db.commit()
    return jsonify({"message":"Student account created.", "password":pw})

def gen_password(sid):
    """Auto-generate password: uc@ + last 6 digits of ID"""
    digits = ''.join(c for c in sid if c.isdigit())
    return 'uc@' + digits[-6:] if len(digits) >= 6 else 'uc@' + digits

@app.route("/api/users/upload-csv", methods=["POST"])
def upload_csv():
    if not uid() or session.get("role")!="admin": return jsonify({"error":"Unauthorized"}),401
    data     = request.get_json()
    csv_text = data.get("csv","")
    reader   = csv.DictReader(io.StringIO(csv_text))
    db       = get_db()
    added, skipped, errors = 0, 0, []
    for row in reader:
        sid  = row.get("student_id","").strip()
        name = row.get("name","").strip()
        role = row.get("role","student").strip() or "student"
        pw   = row.get("password","").strip() or gen_password(sid)
        if not sid or not name: skipped+=1; continue
        if db.execute("SELECT id FROM users WHERE student_id=?", (sid,)).fetchone():
            skipped+=1; continue
        db.execute("INSERT INTO users (name,student_id,password,role,must_change_pw) VALUES (?,?,?,?,1)",
                   (name, sid, hp(pw), role))
        added+=1
    db.commit()
    msg = f"Added {added} accounts. Skipped {skipped} (duplicate or incomplete)."
    return jsonify({"message":msg})

@app.route("/api/users/<int:user_id>", methods=["PATCH"])
def update_user(user_id):
    if not uid() or session.get("role")!="admin": return jsonify({"error":"Unauthorized"}),401
    data = request.get_json()
    db   = get_db()
    user = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not user: return jsonify({"error":"User not found."}),404
    name = data.get("name", user["name"]).strip()
    role = data.get("role", user["role"])
    new_pw = data.get("password","").strip()
    if new_pw:
        db.execute("UPDATE users SET name=?,role=?,password=?,must_change_pw=1 WHERE id=?",
                   (name, role, hp(new_pw), user_id))
    else:
        db.execute("UPDATE users SET name=?,role=? WHERE id=?", (name, role, user_id))
    db.commit()
    return jsonify({"message":"User updated."})

@app.route("/api/users/<int:user_id>", methods=["DELETE"])
def delete_user(user_id):
    if not uid() or session.get("role")!="admin": return jsonify({"error":"Unauthorized"}),401
    if user_id == uid(): return jsonify({"error":"Cannot delete your own account."}),400
    db = get_db()
    db.execute("DELETE FROM users WHERE id=?", (user_id,))
    db.execute("DELETE FROM safety_status WHERE user_id=?", (user_id,))
    db.execute("DELETE FROM reports WHERE user_id=?", (user_id,))
    db.commit()
    return jsonify({"message":"User deleted."})

# ── Alerts ────────────────────────────────────────────────────────────────────
@app.route("/api/alerts", methods=["GET"])
def get_alerts():
    db   = get_db()
    rows = db.execute("SELECT * FROM alerts WHERE status='approved' ORDER BY created_at DESC LIMIT 30").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/alerts/pending", methods=["GET"])
def get_pending():
    if not uid() or session.get("role")!="admin": return jsonify({"error":"Unauthorized"}),401
    db   = get_db()
    rows = db.execute("SELECT * FROM alerts WHERE status='pending' ORDER BY created_at ASC").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/alerts", methods=["POST"])
def post_alert():
    if not uid(): return jsonify({"error":"Unauthorized"}),401
    data    = request.get_json()
    kind    = data.get("type","general")
    message = data.get("message","").strip()
    role    = session.get("role","student")
    if not message: return jsonify({"error":"Message cannot be empty."}),400
    status  = "approved" if role=="admin" else "pending"
    db      = get_db()
    cur     = db.execute(
        "INSERT INTO alerts (type,message,sender,sender_role,created_at,user_id,status) VALUES (?,?,?,?,?,?,?)",
        (kind, message, session.get("name","Unknown"), role, now(), uid(), status)
    )
    db.commit()
    label = "Alert broadcast!" if role=="admin" else "Report submitted — waiting for admin approval."
    return jsonify({"message":label,"id":cur.lastrowid,"status":status})

@app.route("/api/alerts/<int:aid>", methods=["PATCH"])
def update_alert(aid):
    if not uid() or session.get("role")!="admin": return jsonify({"error":"Unauthorized"}),401
    data  = request.get_json()
    db    = get_db()
    alert = db.execute("SELECT * FROM alerts WHERE id=?", (aid,)).fetchone()
    if not alert: return jsonify({"error":"Alert not found."}),404
    msg  = data.get("message", alert["message"]).strip()
    kind = data.get("type", alert["type"])
    db.execute("UPDATE alerts SET message=?,type=? WHERE id=?", (msg, kind, aid))
    db.commit()
    return jsonify({"message":"Alert updated."})

@app.route("/api/alerts/<int:aid>", methods=["DELETE"])
def delete_alert(aid):
    if not uid(): return jsonify({"error":"Unauthorized"}),401
    db    = get_db()
    alert = db.execute("SELECT * FROM alerts WHERE id=?", (aid,)).fetchone()
    if not alert: return jsonify({"error":"Alert not found."}),404
    if session.get("role")=="admin" or alert["user_id"]==uid():
        db.execute("DELETE FROM alerts WHERE id=?", (aid,))
        db.commit()
        return jsonify({"message":"Alert deleted."})
    return jsonify({"error":"You can only delete your own alerts."}),403

@app.route("/api/alerts/<int:aid>/approve", methods=["POST"])
def approve_alert(aid):
    if not uid() or session.get("role")!="admin": return jsonify({"error":"Unauthorized"}),401
    db = get_db()
    db.execute("UPDATE alerts SET status='approved' WHERE id=?", (aid,))
    db.commit()
    return jsonify({"message":"Alert approved and now live."})

@app.route("/api/alerts/<int:aid>/decline", methods=["POST"])
def decline_alert(aid):
    if not uid() or session.get("role")!="admin": return jsonify({"error":"Unauthorized"}),401
    db = get_db()
    db.execute("UPDATE alerts SET status='declined' WHERE id=?", (aid,))
    db.commit()
    return jsonify({"message":"Alert declined."})

# ── Reports ───────────────────────────────────────────────────────────────────
@app.route("/api/reports", methods=["GET"])
def get_reports():
    if not uid() or session.get("role")!="admin": return jsonify({"error":"Unauthorized"}),401
    db   = get_db()
    rows = db.execute(
        "SELECT r.id,r.location,r.detail,r.created_at,r.user_id,u.name as student_name "
        "FROM reports r LEFT JOIN users u ON r.user_id=u.id ORDER BY r.created_at DESC"
    ).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/reports", methods=["POST"])
def post_report():
    if not uid(): return jsonify({"error":"Unauthorized"}),401
    data     = request.get_json()
    location = data.get("location","").strip()
    detail   = data.get("detail","").strip()
    if not location: return jsonify({"error":"Location is required."}),400
    db = get_db()
    db.execute("INSERT INTO reports (user_id,location,detail,created_at) VALUES (?,?,?,?)",
               (uid(), location, detail, now()))
    db.commit()
    return jsonify({"message":"Hazard report submitted."})

@app.route("/api/reports/<int:rid>", methods=["DELETE"])
def delete_report(rid):
    if not uid() or session.get("role")!="admin": return jsonify({"error":"Unauthorized"}),401
    db = get_db()
    db.execute("DELETE FROM reports WHERE id=?", (rid,))
    db.commit()
    return jsonify({"message":"Report deleted."})

# ── Safety ────────────────────────────────────────────────────────────────────
@app.route("/api/safe", methods=["POST"])
def mark_safe():
    if not uid(): return jsonify({"error":"Unauthorized"}),401
    db = get_db()
    db.execute("INSERT OR REPLACE INTO safety_status (user_id,is_safe,updated_at) VALUES (?,1,?)", (uid(),now()))
    db.commit()
    return jsonify({"message":"You have been marked as safe."})

@app.route("/api/safe/admin", methods=["POST"])
def admin_mark_safe():
    if not uid() or session.get("role")!="admin": return jsonify({"error":"Unauthorized"}),401
    user_id = request.get_json().get("user_id")
    db = get_db()
    db.execute("INSERT OR REPLACE INTO safety_status (user_id,is_safe,updated_at) VALUES (?,1,?)", (user_id,now()))
    db.commit()
    return jsonify({"message":"Student marked as safe."})

@app.route("/api/safe/reset", methods=["POST"])
def reset_safe():
    if not uid() or session.get("role")!="admin": return jsonify({"error":"Unauthorized"}),401
    db = get_db()
    db.execute("UPDATE safety_status SET is_safe=0, updated_at=?", (now(),))
    db.commit()
    return jsonify({"message":"All safety statuses reset."})

@app.route("/api/safety", methods=["GET"])
def get_safety():
    if not uid() or session.get("role")!="admin": return jsonify({"error":"Unauthorized"}),401
    db   = get_db()
    rows = db.execute(
        "SELECT u.id,u.name,u.student_id,COALESCE(s.is_safe,0) as is_safe,s.updated_at "
        "FROM users u LEFT JOIN safety_status s ON u.id=s.user_id WHERE u.role IN ('student','staff','teacher')"
    ).fetchall()
    return jsonify([dict(r) for r in rows])

# ── SOS ───────────────────────────────────────────────────────────────────────
@app.route("/api/sos", methods=["POST"])
def send_sos():
    if not uid(): return jsonify({"error":"Unauthorized"}),401
    db = get_db()
    existing = db.execute("SELECT id FROM sos_alerts WHERE user_id=? AND resolved=0 AND cancelled=0",(uid(),)).fetchone()
    if existing: return jsonify({"error":"You already have an active SOS."}),409
    db.execute("INSERT INTO sos_alerts (user_id,sender,created_at,resolved,responded,cancelled) VALUES (?,?,?,0,0,0)",
               (uid(), session.get("name","Unknown"), now()))
    db.commit()
    return jsonify({"message":"SOS sent."})

@app.route("/api/sos", methods=["GET"])
def get_sos():
    if not uid() or session.get("role")!="admin": return jsonify({"error":"Unauthorized"}),401
    db   = get_db()
    rows = db.execute(
        "SELECT s.*,u.name as student_name,u.email,u.student_id FROM sos_alerts s "
        "JOIN users u ON s.user_id=u.id WHERE s.cancelled=0 ORDER BY s.created_at DESC"
    ).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/sos/my", methods=["GET"])
def my_sos():
    if not uid(): return jsonify({"error":"Unauthorized"}),401
    db  = get_db()
    row = db.execute("SELECT * FROM sos_alerts WHERE user_id=? AND cancelled=0 ORDER BY created_at DESC LIMIT 1",(uid(),)).fetchone()
    if not row: return jsonify({"active":False})
    return jsonify(dict(row)|{"active":True})

@app.route("/api/sos/<int:sid>/respond", methods=["POST"])
def respond_sos(sid):
    if not uid() or session.get("role")!="admin": return jsonify({"error":"Unauthorized"}),401
    db  = get_db()
    sos = db.execute("SELECT * FROM sos_alerts WHERE id=?", (sid,)).fetchone()
    if not sos: return jsonify({"error":"Not found."}),404
    if sos["responded"]: return jsonify({"error":"Already responded."}),400
    db.execute("UPDATE sos_alerts SET responded=1,responded_at=?,notification=? WHERE id=?",
               (now(),"A safety officer has been deployed and is on the way to your location. Please stay calm and stay where you are if it is safe to do so.",sid))
    db.commit()
    return jsonify({"message":"Student notified."})

@app.route("/api/sos/<int:sid>/resolve", methods=["POST"])
def resolve_sos(sid):
    if not uid() or session.get("role")!="admin": return jsonify({"error":"Unauthorized"}),401
    db  = get_db()
    sos = db.execute("SELECT * FROM sos_alerts WHERE id=?", (sid,)).fetchone()
    if not sos: return jsonify({"error":"Not found."}),404
    if not sos["responded"]: return jsonify({"error":"Must mark responded before marking safe."}),400
    db.execute("UPDATE sos_alerts SET resolved=1,notification=? WHERE id=?",
               ("You have been marked as safe by a safety officer. Please proceed to the assembly area.",sid))
    db.execute("INSERT OR REPLACE INTO safety_status (user_id,is_safe,updated_at) VALUES (?,1,?)",(sos["user_id"],now()))
    db.commit()
    return jsonify({"message":"Student marked as safe."})

@app.route("/api/sos/<int:sid>/cancel", methods=["POST"])
def cancel_sos(sid):
    if not uid(): return jsonify({"error":"Unauthorized"}),401
    db  = get_db()
    sos = db.execute("SELECT * FROM sos_alerts WHERE id=?", (sid,)).fetchone()
    if not sos: return jsonify({"error":"Not found."}),404
    if sos["user_id"]!=uid(): return jsonify({"error":"Not your SOS."}),403
    if sos["responded"]: return jsonify({"error":"Cannot cancel — officer already on the way."}),400
    db.execute("UPDATE sos_alerts SET cancelled=1 WHERE id=?", (sid,))
    db.commit()
    return jsonify({"message":"SOS cancelled."})

@app.route("/profile")
def profile_page():
    if not uid(): return redirect(url_for("index"))
    return render_template("profile.html", name=session.get("name"), role=session.get("role"), sid=session.get("sid"))

@app.route("/admin/students")
def students_page():
    if not uid() or session.get("role") != "admin":
        return redirect(url_for("index"))
    return render_template("students.html", name=session.get("name"))

if __name__ == "__main__":
    app.run(debug=True, port=5000)
