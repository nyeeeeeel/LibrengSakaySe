from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import oracledb
import os
import uuid

# Initialize Flask application
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

app.secret_key = os.urandom(24)
LIB_DIR = r"D:\se\instantclient-basic-windows.x64-23.7.0.25.01\instantclient_23_7"

# Initialize Oracle Client
try:
    oracledb.init_oracle_client(lib_dir=LIB_DIR)
except Exception as e:
    print(f"Error initializing Oracle Client: {e}")
    exit()

# Database Connection Function
def get_db_connection():
    try:
        conn = oracledb.connect(
            user="system",
            password="Daniel",
            dsn="LAPTOP-QG816HRU/XE"
        )
        print("Database connection successful.")
        return conn
    except oracledb.Error as error:
        print(f"Database connection error: {error}")
        return None

# Utility Function (keeping UUID for bus_id for now)
def generate_unique_bus_id():
    return str(uuid.uuid4())

# Routes
@app.route('/admin.html')
def admin_page():
    return render_template('admin.html')

@app.route('/add_bus_info', methods=['POST'])
def add_bus_info():
    conn = None
    try:
        data = request.get_json()
        print(f"Received data: {data}")

        bus_id = data.get('bus_id')
        plate_number = data.get('plate_number')
        name = data.get('name')
        email = data.get('email')
        password = data.get('password')

        if not bus_id or not plate_number or not name or not email or not password:
            return jsonify({'success': False, 'message': 'Please fill up all the details.'}), 400

        conn = get_db_connection()
        if conn is None:
            return jsonify({'success': False, 'message': 'Database connection failed.'}), 500

        cursor = conn.cursor()
        try:
            # Check if Bus ID or Plate Number already exists
            cursor.execute("SELECT 1 FROM bus_info_tb WHERE BUS_ID = :1", [bus_id])
            if cursor.fetchone():
                return jsonify({'success': False, 'message': 'Bus ID already exists.'}), 400
            cursor.execute("SELECT 1 FROM bus_info_tb WHERE PLATE_NUMBER = :1", [plate_number])
            if cursor.fetchone():
                return jsonify({'success': False, 'message': 'Plate Number already exists.'}), 400

            # Check if Email already exists
            cursor.execute("SELECT 1 FROM login_info_tb WHERE email = :1", [email])
            if cursor.fetchone():
                return jsonify({'success': False, 'message': 'Email already exists.'}), 400

            # 1. Insert into login_info_tb using sequence
            cursor.execute("SELECT login_id_seqTB.NEXTVAL FROM DUAL")
            login_id = cursor.fetchone()[0]
            cursor.execute(
                "INSERT INTO login_info_tb (LOGIN_ID, email, password, user_role) VALUES (:1, :2, :3, 'conductor')",
                [login_id, email, password]
            )

            # 2. Insert into conductor_info_tb using sequence
            cursor.execute("SELECT conductor_id_seq.NEXTVAL FROM DUAL")
            conductor_id = cursor.fetchone()[0]
            cursor.execute(
                "INSERT INTO conductor_info_tb (CONDUCTOR_ID, CONDUCTOR_NAME, LOGIN_ID, BUS_ID) VALUES (:1, :2, :3, :4)",
                [conductor_id, name, login_id, bus_id]
            )

            # 3. Insert into bus_info_tb
            cursor.execute("INSERT INTO bus_info_tb (BUS_ID, PLATE_NUMBER) VALUES (:1, :2)", [bus_id, plate_number])

            conn.commit()
            print(f"Bus inserted with ID: {bus_id}")
            return jsonify({'success': True, 'message': f'Successfully added Bus ID: {bus_id}, Conductor ID: {conductor_id}, Login ID: {login_id}'}), 201

        except oracledb.Error as error:
            conn.rollback()
            print(f"DB error: {error}")
            return jsonify({'success': False, 'message': f'DB error: {error}'}), 500

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    except Exception as e:
        print(f"Request error: {e}")
        return jsonify({'success': False, 'message': f'Request error: {e}'}), 500

