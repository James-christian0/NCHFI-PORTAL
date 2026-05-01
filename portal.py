import os
import io
import base64
import datetime
import calendar
from flask import Flask, render_template_string, request, redirect, url_for, session, flash, abort

try:
    import qrcode
except ImportError:
    print("Please run: pip install qrcode[pil]")

app = Flask(__name__)
app.secret_key = 'nchfi_innovation_2026'
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # Strict 5MB limit

# --- DATA STORE (In-Memory) ---
users = {
    'admin': {
        'password': 'admin_password', 
        'name': 'Admin Office', 
        'role': 'admin'
    }
}
announcements = [] 

# Global structure for tasks (Admin can modify these)
# Format: { 'category_name': { 'task_name': { 'deadline': 'date', 'max_attempts': int } } }
curriculum = {
    'assignments': {
        "Ethics Case Study": {"deadline": "2026-05-15", "max_attempts": 2},
        "Reflection Paper": {"deadline": "2026-05-20", "max_attempts": 1}
    },
    'projects': {
        "STS Innovation Prototype": {"deadline": "2026-06-01", "max_attempts": 3}
    }
}

# --- STYLING ---
BASE_CSS = """
:root { --nchfi-maroon: #800000; --nchfi-gold: #FFD700; --late-orange: #ff8c00; }
body { font-family: 'Segoe UI', sans-serif; background-color: #f4f4f9; margin: 0; padding-bottom: 50px; color: #333; }
.navbar { background: var(--nchfi-maroon); color: white; padding: 12px 25px; display: flex; align-items: center; justify-content: space-between; box-shadow: 0 2px 5px rgba(0,0,0,0.2); }
.navbar img { height: 45px; background: white; border-radius: 50%; padding: 2px; }
.container { max-width: 1100px; margin: 20px auto; padding: 0 20px; }
.card { background: white; border: 1px solid #ddd; padding: 20px; margin-bottom: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
.btn { background: var(--nchfi-maroon); color: white; border: none; padding: 8px 15px; border-radius: 6px; cursor: pointer; text-decoration: none; font-weight: 600; font-size: 13px; }
.btn-gold { background: var(--nchfi-gold); color: var(--nchfi-maroon); }
.btn-danger { background: #dc3545; }
.scroll-container { max-height: 300px; overflow-y: auto; border: 1px solid #eee; padding: 10px; border-radius: 8px; }
table { width: 100%; border-collapse: collapse; margin-top: 10px; }
th, td { text-align: left; padding: 12px; border-bottom: 1px solid #eee; }
.status-tag { padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }
.tag-submitted { background: #d4edda; color: #155724; }
.tag-pending { background: #f8d7da; color: #721c24; }
.calendar-item { border-left: 4px solid var(--nchfi-maroon); padding: 10px; margin-bottom: 10px; background: #fffcfc; border-radius: 0 8px 8px 0; }
.grid { display: grid; grid-template-columns: 1.5fr 1fr; gap: 20px; }
"""

FOOTER_HTML = """
<footer>
    © 2026 Nazarenus College and Hospital Foundation Inc.<br>
    Developed by: Karen D. Soriano & James Christian G. Octaviano<br>
    <em>An Efficient Student Monitoring System Innovation</em>
</footer>
"""

