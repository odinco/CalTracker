import webbrowser
import threading
import sys
import os
import secrets
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_socketio import SocketIO

# Determine the base directory dynamically
if getattr(sys, 'frozen', False):  # Running as a PyInstaller executable
    base_dir = os.path.dirname(sys.executable)
else:  # Running as a Python script
    base_dir = os.path.dirname(os.path.abspath(__file__))

# Define the instance directory inside CalTracke
instance_path = os.path.join(base_dir, "instance")

# Ensure the instance directory exists
os.makedirs(instance_path, exist_ok=True)

# Ensure the templates folder is correctly referenced
template_path = os.path.join(base_dir, "templates")

# Corrected Flask app initialization
app = Flask(__name__, template_folder=template_path)
CORS(app)

# Define database path
db_path = os.path.join(instance_path, "calibration.db")
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_path}"

# Add this line to debug where the database is being created
print(f"📌 Database path: {db_path}")

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = secrets.token_hex(16)  # Securely generate a secret key

db = SQLAlchemy(app)

# Force threading as async mode
async_mode = "threading"

# Initialize SocketIO with a valid async_mode
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

def notify_clients():
    socketio.emit('update_calibrations')

# Database models
class Component(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)

class CalibrationData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    component_id = db.Column(db.Integer, db.ForeignKey('component.id'), nullable=False)
    cal_number = db.Column(db.String(3), nullable=False)
    description = db.Column(db.Text, nullable=True)
    pri = db.Column(db.String(5), nullable=True)
    sec = db.Column(db.String(5), nullable=True)
    reso = db.Column(db.String(5), nullable=True)
    dm = db.Column(db.String(5), nullable=True)
    pri_completed = db.Column(db.Boolean, default=False)
    sec_completed = db.Column(db.Boolean, default=False)
    reso_completed = db.Column(db.Boolean, default=False)
    dm_completed = db.Column(db.Boolean, default=False)

# Credentials (for demonstration; replace with a secure method)
USERNAME = "admin"
PASSWORD = "password123"

# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username == USERNAME and password == PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('home'))

        return "Invalid credentials, try again!"

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.before_request
def require_login():
    allowed_routes = ['login', 'static']
    if request.endpoint not in allowed_routes and 'logged_in' not in session:
        return redirect(url_for('login'))

# Main routes
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/add_component', methods=['POST'])
def add_component():
    data = request.json
    print(f"📌 Received Component Data: {data}")  # Debugging

    try:
        new_component = Component(name=data['name'])
        db.session.add(new_component)
        db.session.commit()
        print(f"✅ Added Component: {new_component.name} (ID: {new_component.id})")
        return jsonify({"message": "Component added successfully", "id": new_component.id})
    except Exception as e:
        db.session.rollback()
        print(f"❌ Database Error: {e}")
        return jsonify({"error": "Failed to add component"}), 500

@app.route('/get_components', methods=['GET'])
def get_components():
    components = Component.query.all()
    return jsonify([{"id": c.id, "name": c.name} for c in components])

@app.route('/add_calibration', methods=['POST'])
def add_calibration():
    data = request.json
    try:
        new_cal = CalibrationData(
            component_id=data['component_id'],
            cal_number=data['cal_number']
        )
        db.session.add(new_cal)
        db.session.commit()

        # Notify clients about the new calibration
        notify_clients()

        return jsonify({
            "message": "Calibration entry added successfully",
            "cal": {
                "id": new_cal.id,
                "component_id": new_cal.component_id,
                "cal_number": new_cal.cal_number,
                "description": new_cal.description,
                "pri": new_cal.pri,
                "sec": new_cal.sec,
                "reso": new_cal.reso,
                "dm": new_cal.dm,
                "pri_completed": new_cal.pri_completed,
                "sec_completed": new_cal.sec_completed,
                "reso_completed": new_cal.reso_completed,
                "dm_completed": new_cal.dm_completed
            }
        })
    except Exception as e:
        db.session.rollback()
        print(f"❌ Database Error: {e}")
        return jsonify({"error": "Failed to add calibration"}), 500

