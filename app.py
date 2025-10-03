from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import os
import math
import random
import string
reset_codes = {}
bin_status = {"el tarf": "pending"}

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY, fullname TEXT, username TEXT, email TEXT, password TEXT, role TEXT,
                  current_latitude REAL, current_longitude REAL, points INTEGER DEFAULT 0, promotion TEXT DEFAULT 'New Driver')''')
    
    c.execute("SELECT * FROM users WHERE username=?", ('admin',))
    if not c.fetchone():
        c.execute("INSERT INTO users (fullname, username, email, password, role, current_latitude, current_longitude, points, promotion) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                  ('Administrator', 'admin', 'admin@gmail.com', 'admin123', 'admin', 0.0, 0.0, 0, 'None'))
    
    c.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in c.fetchall()]
    if 'points' not in columns:
        c.execute("ALTER TABLE users ADD COLUMN points INTEGER DEFAULT 0")
    if 'promotion' not in columns:
        c.execute("ALTER TABLE users ADD COLUMN promotion TEXT DEFAULT 'New Driver'")
    
    c.execute('''CREATE TABLE IF NOT EXISTS trash_bins 
                 (id INTEGER PRIMARY KEY, user_id INTEGER, location TEXT, latitude REAL, longitude REAL, 
                  fill_percentage REAL, is_full INTEGER, status TEXT, reported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  notes TEXT, assigned_driver_id INTEGER, FOREIGN KEY(user_id) REFERENCES users(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS messages 
                 (id INTEGER PRIMARY KEY, user_id INTEGER, message TEXT, status TEXT, 
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
                  FOREIGN KEY(user_id) REFERENCES users(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS maintenance_requests 
                 (id INTEGER PRIMARY KEY, user_id INTEGER, location TEXT, latitude REAL, longitude REAL, 
                  problem_type TEXT, description TEXT, image_path TEXT, status TEXT, 
                  reported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, notes TEXT, assigned_driver_id INTEGER,
                  FOREIGN KEY(user_id) REFERENCES users(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS purchase_requests 
                 (id INTEGER PRIMARY KEY, user_id INTEGER, bin_type TEXT, quantity INTEGER, delivery_address TEXT, 
                  latitude REAL, longitude REAL, status TEXT, 
                  requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, notes TEXT, assigned_driver_id INTEGER,
                  FOREIGN KEY(user_id) REFERENCES users(id))''')
    
    conn.commit()
    conn.close()

# Haversine formula for distance calculation
def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        user = c.fetchone()
        conn.close()
        if user:
            session['username'] = user[2]  # Username
            session['role'] = user[5]      # Role
            if session['role'] == 'driver':
                return redirect(url_for('driver_dashboard'))
            elif session['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:  # user
                return redirect(url_for('user_dashboard'))
        else:
            error = "Wrong username or password"
    return render_template('login.html', error=error)

@app.route('/sign', methods=['GET', 'POST'])
def sign():
    if request.method == 'POST':
        fullname = request.form['fullname']
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        role = request.form.get('role', 'user')
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("INSERT INTO users (fullname, username, email, password, role, current_latitude, current_longitude) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (fullname, username, email, password, role, 0.0, 0.0))
        conn.commit()
        conn.close()
        return redirect(url_for('login'))
    return render_template('sign.html')

@app.route('/user_dashboard')
def user_dashboard():
    if 'username' not in session or session['role'] != 'user':
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username=?", (session['username'],))
    user_id = c.fetchone()[0]
    
    # Total requests (notifications + purchases + maintenance)
    c.execute("SELECT COUNT(*) FROM trash_bins WHERE user_id=?", (user_id,))
    trash_notifications_count = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM purchase_requests WHERE user_id=?", (user_id,))
    purchase_requests_count = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM maintenance_requests WHERE user_id=?", (user_id,))
    maintenance_requests_count = c.fetchone()[0]
    
    notifications_count = trash_notifications_count + purchase_requests_count + maintenance_requests_count
    
    # Collected requests (approved or completed)
    c.execute("SELECT COUNT(*) FROM trash_bins WHERE user_id=? AND status IN ('approved', 'completed')", (user_id,))
    collected_trash_count = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM purchase_requests WHERE user_id=? AND status IN ('approved', 'completed')", (user_id,))
    collected_purchase_count = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM maintenance_requests WHERE user_id=? AND status IN ('approved', 'completed')", (user_id,))
    collected_maintenance_count = c.fetchone()[0]
    
    collected_count = collected_trash_count + collected_purchase_count + collected_maintenance_count
    
    # Pending requests
    c.execute("SELECT COUNT(*) FROM trash_bins WHERE user_id=? AND status='pending'", (user_id,))
    pending_trash_count = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM purchase_requests WHERE user_id=? AND status='pending'", (user_id,))
    pending_purchase_count = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM maintenance_requests WHERE user_id=? AND status='pending'", (user_id,))
    pending_maintenance_count = c.fetchone()[0]
    
    pending_count = pending_trash_count + pending_purchase_count + pending_maintenance_count
    
    # Recent requests (unchanged)
    c.execute("SELECT id, location, fill_percentage, status, reported_at FROM trash_bins WHERE user_id=? AND status='pending' ORDER BY reported_at DESC LIMIT 5", (user_id,))
    recent_notifications = c.fetchall()
    
    c.execute("SELECT message, created_at FROM messages WHERE user_id=? ORDER BY created_at DESC LIMIT 5", (user_id,))
    recent_messages = c.fetchall()
    
    c.execute("SELECT id, location, problem_type, status, reported_at FROM maintenance_requests WHERE user_id=? AND status='pending' ORDER BY reported_at DESC LIMIT 5", (user_id,))
    recent_maintenance_requests = c.fetchall()
    
    c.execute("SELECT id, bin_type, quantity, status, requested_at FROM purchase_requests WHERE user_id=? AND status='pending' ORDER BY requested_at DESC LIMIT 5", (user_id,))
    recent_purchases = c.fetchall()
    
    conn.close()
    return render_template('user_dashboard.html', 
                         notifications_count=notifications_count, 
                         collected_count=collected_count, 
                         pending_count=pending_count,
                         recent_notifications=recent_notifications,
                         recent_messages=recent_messages,
                         recent_maintenance_requests=recent_maintenance_requests,
                         recent_purchases=recent_purchases)

@app.route('/clear_messages', methods=['POST'])
def clear_messages():
    if 'username' not in session or session['role'] != 'user':
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username=?", (session['username'],))
    user_id = c.fetchone()[0]
    
    c.execute("DELETE FROM messages WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('user_dashboard'))

@app.route('/add_notification', methods=['GET', 'POST'])
def add_notification():
    if 'username' not in session or session['role'] != 'user':
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username=?", (session['username'],))
    user_id = c.fetchone()[0]
    
    if request.method == 'POST':
        location = request.form['location']
        latitude = float(request.form['latitude'])
        longitude = float(request.form['longitude'])
        fill_percentage = float(request.form['fill_percentage'])
        is_full = 1 if fill_percentage >= 90 else 0
        
        c.execute("INSERT INTO trash_bins (user_id, location, latitude, longitude, fill_percentage, is_full, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (user_id, location, latitude, longitude, fill_percentage, is_full, 'pending'))
        conn.commit()
        conn.close()
        return redirect(url_for('user_dashboard'))
    
    conn.close()
    return render_template('add_notification.html')

@app.route('/delete_notification/<int:notif_id>', methods=['POST'])
def delete_notification(notif_id):
    if 'username' not in session or session['role'] != 'user':
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username=?", (session['username'],))
    user_id = c.fetchone()[0]
    
    c.execute("DELETE FROM trash_bins WHERE id=? AND user_id=?", (notif_id, user_id))
    conn.commit()
    conn.close()
    return redirect(url_for('user_dashboard'))

@app.route('/edit_notification/<int:notif_id>', methods=['GET', 'POST'])
def edit_notification(notif_id):
    if 'username' not in session or session['role'] != 'user':
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username=?", (session['username'],))
    user_id = c.fetchone()[0]
    
    if request.method == 'POST':
        location = request.form['location']
        latitude = float(request.form['latitude'])
        longitude = float(request.form['longitude'])
        fill_percentage = float(request.form['fill_percentage'])
        is_full = 1 if fill_percentage >= 90 else 0
        
        c.execute("UPDATE trash_bins SET location=?, latitude=?, longitude=?, fill_percentage=?, is_full=? WHERE id=? AND user_id=?",
                  (location, latitude, longitude, fill_percentage, is_full, notif_id, user_id))
        conn.commit()
        conn.close()
        return redirect(url_for('user_dashboard'))
    
    c.execute("SELECT location, latitude, longitude, fill_percentage FROM trash_bins WHERE id=? AND user_id=?", (notif_id, user_id))
    notification = c.fetchone()
    conn.close()
    
    if notification:
        return render_template('edit_notification.html', notification=notification, notif_id=notif_id)
    return redirect(url_for('user_dashboard'))

@app.route('/request_maintenance', methods=['GET', 'POST'])
def request_maintenance():
    if 'username' not in session or session['role'] != 'user':
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username=?", (session['username'],))
    user_id = c.fetchone()[0]
    
    if request.method == 'POST':
        location = request.form['location']
        latitude = float(request.form['latitude'])
        longitude = float(request.form['longitude'])
        problem_type = request.form['problem_type']
        description = request.form['description']
        
        image_path = None
        if 'image' in request.files:
            file = request.files['image']
            if file.filename != '':
                filename = f"{user_id}_{file.filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_path = f"uploads/{filename}"
        
        c.execute("INSERT INTO maintenance_requests (user_id, location, latitude, longitude, problem_type, description, image_path, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                  (user_id, location, latitude, longitude, problem_type, description, image_path, 'pending'))
        conn.commit()
        conn.close()
        return redirect(url_for('user_dashboard'))
    
    conn.close()
    return render_template('request_maintenance.html')

@app.route('/delete_maintenance/<int:request_id>', methods=['POST'])
def delete_maintenance(request_id):
    if 'username' not in session or session['role'] != 'user':
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username=?", (session['username'],))
    user_id = c.fetchone()[0]
    
    c.execute("DELETE FROM maintenance_requests WHERE id=? AND user_id=?", (request_id, user_id))
    conn.commit()
    conn.close()
    return redirect(url_for('user_dashboard'))

@app.route('/edit_maintenance/<int:request_id>', methods=['GET', 'POST'])
def edit_maintenance(request_id):
    if 'username' not in session or session['role'] != 'user':
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username=?", (session['username'],))
    user_id = c.fetchone()[0]
    
    if request.method == 'POST':
        location = request.form['location']
        latitude = float(request.form['latitude'])
        longitude = float(request.form['longitude'])
        problem_type = request.form['problem_type']
        description = request.form['description']
        
        image_path = None
        if 'image' in request.files:
            file = request.files['image']
            if file.filename != '':
                filename = f"{user_id}_{file.filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_path = f"uploads/{filename}"
        
        if image_path:
            c.execute("UPDATE maintenance_requests SET location=?, latitude=?, longitude=?, problem_type=?, description=?, image_path=? WHERE id=? AND user_id=?",
                      (location, latitude, longitude, problem_type, description, image_path, request_id, user_id))
        else:
            c.execute("UPDATE maintenance_requests SET location=?, latitude=?, longitude=?, problem_type=?, description=? WHERE id=? AND user_id=?",
                      (location, latitude, longitude, problem_type, description, request_id, user_id))
        conn.commit()
        conn.close()
        return redirect(url_for('user_dashboard'))
    
    c.execute("SELECT location, latitude, longitude, problem_type, description, image_path FROM maintenance_requests WHERE id=? AND user_id=?", (request_id, user_id))
    maintenance_request = c.fetchone()
    conn.close()
    
    if maintenance_request:
        return render_template('edit_maintenance.html', request=maintenance_request, request_id=request_id)
    return redirect(url_for('user_dashboard'))

@app.route('/buy_trash_bin', methods=['GET', 'POST'])
def buy_trash_bin():
    if 'username' not in session or session['role'] != 'user':
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username=?", (session['username'],))
    user_id = c.fetchone()[0]
    
    if request.method == 'POST':
        bin_type = request.form['bin_type']
        quantity = int(request.form['quantity'])
        delivery_address = request.form['delivery_address']
        latitude = float(request.form['latitude'])
        longitude = float(request.form['longitude'])
        
        c.execute("INSERT INTO purchase_requests (user_id, bin_type, quantity, delivery_address, latitude, longitude, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (user_id, bin_type, quantity, delivery_address, latitude, longitude, 'pending'))
        conn.commit()
        conn.close()
        return redirect(url_for('user_dashboard'))
    
    conn.close()
    return render_template('buy_trash_bin.html')

@app.route('/delete_purchase/<int:purchase_id>', methods=['POST'])
def delete_purchase(purchase_id):
    if 'username' not in session or session['role'] != 'user':
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username=?", (session['username'],))
    user_id = c.fetchone()[0]
    
    c.execute("DELETE FROM purchase_requests WHERE id=? AND user_id=?", (purchase_id, user_id))
    conn.commit()
    conn.close()
    return redirect(url_for('user_dashboard'))

@app.route('/edit_purchase/<int:purchase_id>', methods=['GET', 'POST'])
def edit_purchase(purchase_id):
    if 'username' not in session or session['role'] != 'user':
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username=?", (session['username'],))
    user_id = c.fetchone()[0]
    
    if request.method == 'POST':
        bin_type = request.form['bin_type']
        quantity = int(request.form['quantity'])
        delivery_address = request.form['delivery_address']
        latitude = float(request.form['latitude'])
        longitude = float(request.form['longitude'])
        
        c.execute("UPDATE purchase_requests SET bin_type=?, quantity=?, delivery_address=?, latitude=?, longitude=? WHERE id=? AND user_id=?",
                  (bin_type, quantity, delivery_address, latitude, longitude, purchase_id, user_id))
        conn.commit()
        conn.close()
        return redirect(url_for('user_dashboard'))
    
    c.execute("SELECT bin_type, quantity, delivery_address, latitude, longitude FROM purchase_requests WHERE id=? AND user_id=?", (purchase_id, user_id))
    purchase = c.fetchone()
    conn.close()
    
    if purchase:
        return render_template('edit_purchase.html', purchase=purchase, purchase_id=purchase_id)
    return redirect(url_for('user_dashboard'))

@app.route('/update_location', methods=['POST'])
def update_location():
    if 'username' not in session or session['role'] != 'driver':
        return redirect(url_for('login'))
    
    latitude = float(request.form['latitude'])
    longitude = float(request.form['longitude'])
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("UPDATE users SET current_latitude=?, current_longitude=? WHERE username=?",
              (latitude, longitude, session['username']))
    conn.commit()
    conn.close()
    
    return redirect(url_for('driver_dashboard'))

@app.route('/driver_dashboard')
def driver_dashboard():
    if 'username' not in session or session['role'] != 'driver':
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    # Get driver's info
    c.execute("SELECT id, current_latitude, current_longitude, points, promotion FROM users WHERE username=?", (session['username'],))
    driver_info = c.fetchone()
    driver_id = driver_info[0]  # Get the driver's ID
    if not driver_info or (driver_info[1] == 0.0 and driver_info[2] == 0.0):
        current_pos = (30.0444, 31.2357)  # Default to Cairo
    else:
        current_pos = (driver_info[1], driver_info[2])
    driver_points = driver_info[3]
    driver_promotion = driver_info[4]
    
    # Fetch approved tasks for this driver only
    c.execute("SELECT id, location, latitude, longitude, fill_percentage, reported_at FROM trash_bins WHERE status='approved' AND assigned_driver_id=?", (driver_id,))
    approved_trash_bins = c.fetchall()
    c.execute("SELECT id, location, latitude, longitude, problem_type, reported_at FROM maintenance_requests WHERE status='approved' AND assigned_driver_id=?", (driver_id,))
    approved_maintenance = c.fetchall()
    c.execute("SELECT id, delivery_address AS location, latitude, longitude, bin_type, requested_at FROM purchase_requests WHERE status='approved' AND assigned_driver_id=?", (driver_id,))
    approved_purchases = c.fetchall()
    
    # Statistics
    trash_count = len(approved_trash_bins)
    maintenance_count = len(approved_maintenance)
    purchase_count = len(approved_purchases)
    total_tasks = trash_count + maintenance_count + purchase_count
    
    conn.close()
    
    # Combine all locations
    locations = (
        [{'id': tb[0], 'type': 'trash_bin', 'location': tb[1], 'latitude': tb[2], 'longitude': tb[3], 'details': f"Fill: {tb[4]}%", 'date': tb[5]} for tb in approved_trash_bins] +
        [{'id': m[0], 'type': 'maintenance', 'location': m[1], 'latitude': m[2], 'longitude': m[3], 'details': f"Problem: {m[4]}", 'date': m[5]} for m in approved_maintenance] +
        [{'id': p[0], 'type': 'purchase', 'location': p[1], 'latitude': p[2], 'longitude': p[3], 'details': f"Bin: {p[4]}", 'date': p[5]} for p in approved_purchases]
    )
    
    # Nearest Neighbor for TSP
    if locations:
        sorted_locations = []
        unvisited = locations.copy()
        current = current_pos
        
        while unvisited:
            nearest = min(unvisited, key=lambda x: haversine(current[0], current[1], x['latitude'], x['longitude']))
            sorted_locations.append(nearest)
            current = (nearest['latitude'], nearest['longitude'])
            unvisited.remove(nearest)
    else:
        sorted_locations = []
    
    return render_template('driver_dashboard.html', 
                         locations=locations, 
                         sorted_locations=sorted_locations,
                         total_tasks=total_tasks,
                         trash_count=trash_count,
                         maintenance_count=maintenance_count,
                         purchase_count=purchase_count,
                         driver_lat=current_pos[0],
                         driver_lon=current_pos[1],
                         driver_points=driver_points,
                         driver_promotion=driver_promotion)

@app.route('/complete_task/<task_type>/<int:task_id>', methods=['POST'])
def complete_task(task_type, task_id):
    if 'username' not in session or session['role'] != 'driver':
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    # Get driver ID
    c.execute("SELECT id FROM users WHERE username=?", (session['username'],))
    driver_id = c.fetchone()[0]
    
    # Points for each task type
    points_map = {
        'trash_bin': 10,
        'maintenance': 15,
        'purchase': 20
    }
    
    if task_type == 'trash_bin':
        c.execute("UPDATE trash_bins SET status='completed' WHERE id=? AND assigned_driver_id=?", (task_id, driver_id))
        c.execute("SELECT user_id, location FROM trash_bins WHERE id=?", (task_id,))
        task = c.fetchone()
        message = f"Driver {session['username']} collected the trash at {task[1]}"
    elif task_type == 'maintenance':
        c.execute("UPDATE maintenance_requests SET status='completed' WHERE id=? AND assigned_driver_id=?", (task_id, driver_id))
        c.execute("SELECT user_id, location FROM maintenance_requests WHERE id=?", (task_id,))
        task = c.fetchone()
        message = f"Maintenance at {task[1]} marked as completed by driver {session['username']}"
    elif task_type == 'purchase':
        c.execute("UPDATE purchase_requests SET status='completed' WHERE id=? AND assigned_driver_id=?", (task_id, driver_id))
        c.execute("SELECT user_id, delivery_address FROM purchase_requests WHERE id=?", (task_id,))
        task = c.fetchone()
        message = f"Purchase delivery to {task[1]} marked as completed by driver {session['username']}"
    else:
        conn.close()
        return redirect(url_for('driver_dashboard'))
    
    # Add points to driver
    if task_type in points_map:
        points = points_map[task_type]
        c.execute("UPDATE users SET points = points + ? WHERE id=?", (points, driver_id))
        
        # Update promotion based on points
        c.execute("SELECT points FROM users WHERE id=?", (driver_id,))
        total_points = c.fetchone()[0]
        if total_points >= 500:
            new_promotion = 'Legend Driver'
        elif total_points >= 250:
            new_promotion = 'Pro Driver'
        elif total_points >= 100:
            new_promotion = 'Active Driver'
        else:
            new_promotion = 'New Driver'
        
        c.execute("UPDATE users SET promotion=? WHERE id=?", (new_promotion, driver_id))
        
        # Send notification if promotion changed
        c.execute("SELECT promotion FROM users WHERE id=?", (driver_id,))
        current_promotion = c.fetchone()[0]
        if current_promotion != new_promotion:
            c.execute("INSERT INTO messages (user_id, message, status) VALUES (?, ?, ?)",
                      (driver_id, f"Congratulations! You've been promoted to {new_promotion}!", 'unread'))
    
    # Send message to admin
    c.execute("SELECT id FROM users WHERE role='admin' LIMIT 1")
    admin_id = c.fetchone()[0]
    c.execute("INSERT INTO messages (user_id, message, status) VALUES (?, ?, ?)",
              (admin_id, message, 'unread'))
    
    # Send confirmation to user
    c.execute("INSERT INTO messages (user_id, message, status) VALUES (?, ?, ?)",
              (task[0], f"Your {task_type.replace('_', ' ')} request has been completed.", 'unread'))
    
    conn.commit()
    conn.close()
    return redirect(url_for('driver_dashboard'))

@app.route('/start_task/<task_type>/<int:task_id>', methods=['POST'])
def start_task(task_type, task_id):
    if 'username' not in session or session['role'] != 'driver':
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    if task_type == 'trash_bin':
        c.execute("UPDATE trash_bins SET status='in_progress' WHERE id=?", (task_id,))
    elif task_type == 'maintenance':
        c.execute("UPDATE maintenance_requests SET status='in_progress' WHERE id=?", (task_id,))
    elif task_type == 'purchase':
        c.execute("UPDATE purchase_requests SET status='in_progress' WHERE id=?", (task_id,))
    
    conn.commit()
    conn.close()
    return redirect(url_for('driver_routes'))

@app.route('/driver_routes')
def driver_routes():
    if 'username' not in session or session['role'] != 'driver':
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    # Get driver's ID and current location
    c.execute("SELECT id, current_latitude, current_longitude FROM users WHERE username=?", (session['username'],))
    driver_info = c.fetchone()
    driver_id, driver_lat, driver_lon = driver_info
    current_pos = (driver_lat, driver_lon) if driver_lat and driver_lon else (30.0444, 31.2357)  # Default to Cairo
    
    # Fetch tasks assigned to this driver only
    c.execute("SELECT id, location, latitude, longitude, fill_percentage, reported_at, status FROM trash_bins WHERE assigned_driver_id=? AND status IN ('approved', 'in_progress', 'completed')", (driver_id,))
    trash_bins = c.fetchall()
    c.execute("SELECT id, location, latitude, longitude, problem_type, reported_at, status FROM maintenance_requests WHERE assigned_driver_id=? AND status IN ('approved', 'in_progress', 'completed')", (driver_id,))
    maintenance = c.fetchall()
    c.execute("SELECT id, delivery_address AS location, latitude, longitude, bin_type, requested_at, status FROM purchase_requests WHERE assigned_driver_id=? AND status IN ('approved', 'in_progress', 'completed')", (driver_id,))
    purchases = c.fetchall()
    
    conn.close()
    
    # Combine all tasks
    all_tasks = (
        [{'id': tb[0], 'type': 'trash_bin', 'location': tb[1], 'latitude': tb[2], 'longitude': tb[3], 'details': f"Fill: {tb[4]}%", 'date': tb[5], 'status': tb[6]} for tb in trash_bins] +
        [{'id': m[0], 'type': 'maintenance', 'location': m[1], 'latitude': m[2], 'longitude': m[3], 'details': f"Problem: {m[4]}", 'date': m[5], 'status': m[6]} for m in maintenance] +
        [{'id': p[0], 'type': 'purchase', 'location': p[1], 'latitude': p[2], 'longitude': p[3], 'details': f"Bin: {p[4]}", 'date': p[5], 'status': p[6]} for p in purchases]
    )
    
    # Nearest Neighbor for sorted route
    if all_tasks:
        sorted_locations = []
        unvisited = all_tasks.copy()
        current = current_pos
        
        while unvisited:
            nearest = min(unvisited, key=lambda x: haversine(current[0], current[1], x['latitude'], x['longitude']))
            sorted_locations.append(nearest)
            current = (nearest['latitude'], nearest['longitude'])
            unvisited.remove(nearest)
    else:
        sorted_locations = []
    
    return render_template('driver_routes.html', 
                         sorted_locations=sorted_locations,
                         driver_lat=current_pos[0],
                         driver_lon=current_pos[1])

@app.route('/admin_dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    # Counts
    c.execute("SELECT COUNT(*) FROM users WHERE role='driver'")
    drivers_count = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM users WHERE role='user'")
    users_count = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM users WHERE role='admin'")
    admins_count = c.fetchone()[0]
    
    # Calculate total pending requests for trash bins card
    c.execute("SELECT COUNT(*) FROM trash_bins WHERE status='pending'")
    trash_notifications_count = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM purchase_requests WHERE status='pending'")
    purchase_requests_count = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM maintenance_requests WHERE status='pending'")
    maintenance_requests_count = c.fetchone()[0]
    
    trash_count = trash_notifications_count + purchase_requests_count + maintenance_requests_count
    
    # Recent drivers
    c.execute("SELECT fullname, username FROM users WHERE role='driver' ORDER BY id DESC LIMIT 5")
    recent_drivers = c.fetchall() or []
    
    # Pending requests
    requests_per_page = session.get('requests_per_page', 5)
    c.execute("SELECT id, user_id, bin_type, quantity, delivery_address, latitude, longitude, status, requested_at FROM purchase_requests WHERE status='pending' ORDER BY requested_at DESC LIMIT ?", (requests_per_page,))
    pending_purchases = c.fetchall() or []
    
    # Notifications from users (user_id is not NULL)
    c.execute("SELECT id, user_id, location, fill_percentage, latitude, longitude, status, reported_at FROM trash_bins WHERE status='pending' AND user_id IS NOT NULL ORDER BY reported_at DESC LIMIT ?", (requests_per_page,))
    pending_notifications = c.fetchall() or []

# Notifications from Arduino (user_id is NULL)
    c.execute("SELECT id, user_id, location, fill_percentage, latitude, longitude, status, reported_at FROM trash_bins WHERE status='pending' AND user_id IS NULL ORDER BY reported_at DESC LIMIT ?", (requests_per_page,))
    arduino_notifications = c.fetchall() or []
    
    c.execute("SELECT id, user_id, location, problem_type, latitude, longitude, status, reported_at FROM maintenance_requests WHERE status='pending' ORDER BY reported_at DESC LIMIT ?", (requests_per_page,))
    pending_maintenance_requests = c.fetchall() or []
    
    # Recent messages for admin
    c.execute("SELECT id FROM users WHERE username=?", (session['username'],))
    admin_id = c.fetchone()[0]
    c.execute("SELECT message, created_at FROM messages WHERE user_id=? ORDER BY created_at DESC LIMIT 5", (admin_id,))
    recent_messages = c.fetchall() or []
    
    # Search functionality
    search_results = []
    if request.method == 'POST' and 'search' in request.form:
        search_query = request.form.get('search', '').strip()
        if search_query:
            c.execute("SELECT fullname, username, email, role FROM users WHERE role IN ('user', 'driver', 'admin') AND (fullname LIKE ? OR username LIKE ?)",
                      (f'%{search_query}%', f'%{search_query}%'))
            search_results = c.fetchall() or []
    
    # Combine all pending locations for map (optional)
    locations = (
        [{'id': tb[0], 'type': 'trash_bin', 'location': tb[2], 'latitude': tb[4], 'longitude': tb[5], 'details': f"Fill: {tb[3]}%", 'date': tb[7]} for tb in pending_notifications] +
        [{'id': m[0], 'type': 'maintenance', 'location': m[2], 'latitude': m[4], 'longitude': m[5], 'details': f"Problem: {m[3]}", 'date': m[7]} for m in pending_maintenance_requests] +
        [{'id': p[0], 'type': 'purchase', 'location': p[4], 'latitude': p[5], 'longitude': p[6], 'details': f"Bin: {p[2]}, Qty: {p[3]}", 'date': p[8]} for p in pending_purchases]
    )
    
    conn.close()
    
    return render_template('admin_dashboard.html', 
                     drivers_count=drivers_count, 
                     users_count=users_count, 
                     admins_count=admins_count, 
                     trash_count=trash_count, 
                     recent_drivers=recent_drivers, 
                     search_results=search_results,
                     pending_purchases=pending_purchases,
                     pending_notifications=pending_notifications,
                     pending_maintenance_requests=pending_maintenance_requests,
                     recent_messages=recent_messages,
                     locations=locations,
                     arduino_notifications=arduino_notifications)  # Add this

@app.route('/clear_admin_messages', methods=['POST'])
def clear_admin_messages():
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username=?", (session['username'],))
    admin_id = c.fetchone()[0]
    
    c.execute("DELETE FROM messages WHERE user_id=?", (admin_id,))
    conn.commit()
    conn.close()
    
    return redirect(url_for('admin_dashboard'))

@app.route('/approve_notification/<int:notif_id>', methods=['POST'])
def approve_notification(notif_id):
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    # Fetch task details
    c.execute("SELECT user_id, location, fill_percentage, latitude, longitude FROM trash_bins WHERE id=?", (notif_id,))
    notification = c.fetchone()
    if not notification:
        print(f"Notification {notif_id} not found!")
        conn.close()
        return redirect(url_for('admin_dashboard'))
    
    user_id, location, fill_percentage, latitude, longitude = notification
    print(f"Approving notification {notif_id} at {location}")
    
    # Fetch all drivers and their task counts
    c.execute("SELECT id, username, current_latitude, current_longitude FROM users WHERE role='driver'")
    drivers = c.fetchall()
    if not drivers:
        print("No drivers found!")
        conn.close()
        return redirect(url_for('admin_dashboard'))
    
    # Choose the best driver (closest with least tasks)
    assigned_driver_id = None
    min_score = float('inf')
    for driver in drivers:
        driver_id, driver_username, driver_lat, driver_lon = driver
        # Skip drivers with invalid location (e.g., 0.0, 0.0)
        if not driver_lat or not driver_lon or (driver_lat == 0.0 and driver_lon == 0.0):
            print(f"Skipping driver {driver_username}: No valid location (lat={driver_lat}, lon={driver_lon})")
            continue
        
        # Calculate distance
        distance = haversine(latitude, longitude, driver_lat, driver_lon)
        
        # Count total active tasks for this driver across all types
        c.execute("""
            SELECT COUNT(*) FROM (
                SELECT id FROM trash_bins WHERE assigned_driver_id=? AND status IN ('approved', 'in_progress')
                UNION ALL
                SELECT id FROM maintenance_requests WHERE assigned_driver_id=? AND status IN ('approved', 'in_progress')
                UNION ALL
                SELECT id FROM purchase_requests WHERE assigned_driver_id=? AND status IN ('approved', 'in_progress')
            ) AS active_tasks
        """, (driver_id, driver_id, driver_id))
        task_count = c.fetchone()[0]
        
        # Adjusted scoring: Prioritize distance more, but penalize high task counts
        score = distance + (task_count * 5)  # Reduced multiplier to prioritize proximity
        print(f"Driver {driver_username} - Distance: {distance:.2f} km, Tasks: {task_count}, Score: {score:.2f}")
        
        if score < min_score:
            min_score = score
            assigned_driver_id = driver_id
    
    if assigned_driver_id:
        print(f"Assigning to driver ID {assigned_driver_id}")
        # Assign task to driver
        c.execute("UPDATE trash_bins SET status='approved', assigned_driver_id=? WHERE id=?", (assigned_driver_id, notif_id))
        c.execute("INSERT INTO messages (user_id, message, status) VALUES (?, ?, ?)",
                  (user_id, f"Your notification for trash bin at {location} (Fill: {fill_percentage}%) has been approved.", 'unread'))
        c.execute("INSERT INTO messages (user_id, message, status) VALUES (?, ?, ?)",
                  (assigned_driver_id, f"New task assigned: Collect trash bin at {location}.", 'unread'))
        c.execute("SELECT id FROM users WHERE username=?", (session['username'],))
        admin_id = c.fetchone()[0]
        c.execute("INSERT INTO messages (user_id, message, status) VALUES (?, ?, ?)",
                  (admin_id, f"Admin Activity: Approved notification ID {notif_id} and assigned to driver {assigned_driver_id}", 'unread'))
        conn.commit()
        print(f"Notification {notif_id} approved and assigned!")
    else:
        print("No suitable driver found with valid location and capacity!")
        # Optionally notify admin of failure to assign
        c.execute("SELECT id FROM users WHERE username=?", (session['username'],))
        admin_id = c.fetchone()[0]
        c.execute("INSERT INTO messages (user_id, message, status) VALUES (?, ?, ?)",
                  (admin_id, f"Admin Activity: Failed to assign notification ID {notif_id} - No suitable driver found", 'unread'))
        # تحديث حالة السلة في "el tarf" إلى "approved"
        if location == "el tarf":
         bin_status["el tarf"] = "approved"
         conn.commit()
    
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/reject_notification/<int:notif_id>', methods=['POST'])
def reject_notification(notif_id):
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    c.execute("SELECT user_id, location, fill_percentage FROM trash_bins WHERE id=?", (notif_id,))
    notification = c.fetchone()
    if notification:
        user_id, location, fill_percentage = notification
        c.execute("DELETE FROM trash_bins WHERE id=?", (notif_id,))
        c.execute("INSERT INTO messages (user_id, message, status) VALUES (?, ?, ?)",
                  (user_id, f"Your notification for trash bin at {location} (Fill: {fill_percentage}%) has been rejected.", 'unread'))
        c.execute("SELECT id FROM users WHERE username=?", (session['username'],))
        admin_id = c.fetchone()[0]
        c.execute("INSERT INTO messages (user_id, message, status) VALUES (?, ?, ?)",
                  (admin_id, f"Admin Activity: Rejected notification ID {notif_id} for user {user_id}", 'unread'))
         # تحديث حالة السلة في "el tarf" إلى "rejected"
        if location == "el tarf":
         bin_status["el tarf"] = "rejected"
        conn.commit()
    
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/approve_purchase/<int:purchase_id>', methods=['POST'])
def approve_purchase(purchase_id):
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    c.execute("SELECT user_id, bin_type, quantity, delivery_address, latitude, longitude FROM purchase_requests WHERE id=?", (purchase_id,))
    purchase = c.fetchone()
    if purchase:
        user_id, bin_type, quantity, delivery_address, latitude, longitude = purchase
        
        # حاول تجيب سايق مناسب
        c.execute("SELECT id, username, current_latitude, current_longitude FROM users WHERE role='driver'")
        drivers = c.fetchall()
        
        assigned_driver_id = None
        min_score = float('inf')
        for driver in drivers:
            driver_id, _, driver_lat, driver_lon = driver
            if driver_lat and driver_lon:  # تأكد إن الموقع موجود
                distance = haversine(latitude, longitude, driver_lat, driver_lon)
                c.execute("SELECT COUNT(*) FROM purchase_requests WHERE assigned_driver_id=? AND status IN ('approved', 'in_progress')", (driver_id,))
                task_count = c.fetchone()[0]
                score = distance + (task_count * 10)
                if score < min_score:
                    min_score = score
                    assigned_driver_id = driver_id
        
        # حدث الحالة بغض النظر عن وجود سايق
        if assigned_driver_id:
            c.execute("UPDATE purchase_requests SET status='approved', assigned_driver_id=? WHERE id=?", (assigned_driver_id, purchase_id))
            c.execute("INSERT INTO messages (user_id, message, status) VALUES (?, ?, ?)",
                      (assigned_driver_id, f"New task assigned: Deliver {quantity} {bin_type} bin(s) to {delivery_address}.", 'unread'))
        else:
            c.execute("UPDATE purchase_requests SET status='approved' WHERE id=?", (purchase_id,))
            print(f"No suitable driver found for purchase ID {purchase_id}")
        
        # إرسال رسايل
        c.execute("INSERT INTO messages (user_id, message, status) VALUES (?, ?, ?)",
                  (user_id, f"Your request to purchase {quantity} {bin_type} trash bin(s) has been approved.", 'unread'))
        c.execute("SELECT id FROM users WHERE username=?", (session['username'],))
        admin_id = c.fetchone()[0]
        c.execute("INSERT INTO messages (user_id, message, status) VALUES (?, ?, ?)",
                  (admin_id, f"Admin Activity: Approved purchase ID {purchase_id}", 'unread'))
        conn.commit()
    else:
        print(f"Purchase ID {purchase_id} not found!")
    
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/reject_purchase/<int:purchase_id>', methods=['POST'])
def reject_purchase(purchase_id):
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    c.execute("SELECT user_id, bin_type, quantity FROM purchase_requests WHERE id=?", (purchase_id,))
    purchase = c.fetchone()
    if purchase:
        user_id, bin_type, quantity = purchase
        c.execute("DELETE FROM purchase_requests WHERE id=?", (purchase_id,))
        c.execute("INSERT INTO messages (user_id, message, status) VALUES (?, ?, ?)",
                  (user_id, f"Your request to purchase {quantity} {bin_type} trash bin(s) has been rejected.", 'unread'))
        c.execute("SELECT id FROM users WHERE username=?", (session['username'],))
        admin_id = c.fetchone()[0]
        c.execute("INSERT INTO messages (user_id, message, status) VALUES (?, ?, ?)",
                  (admin_id, f"Admin Activity: Rejected purchase ID {purchase_id} for user {user_id}", 'unread'))
        conn.commit()
    
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/approve_maintenance/<int:request_id>', methods=['POST'])
def approve_maintenance(request_id):
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    c.execute("SELECT user_id, location, problem_type, latitude, longitude FROM maintenance_requests WHERE id=?", (request_id,))
    maintenance = c.fetchone()
    if maintenance:
        user_id, location, problem_type, latitude, longitude = maintenance
        
        # حاول تجيب سايق مناسب
        c.execute("SELECT id, username, current_latitude, current_longitude FROM users WHERE role='driver'")
        drivers = c.fetchall()
        
        assigned_driver_id = None
        min_score = float('inf')
        for driver in drivers:
            driver_id, _, driver_lat, driver_lon = driver
            if driver_lat and driver_lon:  # تأكد إن الموقع موجود
                distance = haversine(latitude, longitude, driver_lat, driver_lon)
                c.execute("SELECT COUNT(*) FROM maintenance_requests WHERE assigned_driver_id=? AND status IN ('approved', 'in_progress')", (driver_id,))
                task_count = c.fetchone()[0]
                score = distance + (task_count * 10)
                if score < min_score:
                    min_score = score
                    assigned_driver_id = driver_id
        
        # حدث الحالة بغض النظر عن وجود سايق
        if assigned_driver_id:
            c.execute("UPDATE maintenance_requests SET status='approved', assigned_driver_id=? WHERE id=?", (assigned_driver_id, request_id))
            c.execute("INSERT INTO messages (user_id, message, status) VALUES (?, ?, ?)",
                      (assigned_driver_id, f"New task assigned: Maintenance at {location} (Problem: {problem_type}).", 'unread'))
        else:
            c.execute("UPDATE maintenance_requests SET status='approved' WHERE id=?", (request_id,))
            print(f"No suitable driver found for maintenance ID {request_id}")
        
        # إرسال رسايل
        c.execute("INSERT INTO messages (user_id, message, status) VALUES (?, ?, ?)",
                  (user_id, f"Your maintenance request for {location} (Problem: {problem_type}) has been approved.", 'unread'))
        c.execute("SELECT id FROM users WHERE username=?", (session['username'],))
        admin_id = c.fetchone()[0]
        c.execute("INSERT INTO messages (user_id, message, status) VALUES (?, ?, ?)",
                  (admin_id, f"Admin Activity: Approved maintenance request ID {request_id}", 'unread'))
        conn.commit()
    else:
        print(f"Maintenance ID {request_id} not found!")
    
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/reject_maintenance/<int:request_id>', methods=['POST'])
def reject_maintenance(request_id):
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    c.execute("SELECT user_id, location, problem_type FROM maintenance_requests WHERE id=?", (request_id,))
    maintenance = c.fetchone()
    if maintenance:
        user_id, location, problem_type = maintenance
        c.execute("DELETE FROM maintenance_requests WHERE id=?", (request_id,))
        c.execute("INSERT INTO messages (user_id, message, status) VALUES (?, ?, ?)",
                  (user_id, f"Your maintenance request for {location} (Problem: {problem_type}) has been rejected.", 'unread'))
        c.execute("SELECT id FROM users WHERE username=?", (session['username'],))
        admin_id = c.fetchone()[0]
        c.execute("INSERT INTO messages (user_id, message, status) VALUES (?, ?, ?)",
                  (admin_id, f"Admin Activity: Rejected maintenance request ID {request_id} for user {user_id}", 'unread'))
        conn.commit()
    
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/driver_management', methods=['GET', 'POST'])
def driver_management():
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    if request.method == 'POST' and 'add_driver' in request.form:
        fullname = request.form['fullname']
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        c.execute("INSERT INTO users (fullname, username, email, password, role, current_latitude, current_longitude, points, promotion) VALUES (?, ?, ?, ?, 'driver', ?, ?, ?, ?)",
                  (fullname, username, email, password, 0.0, 0.0, 0, 'New Driver'))
        c.execute("SELECT id FROM users WHERE username=?", (session['username'],))
        admin_id = c.fetchone()[0]
        c.execute("INSERT INTO messages (user_id, message, status) VALUES (?, ?, ?)",
                  (admin_id, f"Admin Activity: Added new driver {username}", 'unread'))
        conn.commit()
    
    # Fetch drivers with points and promotion
    c.execute("SELECT id, fullname, username, email, points, promotion FROM users WHERE role='driver'")
    drivers = c.fetchall()
    
    conn.close()
    
    return render_template('driver_management.html', drivers=drivers)

@app.route('/edit_driver/<int:driver_id>', methods=['GET', 'POST'])
def edit_driver(driver_id):
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    if request.method == 'POST':
        fullname = request.form['fullname']
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        points = int(request.form['points'])
        promotion = request.form['promotion']
        c.execute("UPDATE users SET fullname=?, username=?, email=?, password=?, points=?, promotion=? WHERE id=? AND role='driver'",
                  (fullname, username, email, password, points, promotion, driver_id))
        c.execute("SELECT id FROM users WHERE username=?", (session['username'],))
        admin_id = c.fetchone()[0]
        c.execute("INSERT INTO messages (user_id, message, status) VALUES (?, ?, ?)",
                  (admin_id, f"Admin Activity: Edited driver ID {driver_id}", 'unread'))
        conn.commit()
        conn.close()
        return redirect(url_for('driver_management'))
    
    c.execute("SELECT fullname, username, email, password, points, promotion FROM users WHERE id=? AND role='driver'", (driver_id,))
    driver = c.fetchone()
    conn.close()
    
    if driver:
        return render_template('edit_driver.html', driver=driver, driver_id=driver_id)
    return redirect(url_for('driver_management'))

@app.route('/delete_driver/<int:driver_id>', methods=['POST'])
def delete_driver(driver_id):
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT username FROM users WHERE id=? AND role='driver'", (driver_id,))
    driver_username = c.fetchone()[0]
    c.execute("DELETE FROM users WHERE id=? AND role='driver'", (driver_id,))
    c.execute("SELECT id FROM users WHERE username=?", (session['username'],))
    admin_id = c.fetchone()[0]
    c.execute("INSERT INTO messages (user_id, message, status) VALUES (?, ?, ?)",
              (admin_id, f"Admin Activity: Deleted driver {driver_username}", 'unread'))
    conn.commit()
    conn.close()
    
    return redirect(url_for('driver_management'))

@app.route('/users_management', methods=['GET', 'POST'])
def users_management():
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    if request.method == 'POST' and 'add_user' in request.form:
        fullname = request.form['fullname']
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        c.execute("INSERT INTO users (fullname, username, email, password, role, current_latitude, current_longitude) VALUES (?, ?, ?, ?, 'user', ?, ?)",
                  (fullname, username, email, password, 0.0, 0.0))
        c.execute("SELECT id FROM users WHERE username=?", (session['username'],))
        admin_id = c.fetchone()[0]
        c.execute("INSERT INTO messages (user_id, message, status) VALUES (?, ?, ?)",
                  (admin_id, f"Admin Activity: Added new user {username}", 'unread'))
        conn.commit()
    
    c.execute("SELECT id, fullname, username, email FROM users WHERE role='user'")
    users = c.fetchall()
    
    conn.close()
    
    return render_template('users_management.html', users=users)

@app.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
def edit_user(user_id):
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    if request.method == 'POST':
        fullname = request.form['fullname']
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        c.execute("UPDATE users SET fullname=?, username=?, email=?, password=? WHERE id=? AND role='user'",
                  (fullname, username, email, password, user_id))
        c.execute("SELECT id FROM users WHERE username=?", (session['username'],))
        admin_id = c.fetchone()[0]
        c.execute("INSERT INTO messages (user_id, message, status) VALUES (?, ?, ?)",
                  (admin_id, f"Admin Activity: Edited user ID {user_id}", 'unread'))
        conn.commit()
        conn.close()
        return redirect(url_for('users_management'))
    
    c.execute("SELECT fullname, username, email, password FROM users WHERE id=? AND role='user'", (user_id,))
    user = c.fetchone()
    conn.close()
    
    if user:
        return render_template('edit_user.html', user=user, user_id=user_id)
    return redirect(url_for('users_management'))

@app.route('/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT username FROM users WHERE id=? AND role='user'", (user_id,))
    user_username = c.fetchone()[0]
    c.execute("DELETE FROM users WHERE id=? AND role='user'", (user_id,))
    c.execute("SELECT id FROM users WHERE username=?", (session['username'],))
    admin_id = c.fetchone()[0]
    c.execute("INSERT INTO messages (user_id, message, status) VALUES (?, ?, ?)",
              (admin_id, f"Admin Activity: Deleted user {user_username}", 'unread'))
    conn.commit()
    conn.close()
    
    return redirect(url_for('users_management'))

@app.route('/admins_management', methods=['GET', 'POST'])
def admins_management():
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    if request.method == 'POST' and 'add_admin' in request.form:
        fullname = request.form['fullname']
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        c.execute("INSERT INTO users (fullname, username, email, password, role, current_latitude, current_longitude) VALUES (?, ?, ?, ?, 'admin', ?, ?)",
                  (fullname, username, email, password, 0.0, 0.0))
        c.execute("SELECT id FROM users WHERE username=?", (session['username'],))
        admin_id = c.fetchone()[0]
        c.execute("INSERT INTO messages (user_id, message, status) VALUES (?, ?, ?)",
                  (admin_id, f"Admin Activity: Added new admin {username}", 'unread'))
        conn.commit()
    
    c.execute("SELECT id, fullname, username, email FROM users WHERE role='admin'")
    admins = c.fetchall()
    
    conn.close()
    
    return render_template('admins_management.html', admins=admins)

@app.route('/edit_admin/<int:admin_id>', methods=['GET', 'POST'])
def edit_admin(admin_id):
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    if request.method == 'POST':
        fullname = request.form['fullname']
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        c.execute("UPDATE users SET fullname=?, username=?, email=?, password=? WHERE id=? AND role='admin'",
                  (fullname, username, email, password, admin_id))
        c.execute("SELECT id FROM users WHERE username=?", (session['username'],))
        admin_id_log = c.fetchone()[0]
        c.execute("INSERT INTO messages (user_id, message, status) VALUES (?, ?, ?)",
                  (admin_id_log, f"Admin Activity: Edited admin ID {admin_id}", 'unread'))
        conn.commit()
        conn.close()
        return redirect(url_for('admins_management'))
    
    c.execute("SELECT fullname, username, email, password FROM users WHERE id=? AND role='admin'", (admin_id,))
    admin = c.fetchone()
    conn.close()
    
    if admin:
        return render_template('edit_admin.html', admin=admin, admin_id=admin_id)
    return redirect(url_for('admins_management'))

@app.route('/delete_admin/<int:admin_id>', methods=['POST'])
def delete_admin(admin_id):
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT username FROM users WHERE id=? AND role='admin'", (admin_id,))
    admin_username = c.fetchone()[0]
    c.execute("DELETE FROM users WHERE id=? AND role='admin'", (admin_id,))
    c.execute("SELECT id FROM users WHERE username=?", (session['username'],))
    admin_id_log = c.fetchone()[0]
    c.execute("INSERT INTO messages (user_id, message, status) VALUES (?, ?, ?)",
              (admin_id_log, f"Admin Activity: Deleted admin {admin_username}", 'unread'))
    conn.commit()
    conn.close()
    
    return redirect(url_for('admins_management'))

@app.route('/help', methods=['GET', 'POST'])
def help():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    response = None
    if request.method == 'POST':
        user_message = request.form.get('message', '').strip().lower()
        if user_message:
            if "password" in user_message:
                response = "To change your password, you need to click on setting then change password ."
            elif "notification" in user_message:
                response = "To add a notification, go to the 'Add Notifications' page from the menu and fill in the details like location and fill percentage."
            elif "maintenance" in user_message:
                response = "To request maintenance, click on 'Request Maintenance' in the menu and enter the problem details."
            elif "buy" in user_message:
                response = "To buy a trash bin, select 'Buy Trash Bin' from the menu and specify the type and quantity."
            else:
                response = "Sorry, I didn’t understand your question! Try asking something like 'How do I change my password?' or 'How do I request maintenance?'"
    
    return render_template('help.html', response=response)

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT fullname, username, email FROM users WHERE username=?", (session['username'],))
    user = c.fetchone()
    
    message = None
    if request.method == 'POST':
        if 'old_password' in request.form:
            old_password = request.form['old_password']
            new_password = request.form['new_password']
            c.execute("SELECT password FROM users WHERE username=?", (session['username'],))
            current_password = c.fetchone()[0]
            if old_password == current_password:
                c.execute("UPDATE users SET password=? WHERE username=?", (new_password, session['username']))
                conn.commit()
                message = "Password changed successfully!"
            else:
                message = "Old password is incorrect!"
        elif 'fullname' in request.form:
            fullname = request.form['fullname']
            email = request.form['email']
            username = request.form['username']
            c.execute("SELECT id FROM users WHERE username=? AND username!=?", (username, session['username']))
            if c.fetchone():
                message = "Username already taken!"
            else:
                c.execute("UPDATE users SET fullname=?, email=?, username=? WHERE username=?",
                          (fullname, email, username, session['username']))
                session['username'] = username
                conn.commit()
                message = "Profile updated successfully!"
    
    c.execute("SELECT fullname, username, email FROM users WHERE username=?", (session['username'],))
    user = c.fetchone()
    conn.close()
    
    return render_template('settings.html', user=user, message=message)

@app.route('/admin_help', methods=['GET', 'POST'])
def admin_help():
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    message = None
    if request.method == 'POST':
        problem = request.form.get('problem', '').strip()
        if problem:
            conn = sqlite3.connect('users.db')
            c = conn.cursor()
            c.execute("SELECT id FROM users WHERE username=?", (session['username'],))
            admin_id = c.fetchone()[0]
            c.execute("INSERT INTO messages (user_id, message, status) VALUES (?, ?, ?)",
                      (admin_id, f"Problem Report: {problem}", 'unread'))
            conn.commit()
            conn.close()
            message = "Your problem report has been submitted successfully!"
    
    return render_template('admin_help.html', message=message)

@app.route('/admin_settings', methods=['GET', 'POST'])
def admin_settings():
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT fullname, username, email FROM users WHERE username=?", (session['username'],))
    user = c.fetchone()
    
    message = None
    if 'requests_per_page' not in session:
        session['requests_per_page'] = 5
    
    if request.method == 'POST':
        if 'old_password' in request.form:
            old_password = request.form['old_password']
            new_password = request.form['new_password']
            c.execute("SELECT password FROM users WHERE username=?", (session['username'],))
            current_password = c.fetchone()[0]
            if old_password == current_password:
                c.execute("UPDATE users SET password=? WHERE username=?", (new_password, session['username']))
                conn.commit()
                message = "Password changed successfully!"
            else:
                message = "Old password is incorrect!"
        elif 'requests_per_page' in request.form:
            requests_per_page = int(request.form['requests_per_page'])
            session['requests_per_page'] = requests_per_page
            message = "System settings updated successfully!"

    c.execute("SELECT id FROM users WHERE username=?", (session['username'],))
    admin_id = c.fetchone()[0]
    c.execute("SELECT message, created_at FROM messages WHERE user_id=? AND message LIKE 'Admin Activity:%' ORDER BY created_at DESC LIMIT 10", (admin_id,))
    activity_log = c.fetchall()

    conn.close()
    
    return render_template('admin_settings.html', user=user, message=message, requests_per_page=session['requests_per_page'], activity_log=activity_log)

@app.route('/trash_management', methods=['GET', 'POST'])
def trash_management():
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    c.execute("SELECT id, user_id, location, fill_percentage, is_full, status, reported_at FROM trash_bins ORDER BY reported_at DESC")
    trash_bins = c.fetchall()
    
    if request.method == 'POST' and 'update_status' in request.form:
        trash_id = int(request.form['trash_id'])
        new_status = request.form['status']
        c.execute("UPDATE trash_bins SET status=? WHERE id=?", (new_status, trash_id))
        c.execute("SELECT id FROM users WHERE username=?", (session['username'],))
        admin_id = c.fetchone()[0]
        c.execute("INSERT INTO messages (user_id, message, status) VALUES (?, ?, ?)",
                  (admin_id, f"Admin Activity: Updated trash bin ID {trash_id} status to {new_status}", 'unread'))
        conn.commit()
    
    conn.close()
    
    return render_template('trash_management.html', trash_bins=trash_bins)

@app.route('/notifications_center', methods=['GET', 'POST'])
def notifications_center():
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    message = None
    if request.method == 'POST' and 'send_message' in request.form:
        recipients = request.form.getlist('recipients')
        message_content = request.form['message']
        if recipients and message_content:
            for user_id in recipients:
                c.execute("INSERT INTO messages (user_id, message, status) VALUES (?, ?, ?)",
                          (user_id, message_content, 'unread'))
            c.execute("SELECT id FROM users WHERE username=?", (session['username'],))
            admin_id = c.fetchone()[0]
            c.execute("INSERT INTO messages (user_id, message, status) VALUES (?, ?, ?)",
                      (admin_id, f"Admin Activity: Sent message to {len(recipients)} users", 'unread'))
            conn.commit()
            message = "Message sent successfully!"
    
    c.execute("SELECT m.id, m.user_id, u.username, m.message, m.status, m.created_at FROM messages m JOIN users u ON m.user_id = u.id ORDER BY m.created_at DESC LIMIT 20")
    messages = c.fetchall()
    
    c.execute("SELECT id, username FROM users WHERE role IN ('user', 'driver')")
    users = c.fetchall()
    
    conn.close()
    
    return render_template('notifications_center.html', messages=messages, users=users, message=message)

@app.route('/reports', methods=['GET'])
def reports():
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    c.execute("SELECT DATE(requested_at) as date, COUNT(*) as count FROM purchase_requests GROUP BY DATE(requested_at) ORDER BY date DESC LIMIT 7")
    daily_purchases = c.fetchall()
    
    c.execute("SELECT DATE(reported_at) as date, COUNT(*) as count FROM trash_bins GROUP BY DATE(reported_at) ORDER BY date DESC LIMIT 7")
    daily_notifications = c.fetchall()
    
    c.execute("SELECT DATE(reported_at) as date, COUNT(*) as count FROM maintenance_requests GROUP BY DATE(reported_at) ORDER BY date DESC LIMIT 7")
    daily_maintenance = c.fetchall()
    
    c.execute("SELECT u.username, COUNT(*) as count FROM trash_bins t JOIN users u ON t.user_id = u.id GROUP BY t.user_id, u.username ORDER BY count DESC LIMIT 1")
    most_active_user = c.fetchone()
    
    c.execute("SELECT COUNT(*) FROM users WHERE role='driver'")
    total_drivers = c.fetchone()[0]
    
    # Top driver by points
    c.execute("SELECT username, points FROM users WHERE role='driver' ORDER BY points DESC LIMIT 1")
    top_driver = c.fetchone()
    
    # Top driver by completed tasks
    c.execute("""
        SELECT u.username, COUNT(*) as count 
        FROM (
            SELECT assigned_driver_id FROM trash_bins WHERE status='completed'
            UNION ALL
            SELECT assigned_driver_id FROM maintenance_requests WHERE status='completed'
            UNION ALL
            SELECT assigned_driver_id FROM purchase_requests WHERE status='completed'
        ) tasks
        JOIN users u ON u.id = tasks.assigned_driver_id
        WHERE u.role='driver'
        GROUP BY u.id, u.username
        ORDER BY count DESC LIMIT 1
    """)
    top_driver_tasks = c.fetchone()
    
    conn.close()
    
    return render_template('reports.html', 
                         daily_purchases=daily_purchases, 
                         daily_notifications=daily_notifications, 
                         daily_maintenance=daily_maintenance,
                         most_active_user=most_active_user,
                         total_drivers=total_drivers,
                         top_driver=top_driver,
                         top_driver_tasks=top_driver_tasks)

@app.route('/driver_tasks', methods=['GET', 'POST'])
def driver_tasks():
    if 'username' not in session or session['role'] != 'driver':
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    # Get driver's ID and current location
    c.execute("SELECT id, current_latitude, current_longitude FROM users WHERE username=?", (session['username'],))
    driver_info = c.fetchone()
    driver_id, driver_lat, driver_lon = driver_info
    current_pos = (driver_lat, driver_lon) if driver_lat and driver_lon else (30.0444, 31.2357)  # Default to Cairo
    
    # Fetch tasks assigned to this driver only
    c.execute("SELECT id, location, latitude, longitude, fill_percentage, reported_at, status, notes FROM trash_bins WHERE assigned_driver_id=? AND status IN ('approved', 'in_progress', 'completed')", (driver_id,))
    trash_bins = c.fetchall() or []
    c.execute("SELECT id, location, latitude, longitude, problem_type, reported_at, status, notes FROM maintenance_requests WHERE assigned_driver_id=? AND status IN ('approved', 'in_progress', 'completed')", (driver_id,))
    maintenance = c.fetchall() or []
    c.execute("SELECT id, delivery_address AS location, latitude, longitude, bin_type, requested_at, status, notes FROM purchase_requests WHERE assigned_driver_id=? AND status IN ('approved', 'in_progress', 'completed')", (driver_id,))
    purchases = c.fetchall() or []
    
    # Handle POST requests (start/complete tasks)
    if request.method == 'POST':
        task_type = request.form.get('task_type')
        task_id = int(request.form.get('task_id'))
        action = request.form.get('action')
        notes = request.form.get('notes', '')

        if task_type == 'trash_bin':
            table = 'trash_bins'
            location_field = 'location'
        elif task_type == 'maintenance':
            table = 'maintenance_requests'
            location_field = 'location'
        elif task_type == 'purchase':
            table = 'purchase_requests'
            location_field = 'delivery_address'
        else:
            conn.close()
            return redirect(url_for('driver_tasks'))

        if action == 'start':
            c.execute(f"UPDATE {table} SET status='in_progress' WHERE id=? AND assigned_driver_id=?", (task_id, driver_id))
        elif action == 'complete':
            c.execute(f"UPDATE {table} SET status='completed' WHERE id=? AND assigned_driver_id=?", (task_id, driver_id))
            c.execute(f"SELECT user_id, {location_field} FROM {table} WHERE id=?", (task_id,))
            task = c.fetchone()
            message = f"Driver {session['username']} completed {task_type} at {task[1]}"
            c.execute("SELECT id FROM users WHERE role='admin' LIMIT 1")
            admin_id = c.fetchone()[0]
            c.execute("INSERT INTO messages (user_id, message, status) VALUES (?, ?, ?)",
                      (admin_id, message, 'unread'))
            c.execute("INSERT INTO messages (user_id, message, status) VALUES (?, ?, ?)",
                      (task[0], f"Your {task_type.replace('_', ' ')} request has been completed.", 'unread'))

        if notes:
            c.execute(f"UPDATE {table} SET notes=? WHERE id=? AND assigned_driver_id=?", (notes, task_id, driver_id))

        conn.commit()

    conn.close()
    
    # Combine tasks
    tasks = (
        [{'id': tb[0], 'type': 'trash_bin', 'location': tb[1], 'latitude': tb[2], 'longitude': tb[3], 'details': f"Fill: {tb[4]}%", 'date': tb[5], 'status': tb[6], 'notes': tb[7] or ''} for tb in trash_bins] +
        [{'id': m[0], 'type': 'maintenance', 'location': m[1], 'latitude': m[2], 'longitude': m[3], 'details': f"Problem: {m[4]}", 'date': m[5], 'status': m[6], 'notes': m[7] or ''} for m in maintenance] +
        [{'id': p[0], 'type': 'purchase', 'location': p[1], 'latitude': p[2], 'longitude': p[3], 'details': f"Bin: {p[4]}", 'date': p[5], 'status': p[6], 'notes': p[7] or ''} for p in purchases]
    )
    
    return render_template('driver_tasks.html', 
                         tasks=tasks, 
                         driver_lat=current_pos[0], 
                         driver_lon=current_pos[1])

@app.route('/driver_notifications', methods=['GET', 'POST'])
def driver_notifications():
    if 'username' not in session or session['role'] != 'driver':
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    # Get the current driver's ID
    c.execute("SELECT id FROM users WHERE username=?", (session['username'],))
    driver_id = c.fetchone()[0]
    
    # Fetch all messages for the driver
    c.execute("SELECT message, created_at, status FROM messages WHERE user_id=? ORDER BY created_at DESC", (driver_id,))
    notifications = c.fetchall()
    
    # Handle the "Clear All" button
    if request.method == 'POST' and 'clear_notifications' in request.form:
        c.execute("DELETE FROM messages WHERE user_id=?", (driver_id,))
        conn.commit()
        return redirect(url_for('driver_notifications'))
    
    conn.close()
    
    return render_template('driver_notifications.html', notifications=notifications)

@app.route('/driver_help', methods=['GET', 'POST'])
def driver_help():
    if 'username' not in session or session['role'] != 'driver':
        return redirect(url_for('login'))
    
    chat_history = session.get('chat_history', [])  # Load chat history from session
    
    if request.method == 'POST':
        if 'clear_chat' in request.form:  # Check for clear button
            session['chat_history'] = []  # Reset chat history
            return redirect(url_for('driver_help'))
        
        user_message = request.form.get('message', '').strip().lower()
        if user_message:
            # Keyword-based responses
            if "task" in user_message and "complete" in user_message:
                bot_response = "To complete a task, go to the 'Tasks' or 'Routes' page, find the task, and click 'Complete'. Confirm when prompted!"
            elif "location" in user_message and "update" in user_message:
                bot_response = "To update your location, go to the Dashboard and click 'Add Location'. Allow the browser to access your location when asked."
            elif "route" in user_message or "path" in user_message:
                bot_response = "To see your route, go to the 'Routes' page. Click 'Recalculate Route' to update it based on your current tasks."
            elif "notification" in user_message:
                bot_response = "Check your notifications on the 'Notifications' page. You can clear them with the 'Clear All' button."
            elif "logout" in user_message:
                bot_response = "To log out, click 'Logout' from the menu on the left."
            else:
                bot_response = "Sorry, I didn’t understand that! Try asking something like 'How do I complete a task?' or 'How do I update my location?'"
            
            # Add to chat history
            chat_history.append({"user": user_message, "bot": bot_response})
            session['chat_history'] = chat_history  # Update session
    
    return render_template('driver_help.html', chat_history=chat_history)

@app.route('/driver_settings', methods=['GET', 'POST'])
def driver_settings():
    if 'username' not in session or session['role'] != 'driver':
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    # Fetch current driver info
    c.execute("SELECT fullname, username, email FROM users WHERE username=?", (session['username'],))
    driver = c.fetchone()
    
    message = None
    if request.method == 'POST':
        # Update Profile Form
        if 'fullname' in request.form:
            fullname = request.form['fullname']
            username = request.form['username']
            email = request.form['email']
            
            # Check if new username is taken (excluding current user)
            c.execute("SELECT id FROM users WHERE username=? AND username!=?", (username, session['username']))
            if c.fetchone():
                message = "Username already taken!"
            else:
                c.execute("UPDATE users SET fullname=?, username=?, email=? WHERE username=?",
                          (fullname, username, email, session['username']))
                session['username'] = username  # Update session with new username
                conn.commit()
                message = "Profile updated successfully!"
        
        # Change Password Form
        elif 'old_password' in request.form:
            old_password = request.form['old_password']
            new_password = request.form['new_password']
            
            c.execute("SELECT password FROM users WHERE username=?", (session['username'],))
            current_password = c.fetchone()[0]
            if old_password == current_password:
                c.execute("UPDATE users SET password=? WHERE username=?", (new_password, session['username']))
                conn.commit()
                message = "Password changed successfully!"
            else:
                message = "Old password is incorrect!"
    
    # Refresh driver info after updates
    c.execute("SELECT fullname, username, email FROM users WHERE username=?", (session['username'],))
    driver = c.fetchone()
    conn.close()
    
    return render_template('driver_settings.html', driver=driver, message=message)

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('role', None)
    session.pop('requests_per_page', None)
    return redirect(url_for('index'))

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE email=?", (email,))
        user = c.fetchone()
        conn.close()
        
        if user:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            reset_codes[email] = code  
            print(f"Password reset code for {email}: {code}")
            return render_template('forgot_password.html', 
                                message="The activation code has been sent to your email.", 
                                message_type="success", 
                                message_title="The code has been sent.",
                                email=email)  
        else:
            return render_template('forgot_password.html', 
                                message="Email does not exists", 
                                message_type="error", 
                                message_title="Wrong")
    
    return render_template('forgot_password.html')

@app.route('/verify_code', methods=['GET', 'POST'])
def verify_code():
    if request.method == 'POST':
        email = request.form['email']
        code = request.form['code']
        
        if email in reset_codes and reset_codes[email] == code:
            # Code is valid, proceed to reset password
            return render_template('reset_password.html', email=email)
        else:
            return render_template('verify_code.html', email=email, error="Invalid or expired code.")
    
    # GET request: should come from forgot_password with email
    email = request.args.get('email')
    if email:
        return render_template('verify_code.html', email=email)
    return redirect(url_for('forgot_password'))

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            return render_template('reset_password.html', email=email, error="Passwords do not match.")
        
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("UPDATE users SET password=? WHERE email=?", (password, email))
        conn.commit()
        conn.close()
        
        # Clear the reset code
        if email in reset_codes:
            del reset_codes[email]
        
        return render_template('reset_password.html', success="Password reset successfully! You can now log in.")
    
    return redirect(url_for('forgot_password'))

@app.route('/driver_profile')
def driver_profile():
    if 'username' not in session or session['role'] != 'driver':
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT fullname, username, email, points, promotion FROM users WHERE username=?", (session['username'],))
    driver = c.fetchone()
    conn.close()
    
    if driver:
        return render_template('driver_profile.html',
                             driver_fullname=driver[0],
                             driver_username=driver[1],
                             driver_email=driver[2],
                             driver_points=driver[3],
                             driver_promotion=driver[4])
    return redirect(url_for('login'))
@app.route('/add_trash_notification', methods=['POST'])
def add_trash_notification():
    data = request.get_json()
    location = data.get('location')
    latitude = float(data.get('latitude'))
    longitude = float(data.get('longitude'))
    fill_percentage = float(data.get('fill_percentage'))
    is_full = 1 if fill_percentage >= 90 else 0

    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    # Insert the notification into trash_bins (user_id set to NULL since it's from Arduino)
    c.execute("INSERT INTO trash_bins (user_id, location, latitude, longitude, fill_percentage, is_full, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (None, location, latitude, longitude, fill_percentage, is_full, 'pending'))
    
    # Notify admin
    c.execute("SELECT id FROM users WHERE role='admin' LIMIT 1")
    admin_id = c.fetchone()[0]
    c.execute("INSERT INTO messages (user_id, message, status) VALUES (?, ?, ?)",
              (admin_id, f"New trash bin notification from Arduino at {location} (Fill: {fill_percentage}%)", 'unread'))
    
    conn.commit()
    conn.close()
    return jsonify({"status": "success"}), 200

@app.route('/get_bin_status', methods=['GET'])
def get_bin_status():
    location = "el tarf"  #fix for now
    status = bin_status.get(location, "pending")  
    return status

if __name__ == '__main__':
    init_db()
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.run(host='0.0.0.0', port=5000, debug=True)