# --- DASHBOARD TEMPLATE ---
DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head><title>NCHFI Portal</title><style>""" + BASE_CSS + """</style></head>
<body>
    <div class="navbar">
        <div style="display:flex; align-items:center;"><img src="https://i.postimg.cc/9fNfM7vH/image-9da406.png"> <h2 style="margin-left:15px;">NCHFI {{ role|upper }}</h2></div>
        <div><span style="margin-right:15px;">{{ user.name }}</span><a href="/logout" style="color:white; font-weight:bold;">Logout</a></div>
    </div>

    <div class="container">
        {% with messages = get_flashed_messages() %}{% for msg in messages %}<p style="color:red; background:#ffdada; padding:10px; border-radius:5px;">{{ msg }}</p>{% endfor %}{% endwith %}

        {% if role == 'admin' %}
        <!-- ADMIN DASHBOARD -->
        <div class="grid">
            <div class="card">
                <h3>Curriculum Override (Assignments & Projects)</h3>
                <form action="/admin/add_task" method="post" style="display:flex; gap:10px; flex-wrap:wrap;">
                    <input name="task_name" placeholder="Task Name" required style="flex:2;">
                    <select name="category" style="flex:1;"><option value="assignments">Subject Assignment</option><option value="projects">Project Tab</option></select>
                    <input type="date" name="deadline" required style="flex:1;">
                    <input type="number" name="attempts" placeholder="Max Attempts" value="1" style="width:100px;">
                    <button type="submit" class="btn btn-gold">Add Task</button>
                </form>

                <div class="scroll-container" style="margin-top:20px;">
                    <table>
                        <tr><th>Task</th><th>Category</th><th>Deadline</th><th>Action</th></tr>
                        {% for cat, tasks in curriculum.items() %}
                            {% for tname, tdata in tasks.items() %}
                            <tr><td>{{ tname }}</td><td>{{ cat }}</td><td>{{ tdata.deadline }}</td>
                            <td><a href="/admin/delete_task/{{ cat }}/{{ tname }}" class="btn btn-danger" style="font-size:10px;">Remove</a></td></tr>
                            {% endfor %}
                        {% endfor %}
                    </table>
                </div>
            </div>

            <div class="card">
                <h3>Calendar & Broadcast</h3>
                <form action="/post_announcement" method="post">
                    <textarea name="content" placeholder="Public announcement..." required style="height:60px;"></textarea>
                    <input type="date" name="event_date" required>
                    <button type="submit" name="admin_post" value="true" class="btn" style="width:100%;">Post Public Event</button>
                </form>
            </div>
        </div>

        <div class="card">
            <h3>Student Monitoring Tab</h3>
            <div class="scroll-container">
                <table>
                    <thead>
                        <tr><th>Student Name</th><th>ID</th><th>Present/Late</th><th>Submission Status</th><th>Action</th></tr>
                    </thead>
                    <tbody>
                        {% for uid, udata in all_users.items() if udata.role == 'student' %}
                        <tr>
                            <td>{{ udata.name }}</td><td>{{ uid }}</td>
                            <td>{{ udata.attendance.present|length }}P / {{ udata.attendance.late|length }}L</td>
                            <td>{{ udata.submissions|length }} Total</td>
                            <td><a href="/admin/view_submissions/{{ uid }}" class="btn" style="font-size:10px;">Review</a></td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>

        {% else %}
        <!-- STUDENT DASHBOARD -->
        <div class="grid">
            <div>
                <div class="card">
                    <h3>Submissions Portal (Max 5MB)</h3>
                    {% for cat, tasks in curriculum.items() %}
                        <h4 style="color:var(--nchfi-maroon); border-bottom:2px solid var(--nchfi-gold);">{{ cat|capitalize }}</h4>
                        {% for tname, tdata in tasks.items() %}
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:15px; background:#fefefe; padding:10px; border-radius:8px; border:1px solid #eee;">
                            <div>
                                <strong>{{ tname }}</strong> <br>
                                <small>Deadline: {{ tdata.deadline }} | Attempts: {{ user.submissions.get(tname, {}).get('attempts', 0) }}/{{ tdata.max_attempts }}</small>
                            </div>
                            <div>
                                {% if tname in user.submissions %}
                                    <span class="status-tag tag-submitted">Submitted</span>
                                {% else %}
                                    <span class="status-tag tag-pending">Pending</span>
                                {% endif %}
                                
                                <form action="/submit_file" method="post" enctype="multipart/form-data" style="display:inline; margin-left:10px;">
                                    <input type="hidden" name="task_name" value="{{ tname }}">
                                    <input type="file" name="file_upload" style="font-size:10px; width:120px;" required>
                                    <button class="btn btn-gold" style="padding:4px 8px;">Upload</button>
                                </form>
                            </div>
                        </div>
                        {% endfor %}
                    {% endfor %}
                </div>
            </div>

            <div>
                <div class="card">
                    <h3>Calendar & Announcements</h3>
                    <form action="/post_announcement" method="post" style="margin-bottom:15px;">
                        <input name="content" placeholder="Private note..." required>
                        <input type="date" name="event_date" required>
                        <button type="submit" class="btn" style="width:100%;">Add Personal Event</button>
                    </form>
                    <div class="scroll-container">
                        {% for ann in announcements %}
                            {% if ann.type == 'public' or ann.author == user.name %}
                            <div class="calendar-item" style="border-left-color: {{ 'var(--nchfi-maroon)' if ann.type == 'public' else '#ccc' }}">
                                <small style="font-weight:bold; color:var(--nchfi-maroon);">{{ ann.date }}</small> - <span>{{ ann.type|upper }}</span><br>
                                {{ ann.content }}
                            </div>
                            {% endif %}
                        {% endfor %}
                    </div>
                </div>

                <div class="card" style="text-align:center;">
                    <h3>Attendance QR</h3>
                    <img src="data:image/png;base64,{{ qr_code }}" width="120">
                    <p style="font-size:12px;">Scan at Terminal or <br><a href="/scan_manual">Manual Check-in</a></p>
                </div>
            </div>
        </div>
        {% endif %}

        """ + FOOTER_HTML + """
    </div>