@app.route('/update_cal', methods=['POST'])
def update_cal():
    data = request.json.get('updates', [])

    try:
        for update in data:
            cal_entry = CalibrationData.query.get(update['id'])
            if cal_entry:
                cal_entry.description = update.get('description', cal_entry.description)
                cal_entry.pri = update.get('pri', cal_entry.pri)
                cal_entry.sec = update.get('sec', cal_entry.sec)
                cal_entry.reso = update.get('reso', cal_entry.reso)
                cal_entry.dm = update.get('dm', cal_entry.dm)

        db.session.commit()
        notify_clients()  # Notify clients about the update
        return jsonify({"message": "Calibrations updated successfully!"})
    except Exception as e:
        db.session.rollback()
        print(f"❌ Database Error: {e}")
        return jsonify({"error": "Failed to update calibrations"}), 500

@app.route('/get_calibrations/<int:component_id>', methods=['GET'])
def get_calibrations(component_id):
    calibrations = CalibrationData.query.filter_by(component_id=component_id).all()
    return jsonify([{
        "id": c.id,
        "cal_number": c.cal_number,
        "description": c.description,
        "pri": c.pri,
        "sec": c.sec,
        "reso": c.reso,
        "dm": c.dm,
        "pri_completed": c.pri_completed,
        "sec_completed": c.sec_completed,
        "reso_completed": c.reso_completed,
        "dm_completed": c.dm_completed
    } for c in calibrations])

@app.route('/delete_cal/<int:cal_id>', methods=['DELETE'])
def delete_cal(cal_id):
    try:
        cal = CalibrationData.query.get(cal_id)
        if cal:
            db.session.delete(cal)
            db.session.commit()
            return jsonify({"message": "Calibration deleted successfully!"}), 200
        return jsonify({"error": "Calibration not found"}), 404
    except Exception as e:
        db.session.rollback()
        print(f"❌ Database Error: {e}")
        return jsonify({"error": "Failed to delete calibration"}), 500

@app.route('/delete_component/<int:component_id>', methods=['DELETE'])
def delete_component(component_id):
    try:
        component = Component.query.get(component_id)
        if component:
            CalibrationData.query.filter_by(component_id=component_id).delete()
            db.session.delete(component)
            db.session.commit()
            return jsonify({"message": "Component and calibrations deleted successfully!"}), 200
        return jsonify({"error": "Component not found"}), 404
    except Exception as e:
        db.session.rollback()
        print(f"❌ Database Error: {e}")
        return jsonify({"error": "Failed to delete component"}), 500

@app.route('/update_status', methods=['POST'])
def update_status():
    data = request.json
    try:
        cal_entry = CalibrationData.query.get(data['id'])
        if not cal_entry:
            return jsonify({"error": "Entry not found"}), 404

        cal_entry.pri_completed = data.get('pri_completed', cal_entry.pri_completed)
        cal_entry.sec_completed = data.get('sec_completed', cal_entry.sec_completed)
        cal_entry.reso_completed = data.get('reso_completed', cal_entry.reso_completed)
        cal_entry.dm_completed = data.get('dm_completed', cal_entry.dm_completed)

        db.session.commit()
        return jsonify({"message": "Status updated successfully!"})
    except Exception as e:
        db.session.rollback()
        print(f"❌ Database Error: {e}")
        return jsonify({"error": "Failed to update status"}), 500

# SocketIO Events
@socketio.on('connect')
def handle_connect():
    print("Client connected")

@socketio.on('disconnect')
def handle_disconnect():
    print("Client disconnected")

# Browser-opening helper
def open_browser():
    webbrowser.open_new("http://127.0.0.1:5000")

if __name__ == "__main__":
    with app.app_context():
        db.create_all()  # Ensure database tables are created
    threading.Timer(2, open_browser).start()  # Open browser after 2 seconds
    socketio.run(app, debug=True, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
