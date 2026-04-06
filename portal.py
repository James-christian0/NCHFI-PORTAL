import os
import io
import base64
import datetime
import calendar
from flask import Flask, render_template_string, request, redirect, url_for, session, flash

try:
    import qrcode
except ImportError:
    print("Please run: pip install qrcode[pil]")

app = Flask(__name__)
app.secret_key = 'nchfi_innovation_2026'

# --- DATA STORE (In-Memory) ---
# Roles: 'admin' or 'student'
users = {
    'admin': {
        'password': 'admin_password', 
        'name': 'Admin Office', 
        'role': 'admin'
    }
} 
announcements = [] # {id, author, content, date, type: 'public'/'private'}

# --- STYLING ---
BASE_CSS = """
:root { --nchfi-maroon: #800000; --nchfi-gold: #FFD700; --late-orange: #ff8c00; }
body { font-family: 'Segoe UI', sans-serif; background-color: #f4f4f9; margin: 0; padding-bottom: 50px; color: #333; }
.navbar { background: var(--nchfi-maroon); color: white; padding: 12px 25px; display: flex; align-items: center; justify-content: space-between; box-shadow: 0 2px 5px rgba(0,0,0,0.2); }
.navbar img { height: 45px; background: white; border-radius: 50%; padding: 2px; }
.container { max-width: 900px; margin: 20px auto; padding: 0 20px; }
.card { background: white; border: 1px solid #ddd; padding: 20px; margin-bottom: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
.btn { background: var(--nchfi-maroon); color: white; border: none; padding: 10px 18px; border-radius: 6px; cursor: pointer; text-decoration: none; font-weight: 600; transition: 0.3s; }
.btn:hover { opacity: 0.9; transform: translateY(-1px); }
.btn-late { background: var(--late-orange); }
.btn-delete { background: #dc3545; font-size: 11px; padding: 5px 10px; }
.status-tag { padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; text-transform: uppercase; }
.tag-submitted { background: #d4edda; color: #155724; }
.tag-pending { background: #f8d7da; color: #721c24; }
footer { text-align: center; font-size: 12px; color: #777; margin-top: 30px; line-height: 1.6; }
input, textarea { width: 100%; padding: 12px; margin: 8px 0; border: 1px solid #ccc; border-radius: 6px; box-sizing: border-box; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
"""

# --- SHARED COMPONENTS ---
FOOTER_HTML = """
<footer>
    © 2026 Nazarenus College and Hospital Foundation Inc.<br>
    Developed by: Karen D. Soriano & James Christian G. Octaviano<br>
    <em>An Efficient Student Monitoring System Innovation</em>
</footer>
"""

# --- LOGIN TEMPLATE ---
AUTH_HTML = """
<!DOCTYPE html>
<html>
<head><title>NCHFI | Login</title><style>""" + BASE_CSS + """</style></head>
<body>
    <div class="navbar"><img src="https://i.postimg.cc/9fNfM7vH/image-9da406.png"> <h2>NCHFI Portal</h2> <span></span></div>
    <div class="container" style="max-width: 400px; margin-top: 50px;">
        <div class="card">
            <h3 style="text-align:center;">{{ mode }}</h3>
            {% with msgs = get_flashed_messages() %}{% for m in msgs %}<p style="color:red; font-size:12px;">{{m}}</p>{% endfor %}{% endwith %}
            <form method="post">
                {% if mode == 'Register' %}<input name="name" placeholder="Full Name" required>{% endif %}
                <input name="username" placeholder="Student ID / Admin User" required>
                <input name="password" type="password" placeholder="Password" required>
                <button type="submit" class="btn" style="width:100%;">{{ mode }}</button>
            </form>
            <p style="text-align:center; font-size:14px;">
                <a href="{{ url_for('login' if mode == 'Register' else 'register') }}">
                    {{ 'Back to Login' if mode == 'Register' else 'New Student? Register here' }}
                </a>
            </p>
        </div>
        """ + FOOTER_HTML + """
    </div>
</body>
</html>
"""