@app.route('/add_conductor', methods=['POST'])
def add_conductor():
    conn = None
    try:
        data = request.get_json()
        print(f"Received conductor data: {data}")

        conductor_name = data.get('name')
        email = data.get('email')
        password = data.get('password')
        bus_id = data.get('bus_id')  # Get bus_id for the conductor

        if not conductor_name or not email or not password or not bus_id:
            return jsonify({'success': False, 'message': 'Please fill up all the details.'}), 400

        conn = get_db_connection()
        if conn is None:
            return jsonify({'success': False, 'message': 'Database connection failed.'}), 500

        cursor = conn.cursor()
        try:
            # Check if Email already exists
            cursor.execute("SELECT 1 FROM login_info_tb WHERE email = :1", [email])
            if cursor.fetchone():
                return jsonify({'success': False, 'message': 'Email already exists.'}), 400

            # 1. Get next sequence value for LOGIN_ID
            cursor.execute("SELECT login_id_seqTB.NEXTVAL FROM DUAL")
            login_id = cursor.fetchone()[0]
            cursor.execute("INSERT INTO login_info_tb (LOGIN_ID, email, password, user_role) VALUES (:1, :2, :3, 'conductor')", [login_id, email, password])
            print(f"Login inserted with ID: {login_id}")

            # 2. Get next sequence value for CONDUCTOR_ID
            cursor.execute("SELECT conductor_id_seq.NEXTVAL FROM DUAL")
            conductor_id = cursor.fetchone()[0]
            cursor.execute("INSERT INTO conductor_info_tb (CONDUCTOR_ID, CONDUCTOR_NAME, LOGIN_ID, BUS_ID) VALUES (:1, :2, :3, :4)", [conductor_id, conductor_name, login_id, bus_id])
            print(f"Conductor inserted with ID: {conductor_id}, linked to Login ID: {login_id} and Bus ID: {bus_id}")

            conn.commit()
            return jsonify({'success': True, 'message': f'Successfully added Conductor ID: {conductor_id}!'}), 201

        except oracledb.Error as error:
            conn.rollback()
            print(f"DB error: {error}")
            return jsonify({'success': False, 'message': f'DB error: {error}'}), 500

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    except Exception as e:
        print(f"Request error: {e}")
        return jsonify({'success': False, 'message': f'Request error: {e}'}), 500

@app.route('/activate_bus', methods=['POST'])
def activate_bus():
    conn = None
    try:
        data = request.get_json()
        print(f"Received activate bus data: {data}")

        bus_id = data.get('bus_id')
        conductor_id = data.get('conductor_id')
        available_seat = data.get('available_seat')
        eta = data.get('eta')
        notes = data.get('notes')

        if not bus_id or not conductor_id or not available_seat or not eta: # Removed notes from required for now
            return jsonify({'success': False, 'message': 'Please fill up all the details (Bus ID, Conductor ID, Available Seat, ETA).'}), 400

        conn = get_db_connection()
        if conn is None:
            return jsonify({'success': False, 'message': 'Database connection failed.'}), 500

        cursor = conn.cursor()
        try:
            # Check if Bus ID and Conductor ID exist
            cursor.execute("SELECT 1 FROM bus_info_tb WHERE BUS_ID = :1", [bus_id])
            if not cursor.fetchone():
                return jsonify({'success': False, 'message': f'Bus ID "{bus_id}" does not exist.'}), 400
            cursor.execute("SELECT 1 FROM conductor_info_tb WHERE CONDUCTOR_ID = :1", [conductor_id])
            if not cursor.fetchone():
                return jsonify({'success': False, 'message': f'Conductor ID "{conductor_id}" does not exist.'}), 400

            active_bus_id = generate_unique_bus_id() # Keeping UUID for active_bus_id
            cursor.execute("INSERT INTO active_bus_tb (ACTIVE_BUS_ID, BUS_ID, CONDUCTOR_ID, AVAILABLE_SEAT, ETA, NOTES) VALUES (:1, :2, :3, :4, :5, :6)",
                           [active_bus_id, bus_id, conductor_id, available_seat, eta, notes])
            conn.commit()
            print(f"Bus activated with ID: {active_bus_id}, Bus ID: {bus_id}, Conductor ID: {conductor_id}")
            return jsonify({'success': True, 'message': f'Successfully activated Bus ID: {bus_id}'}), 201

        except oracledb.Error as error:
            conn.rollback()
            print(f"DB error: {error}")
            return jsonify({'success': False, 'message': f'DB error: {error}'}), 500

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    except Exception as e:
        print(f"Request error: {e}")
        return jsonify({'success': False, 'message': f'Request error: {e}'}), 500

@app.route('/get_all_bus_info')
def get_all_bus_info():
    conn = None
    try:
        conn = get_db_connection()
        if conn is None:
            return jsonify({'success': False, 'message': 'Database connection failed.'}), 500

        cursor = conn.cursor()
        try:
            # Execute a JOIN query to fetch data from all three tables
            cursor.execute("""
                SELECT
                    b.BUS_ID,
                    b.PLATE_NUMBER,
                    c.CONDUCTOR_NAME,
                    l.EMAIL,
                    l.PASSWORD  -- Be cautious about exposing passwords
                FROM
                    bus_info_tb b
                JOIN
                    conductor_info_tb c ON b.BUS_ID = c.BUS_ID
                JOIN
                    login_info_tb l ON c.LOGIN_ID = l.LOGIN_ID
            """)
            results = cursor.fetchall()

            # Structure the fetched data into a list of dictionaries
            bus_data_list = []
            for row in results:
                bus_data_list.append({
                    'Bus ID': row[0],
                    'Plate Number': row[1],
                    'Conductor Name': row[2],
                    'Email': row[3],
                    'Password': '**********'  # It's better to mask the password for display
                })

            return jsonify({'success': True, 'data': bus_data_list}), 200

        except oracledb.Error as error:
            print(f"DB error: {error}")
            return jsonify({'success': False, 'message': f'DB error: {error}'}), 500

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    except Exception as e:
        print(f"Request error: {e}")
        return jsonify({'success': False, 'message': f'Request error: {e}'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)