</body>
</html>
"""

# --- LOGIC ---

@app.route('/')
def dashboard():
    if 'user' not in session: return redirect('/login')
    uid = session['user']
    user_data = users[uid]
    
    qr_b64 = ""
    if user_data['role'] == 'student':
        qr = qrcode.make(f"NCHFI_{uid}_{datetime.date.today()}")
        buf = io.BytesIO()
        qr.save(buf, format='PNG')
        qr_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')

    return render_template_string(DASHBOARD_HTML, 
                                user=user_data, 
                                role=user_data['role'], 
                                all_users=users, 
                                curriculum=curriculum,
                                announcements=announcements,
                                qr_code=qr_b64)

@app.route('/admin/add_task', methods=['POST'])
def add_task():
    if session.get('user') != 'admin': abort(403)
    cat = request.form['category']
    name = request.form['task_name']
    curriculum[cat][name] = {
        "deadline": request.form['deadline'],
        "max_attempts": int(request.form['attempts'])
    }
    flash(f"Task '{name}' added successfully.")
    return redirect('/')

@app.route('/admin/delete_task/<cat>/<name>')
def delete_task(cat, name):
    if session.get('user') == 'admin':
        curriculum[cat].pop(name, None)
    return redirect('/')

@app.route('/submit_file', methods=['POST'])
def submit_file():
    if 'user' not in session: return redirect('/login')
    uid = session['user']
    task_name = request.form['task_name']
    
    # Check attempts
    # Find which category this task belongs to
    task_config = None
    for cat in curriculum:
        if task_name in curriculum[cat]:
            task_config = curriculum[cat][task_name]
            break
            
    if not task_config: return "Task not found", 404
    
    current_submission = users[uid]['submissions'].get(task_name, {'attempts': 0})
    
    if current_submission['attempts'] >= task_config['max_attempts']:
        flash(f"Error: Maximum attempts ({task_config['max_attempts']}) reached for this task.")
        return redirect('/')

    file = request.files['file_upload']
    if file:
        # In a real app, you'd save the file to os.path.join(UPLOAD_FOLDER, file.filename)
        # Here we just record the metadata
        users[uid]['submissions'][task_name] = {
            'filename': file.filename,
            'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            'attempts': current_submission['attempts'] + 1
        }
        flash(f"Successfully submitted {file.filename} (Attempt {current_submission['attempts'] + 1})")
        
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
        # Sort announcements by date (Calendar alignment)
        announcements.sort(key=lambda x: x['date'])
    return redirect('/')

# --- AUTH & SYSTEM ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        u = request.form['username']
        if u in users:
            flash("ID already registered")
            return redirect('/register')
        users[u] = {
            'password': request.form['password'],
            'name': request.form['name'],
            'role': 'student',
            'attendance': {'present': [], 'late': []},
            'submissions': {}
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
        flash("Invalid Credentials")
    return render_template_string(AUTH_HTML, mode='Login')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

AUTH_HTML = """
<!DOCTYPE html><html><head><style>""" + BASE_CSS + """</style></head>
<body>
    <div class="navbar"><img src="https://i.postimg.cc/9fNfM7vH/image-9da406.png"> <h2>NCHFI Portal</h2></div>
    <div class="container" style="max-width: 400px; margin-top: 50px;">
        <div class="card">
            <h3>{{ mode }}</h3>
            <form method="post">
                {% if mode == 'Register' %}<input name="name" placeholder="Full Name" required>{% endif %}
                <input name="username" placeholder="ID Number" required>
                <input name="password" type="password" placeholder="Password" required>
                <button type="submit" class="btn" style="width:100%;">{{ mode }}</button>
            </form>
            <p><a href="{{ url_for('login' if mode == 'Register' else 'register') }}">{{ 'Login' if mode == 'Register' else 'Register' }}</a></p>
        </div>
    </div>
</body></html>
"""

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