# --- MAIN DASHBOARD (Unified Admin & User) ---
DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head><title>NCHFI Dashboard</title><style>""" + BASE_CSS + """</style></head>
<body>
    <div class="navbar">
        <div style="display:flex; align-items:center;"><img src="https://i.postimg.cc/9fNfM7vH/image-9da406.png"> <h2 style="margin-left:15px;">NCHFI {{ 'ADMIN' if role == 'admin' else 'STUDENT' }}</h2></div>
        <div>
            <span style="margin-right:15px;">{{ user.name }}</span>
            <a href="/logout" style="color:white; font-weight:bold;">Logout</a>
        </div>
    </div>

    <div class="container">
        {% if role == 'student' %}
        <div class="grid">
            <div class="card">
                <h3>Attendance & Performance</h3>
                <p>Present: <strong>{{ stats.present }}</strong> | Late: <strong>{{ stats.late }}</strong></p>
                <p>Monthly Target: {{ stats.total_days }} days</p>
                <div style="background:#eee; width:100%; height:20px; border-radius:10px; overflow:hidden;">
                    <div style="background:linear-gradient(to right, #28a745, #FFD700); width:{{ stats.percent }}%; height:100%; text-align:center; color:white; font-size:12px; line-height:20px;">
                        {{ stats.percent }}%
                    </div>
                </div>
                <div style="text-align:center; margin-top:20px;">
                    <img src="data:image/png;base64,{{ qr_code }}" width="140" style="border:1px solid #ddd; padding:5px;"><br>
                    <div style="margin-top:10px;">
                        <form action="/scan" method="post" style="display:inline;">
                            <button name="type" value="present" class="btn">Manual Present</button>
                            <button name="type" value="late" class="btn btn-late">Record Late</button>
                        </form>
                    </div>
                </div>
            </div>

            <div class="card">
                <h3>Announcement Hub</h3>
                <form action="/post_announcement" method="post">
                    <input name="content" placeholder="Post a query to the hub..." required>
                    <input type="date" name="event_date" required>
                    <button type="submit" class="btn" style="width:100%;">Post Privately</button>
                </form>
                <hr>
                <div style="max-height: 200px; overflow-y:auto;">
                    {% for ann in announcements %}
                        {% if ann.type == 'public' or ann.author == user.name %}
                        <div style="background:#f9f9f9; padding:10px; margin-bottom:8px; border-radius:6px; border-left:4px solid {{ 'maroon' if ann.type == 'public' else '#ccc' }}; position:relative;">
                            <small>{{ ann.author }} | {{ ann.date }}</small><br>
                            {{ ann.content }}
                            {% if ann.author == user.name %}
                            <a href="/delete_announcement/{{ loop.index0 }}" class="btn-delete" style="position:absolute; right:5px; top:5px;">X</a>
                            {% endif %}
                        </div>
                        {% endif %}
                    {% endfor %}
                </div>
            </div>
        </div>

        <div class="grid">
            <div class="card">
                <h3>Assignments Monitor</h3>
                {% for task, status in user.assignments.items() %}
                <div style="display:flex; justify-content:space-between; align-items:center; padding:10px 0; border-bottom:1px solid #eee;">
                    <span>{{ task }}</span>
                    <div>
                        <span class="status-tag {{ 'tag-submitted' if status else 'tag-pending' }}">{{ 'Done' if status else 'Pending' }}</span>
                        <form action="/submit_task" method="post" style="display:inline; margin-left:10px;">
                            <input type="hidden" name="task" value="{{ task }}">
                            <input type="hidden" name="category" value="assignments">
                            <button class="btn" style="padding:2px 8px; font-size:10px;">{{ 'Resubmit' if status else 'Submit' }}</button>
                        </form>
                    </div>
                </div>
                {% endfor %}
            </div>

            <div class="card">
                <h3>Project Tracker</h3>
                {% for task, status in user.projects.items() %}
                <div style="display:flex; justify-content:space-between; align-items:center; padding:10px 0; border-bottom:1px solid #eee;">
                    <span>{{ task }}</span>
                    <div>
                        <span class="status-tag {{ 'tag-submitted' if status else 'tag-pending' }}">{{ 'Done' if status else 'Pending' }}</span>
                        <form action="/submit_task" method="post" style="display:inline; margin-left:10px;">
                            <input type="hidden" name="task" value="{{ task }}">
                            <input type="hidden" name="category" value="projects">
                            <button class="btn" style="padding:2px 8px; font-size:10px;">{{ 'Update' if status else 'Submit' }}</button>
                        </form>
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>

        {% else %}
        <div class="card">
            <h3>Admin: Public Announcement & Event Scheduler</h3>
            <form action="/post_announcement" method="post">
                <textarea name="content" placeholder="Public Announcement (visible to all students)..." required></textarea>
                <div style="display:flex; gap:10px; align-items:center;">
                    <input type="date" name="event_date" required style="flex:1;">
                    <button type="submit" name="admin_post" value="true" class="btn" style="flex:1;">Schedule & Broadcast</button>
                </div>
            </form>
        </div>

        <div class="card">
            <h3>Monitor All Hub Activity</h3>
            <div style="max-height: 400px; overflow-y:auto;">
                {% for ann in announcements %}
                <div style="background:#f4f4f4; padding:10px; margin-bottom:10px; border-radius:8px; position:relative;">
                    <span class="status-tag {{ 'tag-submitted' if ann.type == 'public' else '' }}" style="background:#800000; color:white;">{{ ann.type }}</span>
                    <strong>{{ ann.author }}</strong> - <small>{{ ann.date }}</small><br>
                    <p>{{ ann.content }}</p>
                    <a href="/delete_announcement/{{ loop.index0 }}" class="btn btn-delete" style="position:absolute; right:10px; top:10px;">Delete as Admin</a>
                </div>
                {% endfor %}
            </div>
        </div>
        {% endif %}

        """ + FOOTER_HTML + """
    </div>
</body>
</html>
"""

# --- LOGIC ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        u = request.form['username']
        if u in users:
            flash("User already exists")
            return redirect('/register')
        users[u] = {
            'password': request.form['password'],
            'name': request.form['name'],
            'role': 'student',
            'attendance': {'present': [], 'late': []},
            'assignments': {"Case Study 1": False, "Reflection Paper": False},
            'projects': {"STS Innovation Final": False, "Community Portal Prototype": False}
        }
        return redirect('/login')
    return render_template_string(AUTH_HTML, mode='Register')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u, p = request.form['username'], request.form['password']
        if u in users and users[u]['password'] == p:
            session['user'] = u
            return redirect('/')
        flash("Invalid credentials")
    return render_template_string(AUTH_HTML, mode='Login')

@app.route('/')
def dashboard():
    if 'user' not in session: return redirect('/login')
    uid = session['user']
    user_data = users[uid]
    role = user_data['role']
    
    qr_b64 = ""
    stats = {}

    if role == 'student':
        # Automated Monthly Day Logic
        now = datetime.datetime.now()
        _, total_days = calendar.monthrange(now.year, now.month)
        
        present_count = len(user_data['attendance']['present'])
        late_count = len(user_data['attendance']['late'])
        
        # Calculate overall percentage (Late counts as 0.75 of a presence for academic weighting)
        weighted_presence = present_count + (late_count * 0.75)
        percent = int((weighted_presence / total_days) * 100) if total_days > 0 else 0
        
        stats = {'present': present_count, 'late': late_count, 'total_days': total_days, 'percent': min(percent, 100)}

        # Optimized QR
        qr = qrcode.make(f"NCHFI_SECURE_ID_{uid}_{now.strftime('%Y%m%d')}")
        buf = io.BytesIO()
        qr.save(buf, format='PNG')
        qr_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')

    return render_template_string(DASHBOARD_HTML, 
                                user=user_data, 
                                role=role,
                                announcements=announcements, 
                                qr_code=qr_b64, 
                                stats=stats)

@app.route('/scan', methods=['POST'])
def scan():
    if 'user' in session:
        uid = session['user']
        scan_type = request.form.get('type') # 'present' or 'late'
        today = datetime.date.today().isoformat()
        
        # Avoid duplicate scanning for the same day
        if today not in users[uid]['attendance']['present'] and today not in users[uid]['attendance']['late']:
            users[uid]['attendance'][scan_type].append(today)
    return redirect('/')

@app.route('/submit_task', methods=['POST'])
def submit_task():
    if 'user' in session:
        task_name = request.form.get('task')
        category = request.form.get('category') # 'assignments' or 'projects'
        users[session['user']][category][task_name] = True # Flip to true or toggle
    return redirect('/')

@app.route('/post_announcement', methods=['POST'])
def post_announcement():
    if 'user' in session:
        user_data = users[session['user']]
        is_admin_post = request.form.get('admin_post') == 'true' and user_data['role'] == 'admin'
        
        announcements.insert(0, {
            'author': user_data['name'],
            'content': request.form['content'],
            'date': request.form['event_date'],
            'type': 'public' if is_admin_post else 'private'
        })
    return redirect('/')

@app.route('/delete_announcement/<int:id>')
def delete_announcement(id):
    if 'user' in session:
        user_data = users[session['user']]
        if 0 <= id < len(announcements):
            # Logic: Admin can delete anything. Students can only delete their own.
            if user_data['role'] == 'admin' or announcements[id]['author'] == user_data['name']:
                announcements.pop(id)
    return redirect('/')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
