from flask import Flask, request, jsonify, session, render_template
from flask_cors import CORS
import mysql.connector
import os
import uuid
from datetime import datetime, timedelta
from flask_mail import Message, Mail
import random

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

@app.route('/')
def home():
    return render_template('login.html')


app.secret_key = os.urandom(24)

# Configure Flask-Mail (replace with your actual settings)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'availabusqclibrengsakay@gmail.com'
app.config['MAIL_PASSWORD'] = 'lvzz oror iawr bhnq'
app.config['MAIL_DEFAULT_SENDER'] = 'availabusqclibrengsakay@gmail.com'

mail = Mail(app)

# MySQL database configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'qcbus_db'  # Replace with your actual database name
}

def get_db_connection():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        print("Database connection successful.")
        return conn
    except mysql.connector.Error as error:
        print(f"Database connection error: {error}")
        return None

def is_email_taken(conn, email):
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT 1 FROM qc_login WHERE LOWER(email) = LOWER(%s)", (email.lower(),))
        result = cursor.fetchone()
        return result is not None
    except mysql.connector.Error as error:
        print(f"Error checking email: {error}")
        return False
    finally:
        cursor.close()

def generate_verification_code():
    return str(random.randint(100000, 999999))

def send_verification_email(email, verification_code):
    message = Message('CityBus Password Reset Verification Code',
                        sender=app.config['MAIL_DEFAULT_SENDER'],
                        recipients=[email])
    message.body = f'''Your password reset verification code is:

{verification_code}

This code will expire in 15 minutes.

If you did not request a password reset, please ignore this email.
'''
    print(f"Attempting to send email with username: {app.config['MAIL_USERNAME']}")
    print(f"Attempting to send email with password: {app.config['MAIL_PASSWORD']}")
    try:
        mail.send(message)
        print("Email sent successfully (attempt).")
    except Exception as e:
        print(f"Error sending email AFTER config check: {e}")

# Store verification codes temporarily (consider using a database table for production)
verification_codes = {}

@app.route('/forgot')
def forgot_page():
    return render_template('Forgot.html')  # This file should be in the "templates" folder

@app.route('/send_reset_code', methods=['POST'])
def send_reset_code():
    """Sends a password reset verification code to the user's email."""
    data = request.get_json()
    email = data.get('email')

    if not email:
        return jsonify({'success': False, 'message': 'Email is required.'}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection failed.'}), 500

    cursor = conn.cursor()
    try:
        # Check if the email exists
        cursor.execute("SELECT login_id FROM qc_login WHERE LOWER(email) = LOWER(%s)", (email.lower(),))
        result = cursor.fetchone()
        if not result:
            return jsonify({'success': False, 'message': 'No user found with that email.'}), 404

        verification_code = generate_verification_code()
        verification_codes[email] = {'code': verification_code, 'expiry': datetime.utcnow() + timedelta(minutes=15)}
        send_verification_email(email, verification_code)

        return jsonify({'success': True, 'message': 'Verification code sent to your email.'}), 200

    except mysql.connector.Error as error:
        print(f"Database error sending reset code: {error}")
        return jsonify({'success': False, 'message': f'Database error: {error}'}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/reset_password', methods=['POST'])
def reset_password():
    """Handles the resetting of the user's password after verifying the code."""
    data = request.get_json()
    email = data.get('email')
    verification_code = data.get('verification_code')
    new_password = data.get('new_password')
    confirm_password = data.get('confirm_password')

    if not email or not verification_code or not new_password or not confirm_password:
        return jsonify({'success': False, 'message': 'Email, verification code, and both password fields are required.'}), 400

    if new_password != confirm_password:
        return jsonify({'success': False, 'message': 'New passwords do not match.'}), 400

    if email not in verification_codes or verification_codes[email]['code'] != verification_code:
        return jsonify({'success': False, 'message': 'Invalid verification code.'}), 400

    if datetime.utcnow() > verification_codes[email]['expiry']:
        del verification_codes[email]
        return jsonify({'success': False, 'message': 'Verification code has expired.'}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection failed.'}), 500

    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE qc_login
            SET password = %s, reset_token = NULL, reset_token_expiry = NULL
            WHERE LOWER(email) = LOWER(%s)
        """, (new_password, email.lower()))
        rows_updated = cursor.rowcount
        conn.commit()
        del verification_codes[email]  # Remove the code after successful reset

        if rows_updated > 0:
            return jsonify({'success': True, 'message': 'Password reset successfully.'}), 200
        else:
            return jsonify({'success': False, 'message': 'Failed to update password.'}), 500

    except mysql.connector.Error as error:
        conn.rollback()
        print(f"Database error during password reset: {error}")
        return jsonify({'success': False, 'message': f'Database error: {error}'}), 500
    finally:
        cursor.close()
        conn.close()

# ---------ROUTE to handle POST request for updating password based on email---------
@app.route('/update_password_by_email', methods=['POST'])
def update_password_by_email():
    """Handles updating the user's password based on email with added checks."""
    data = request.get_json()
    email = data.get('email')
    new_password = data.get('new_password')
    confirm_password = data.get('confirm_password')
    verification_code = data.get('verification_code') # Expecting verification code now

    if not email or not verification_code or not new_password or not confirm_password:
        return jsonify({'success': False, 'message': 'Email, verification code, and both password fields are required.'}), 400

    if new_password != confirm_password:
        return jsonify({'success': False, 'message': 'New passwords do not match.'}), 400

    if email not in verification_codes or verification_codes[email]['code'] != verification_code:
        return jsonify({'success': False, 'message': 'Invalid verification code.'}), 400

    if datetime.utcnow() > verification_codes[email]['expiry']:
        del verification_codes[email]
        return jsonify({'success': False, 'message': 'Verification code has expired.'}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection failed.'}), 500

    cursor = conn.cursor()
    try:
        # Check if the email exists
        cursor.execute("SELECT password FROM qc_login WHERE LOWER(email) = LOWER(%s)", (email.lower(),))
        result = cursor.fetchone()

        if not result:
            return jsonify({'success': False, 'message': 'No user found with that email.'}), 404

        current_password = result[0]

        # Check if the new password is the same as the current password
        if new_password == current_password:
            return jsonify({'success': False, 'message': 'New password cannot be the same as the current password.'}), 400

        # If all checks pass, proceed with the update
        cursor.execute("""
            UPDATE qc_login
            SET password = %s, reset_token = NULL, reset_token_expiry = NULL
            WHERE LOWER(email) = LOWER(%s)
        """, (new_password, email.lower()))
        rows_updated = cursor.rowcount
        conn.commit()
        del verification_codes[email] # Remove the code after successful reset

        if rows_updated > 0:
            return jsonify({'success': True, 'message': 'Password updated successfully.'}), 200
        else:
            # This case should ideally not happen if the email existence and verification passed
            return jsonify({'success': False, 'message': 'Failed to update password.'}), 500

    except mysql.connector.Error as error:
        conn.rollback()
        print(f"Database error during password update: {error}")
        return jsonify({'success': False, 'message': f'Database error: {error}'}), 500
    finally:
        cursor.close()
        conn.close()

# ---------Signup Route-------
@app.route('/send_signup_code', methods=['POST'])
def send_signup_code():
    """Sends a verification code to the user's email for signup."""
    data = request.get_json()
    email = data.get('email')

    if not email:
        return jsonify({'success': False, 'message': 'Email is required.'}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection failed.'}), 500

    cursor = conn.cursor()
    try:
        # Check if the email is already taken
        if is_email_taken(conn, email):
            return jsonify({'success': False, 'message': 'Email address is already taken.'}), 400

        verification_code = generate_verification_code()
        verification_codes[email] = {'code': verification_code, 'expiry': datetime.utcnow() + timedelta(minutes=15)}
        send_verification_email(email, verification_code)

        return jsonify({'success': True, 'message': 'Verification code sent to your email.'}), 200

    except mysql.connector.Error as error:
        print(f"Database error sending signup code: {error}")
        return jsonify({'success': False, 'message': f'Database error: {error}'}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/signup', methods=['POST'])
def signup():
    """Signup Endpoint to Register New Users with Email Verification"""
    try:
        data = request.get_json()  # Get JSON data from the request
        print(f"Signup request received with data: {data}")
        if not data:
            print("No data provided in signup request.")
            return jsonify({'success': False, 'message': 'No data provided.'}), 400

        email = data.get('email')
        password = data.get('password')
        verification_code = data.get('verification_code')
        user_role = "user"  # Default role for signup

        if not email:
            return jsonify({'success': False, 'message': 'Email is required.'}), 400
        if not password:
            return jsonify({'success': False, 'message': 'Password is required.'}), 400
        if not verification_code:
            return jsonify({'success': False, 'message': 'Verification code is required.'}), 400

        email = email.strip()
        print(f"Signup attempt for email: '{email}' with verification code: '{verification_code}'")

        # Verify the verification code
        if email not in verification_codes or verification_codes[email]['code'] != verification_code:
            print(f"Invalid verification code provided for email: '{email}'.")
            return jsonify({'success': False, 'message': 'Invalid verification code.'}), 400

        if datetime.utcnow() > verification_codes[email]['expiry']:
            print(f"Verification code expired for email: '{email}'.")
            del verification_codes[email]
            return jsonify({'success': False, 'message': 'Verification code has expired.'}), 400

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            try:
                if is_email_taken(conn, email):
                    print(f"Email '{email}' is already taken. Returning 409 Conflict.")
                    return jsonify({'success': False, 'message': 'Email address is already taken.'}), 409

                login_id = str(uuid.uuid4())[:10]  # Generate a UUID and take the first 10 characters
                print(f"Generated login_id: {login_id}")

                cursor.execute("""
                    INSERT INTO qc_login (login_id, email, password, user_role)
                    VALUES (%s, %s, %s, %s)
                """, (login_id, email, password, user_role))  # Store plain text password
                print(f"Successfully inserted user with email: '{email}' and LOGIN_ID: {login_id}")

                conn.commit()  # Commit transaction
                print("Database transaction committed.")
                del verification_codes[email]  # Remove the used verification code
                return jsonify({'success': True, 'message': 'Successfully Signed Up!'}), 201  # Return 201 for success
            except mysql.connector.Error as error:
                conn.rollback()  # Roll back transaction in case of error
                print(f"Database error during signup: {error}")
                return jsonify({'success': False, 'message': f'Database error: {error}'}), 500
            finally:
                cursor.close()
                conn.close()
                print("Database connection closed after signup attempt.")
        else:
            print("Failed to get database connection for signup.")
            return jsonify({'success': False, 'message': 'Database connection failed.'}), 500
    except Exception as e:
        print(f"Unexpected error during signup: {e}")
        return jsonify({'success': False, 'message': f'Unexpected error: {str(e)}'}), 500
# ---------End of Signup Route-------

# ---------Login Route-------
@app.route('/login', methods=['POST'])
def login():
    """Login Endpoint to Authenticate Users and Redirect by Role (Updated for MySQL) with distinct notifications"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided.'}), 400
        email = data.get("email")
        password = data.get("password")
        selected_role = data.get("role")

        if not email or not password or not selected_role:
            return jsonify({'success': False, 'message': 'Missing required fields!'}), 400

        conn = get_db_connection()  # Assuming this function now returns a MySQL connection
        if conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    SELECT password, user_role, LOGIN_ID
                    FROM qc_login
                    WHERE LOWER(email) = LOWER(%s)
                """, (email.lower(),))  # Use %s for parameter binding in MySQL

                result = cursor.fetchone()

                if result:
                    stored_password, stored_role, login_id = result
                    if stored_password == password:
                        if stored_role == selected_role:
                            session['login_id'] = login_id  # Use 'login_id' as the key
                            session['user_role'] = stored_role

                            if stored_role == 'admin':
                                return jsonify({
                                    'success': True,
                                    'message': 'Admin login successful',
                                    'redirect': 'admin.html',
                                    'login_id': login_id,
                                    'role': stored_role
                                }), 200
                            elif stored_role == 'conductor':
                                cursor.execute("""
                                    SELECT conductor_id, bus_id
                                    FROM conductor_info  -- Changed table name here
                                    WHERE login_id = %s
                                """, (login_id,))
                                conductor_info = cursor.fetchone()
                                if conductor_info:
                                    conductor_id, bus_id = conductor_info
                                    session['conductor_id'] = conductor_id
                                    redirect_url = f"conductor.html?bus_id={bus_id}"
                                    return jsonify({
                                        'success': True,
                                        'message': 'Login successful',
                                        'redirect': redirect_url,
                                        'conductor_id': conductor_id,
                                        'role': stored_role,
                                        'bus_id': bus_id
                                    }), 200
                                else:
                                    return jsonify({'success': False, 'message': 'Conductor information not found.'}), 401
                            elif stored_role == 'user':
                                return jsonify({
                                    'success': True,
                                    'message': 'User login successful',
                                    'redirect': 'userinterface.html',
                                    'login_id': login_id,
                                    'role': stored_role
                                }), 200
                            else:
                                return jsonify({'success': False, 'message': 'Invalid user role found in database.'}), 401
                        else:
                            return jsonify({'success': False, 'message': 'Incorrect user role selected for this account.'}), 401
                    else:
                        return jsonify({'success': False, 'message': 'Incorrect email address or password.'}), 401
                else:
                    return jsonify({'success': False, 'message': 'Incorrect email address or password.'}), 401
            except mysql.connector.Error as error:  # Catch MySQL-specific errors
                return jsonify({'success': False, 'message': f'Database error: {error}'}), 500
            finally:
                cursor.close()
                conn.close()
        else:
            return jsonify({'success': False, 'message': 'Database connection failed.'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': f'Unexpected error: {str(e)}'}), 500
# ---------End of Login Route-------

# ---------Logout Route-------
@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    session.pop('user_role', None)
    session.pop('conductor_id', None)
    return jsonify({'success': True, 'message': 'Logged out successfully.'}), 200
# ---------End of Logout Route-------

# ---------HTML Routes-------
@app.route('/login.html')
def login_html():
    """Serve login.html"""
    return render_template('login.html')
# ---------end of login_html-------

@app.route('/signup.html')
def signup_html():
    """Serve signup.html"""
    return render_template('signup.html')
# ---------end of signup_html-------

@app.route('/')
def index():
    """Serve the login.html file when the root URL is accessed"""
    return render_template('login.html')
# ---------end of index-------

@app.route('/forgot-password')
def forgot_password():
    """Serve forgotpassword.html"""
    return render_template('forgotpassword.html')
# ---------end of forgot_password-------

@app.route('/admin.html')
def admin_page():
    """Serve admin.html"""
    return render_template('admin.html')
# ---------end of admin_page-------

@app.route('/conductor.html')
def conductor_page():
    """Serve conductor.html"""
    return render_template('conductor.html')
# ---------end of conductor_page-------

@app.route('/userinterface.html')
def user_interface_page():
    """Serve userinterface.html"""
    return render_template('userinterface.html')
# ---------end of user_interface_page-------

import mysql.connector
from flask import request, jsonify

# Assuming you have a function get_db_connection() defined elsewhere
# that returns a MySQL connection object

# ---------Add Bus Information Route-------
@app.route('/add_bus_info', methods=['POST'])
def add_bus_info():
    """Endpoint to add new bus information, conductor, and login details."""
    conn = None
    cursor = None
    try:
        data = request.get_json()
        print(f"Received data: {data}")

        bus_id = data.get('bus_id')
        plate_number = data.get('plate_number')
        seat_capacity = data.get('seat_capacity')
        name = data.get('name')
        email = data.get('email')
        password = data.get('password')

        if not bus_id or not plate_number or not name or not email or not password:
            return jsonify({'success': False, 'message': 'Please fill up all the details (except seat capacity).'}), 400

        # Set default seat_capacity if not provided
        if seat_capacity is None:
            seat_capacity = 53
        else:
            try:
                seat_capacity = int(seat_capacity)
                if seat_capacity <= 0:
                    return jsonify({'success': False, 'message': 'Seat capacity must be a positive number.'}), 400
            except ValueError:
                return jsonify({'success': False, 'message': 'Invalid seat capacity format.'}), 400

        conn = get_db_connection()
        if conn is None:
            return jsonify({'success': False, 'message': 'Database connection failed.'}), 500

        cursor = conn.cursor()
        try:
            # Check if Bus ID or Plate Number already exists
            cursor.execute("SELECT 1 FROM bus_info WHERE bus_id = %s", [bus_id])
            if cursor.fetchone():
                return jsonify({'success': False, 'message': 'Bus ID already exists.'}), 400
            cursor.execute("SELECT 1 FROM bus_info WHERE plate_number = %s", [plate_number])
            if cursor.fetchone():
                return jsonify({'success': False, 'message': 'Plate Number already exists.'}), 400

            # Check if Email already exists
            cursor.execute("SELECT 1 FROM qc_login WHERE email = %s", [email])
            if cursor.fetchone():
                return jsonify({'success': False, 'message': 'Email already exists.'}), 400

            # 1. Insert into qc_login
            login_id = str(uuid.uuid4())[:10]  # Generate a unique 10-character login_id
            cursor.execute(
                "INSERT INTO qc_login (login_id, email, password, user_role) VALUES (%s, %s, %s, 'conductor')",
                [login_id, email, password]
            )

            # 2. Insert into bus_info
            cursor.execute(
                "INSERT INTO bus_info (bus_id, plate_number, seat_capacity) VALUES (%s, %s, %s)",
                [bus_id, plate_number, seat_capacity]
            )

            # 3. Insert into conductor_info
            conductor_id = str(uuid.uuid4())[:10]  # Generate a unique 10-character conductor_id
            cursor.execute(
                "INSERT INTO conductor_info (conductor_id, conductor_name, login_id, bus_id) VALUES (%s, %s, %s, %s)",
                [conductor_id, name, login_id, bus_id]
            )

            # 4. Insert into assignment
            active_bus_id = str(uuid.uuid4())  # Generate a unique active_bus_id
            cursor.execute("""
                INSERT INTO assignment (active_bus_id, bus_id, conductor_id, available_seat, eta, next_stop, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, [active_bus_id, bus_id, conductor_id, seat_capacity, 'N/A', 'N/A', ''])

            conn.commit()
            print(f"Bus inserted with ID: {bus_id}, Conductor ID: {conductor_id}, Login ID: {login_id}, Active Bus ID: {active_bus_id}, Seat Capacity: {seat_capacity}")
            return jsonify({
                'success': True,
                'message': f'Successfully added Bus ID: {bus_id}, Conductor ID: {conductor_id}, Login ID: {login_id} and assigned bus with Active Bus ID: {active_bus_id} (Seat Capacity: {seat_capacity})!'
            }), 201

        except mysql.connector.Error as error:
            if conn:
                conn.rollback()
            print(f"DB error: {error}")
            return jsonify({'success': False, 'message': f'DB error: {error}'}), 500

        finally:
            if cursor:
                cursor.close()
            if conn and conn.is_connected():
                conn.close()

    except Exception as e:
        print(f"Request error: {e}")
        return jsonify({'success': False, 'message': f'Request error: {e}'}), 500
# ---------End of Add Bus Information Route-------

#----------Conductor Update Bus Info Route-------
@app.route('/conductor/update_bus_info', methods=['POST'])
def conductor_update_bus_info():
    """
    Allows a conductor to update ETA, available seats, next stop, and notes
    for their assigned active bus, identified by their login session.
    """
    conn = None
    cursor = None
    try:
        data = request.get_json()
        print(f"Received conductor update data: {data}")

        eta = data.get('eta')
        available_seat = data.get('available_seat')
        next_stop = data.get('next_stop')
        notes = data.get('notes')

        if not eta or available_seat is None or not next_stop:
            return jsonify({'success': False, 'message': 'Missing required fields.'}), 400

        conductor_login_id = session.get('login_id') # Get login_id from session
        if not conductor_login_id or session.get('user_role') != 'conductor':
            return jsonify({'success': False, 'message': 'Unauthorized access or conductor not logged in.'}), 401

        conn = get_db_connection()
        if conn is None:
            return jsonify({'success': False, 'message': 'Database connection failed.'}), 500

        cursor = conn.cursor()
        try:
            # 1. Get the BUS_ID associated with the conductor's LOGIN_ID
            cursor.execute("""
                SELECT ci.bus_id
                FROM conductor_info ci
                WHERE ci.login_id = %s
            """, [conductor_login_id])
            result = cursor.fetchone()

            if not result or not result[0]:
                return jsonify({'success': False, 'message': 'Bus ID not found for this conductor.'}), 404

            bus_id = result[0]

            # 2. Update the assignment table for the conductor's assigned bus
            cursor.execute("""
                UPDATE assignment
                SET eta = %s,
                    available_seat = %s,
                    next_stop = %s,
                    notes = %s
                WHERE bus_id = %s AND conductor_id = (
                    SELECT conductor_id
                    FROM conductor_info
                    WHERE login_id = %s
                )
            """, [eta, available_seat, next_stop, notes, bus_id, conductor_login_id])

            rows_updated = cursor.rowcount
            conn.commit()

            if rows_updated > 0:
                return jsonify({'success': True, 'message': 'Bus information updated successfully.'}), 200
            else:
                return jsonify({'success': False, 'message': 'Could not update bus information. Please try again.'}), 400

        except mysql.connector.Error as error:
            if conn:
                conn.rollback()
            print(f"DB error during update: {error}")
            return jsonify({'success': False, 'message': f'Database error: {error}'}), 500

        finally:
            if cursor:
                cursor.close()
            if conn and conn.is_connected():
                conn.close()

    except Exception as e:
        print(f"Request error during update: {e}")
        return jsonify({'success': False, 'message': f'Request error: {e}'}), 500
    #----------End of Conductor Update Bus Info Route-------

    # ---------Commuter View Bus Info by Stop Route-------
@app.route('/commuter/bus_info_by_stop/<next_stop>', methods=['GET'])
def get_bus_info_by_stop(next_stop):
    """
    Allows a commuter to view the ETA, available seats, and notes
    for the first active bus whose NEXT_STOP matches the selected stop.
    """
    conn = None
    cursor = None
    try:
        print(f"Fetching bus info for stop: {next_stop}")
        conn = get_db_connection()
        if conn is None:
            return jsonify({'success': False, 'message': 'Database connection failed.'}), 500

        cursor = conn.cursor()
        try:
            query = """
                SELECT eta, available_seat, notes
                FROM assignment
                WHERE next_stop = %s
                LIMIT 1
            """
            print(f"Executing query: {query} with parameter: [{next_stop}]")
            cursor.execute(query, [next_stop])
            bus_info = cursor.fetchone()
            print(f"Query result: {bus_info}")

            if bus_info:
                eta, available_seat, notes = bus_info
                return jsonify({
                    'success': True,
                    'bus_info': {
                        'eta': eta,
                        'available_seats': available_seat,
                        'notes': notes
                    }
                }), 200
            else:
                return jsonify({'success': False, 'message': f'No active bus found for the stop: {next_stop}'}), 404

        except mysql.connector.Error as error:
            print(f"DB error during fetching bus info: {error}")
            return jsonify({'success': False, 'message': f'Database error: {error}'}), 500

        finally:
            if cursor:
                cursor.close()
            if conn and conn.is_connected():
                conn.close()
                print("Database connection closed after fetching bus info.")

    except Exception as e:
        print(f"Request error during fetching bus info: {e}")
        return jsonify({'success': False, 'message': f'Request error: {e}'}), 500
# ---------End of Commuter View Bus Info by Stop Route-------

# ---------Get bus information route-------
@app.route('/get_all_bus_info')
def get_all_bus_info():
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if conn is None:
            return jsonify({'success': False, 'message': 'Database connection failed.'}), 500

        cursor = conn.cursor()
        try:
            # Execute a JOIN query to fetch data from all three tables
            cursor.execute("""
                SELECT
                    b.bus_id,
                    b.plate_number,
                    c.conductor_name,
                    l.email
                FROM
                    bus_info b
                JOIN
                    conductor_info c ON b.bus_id = c.bus_id
                JOIN
                    qc_login l ON c.login_id = l.login_id
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
                    'Password': '**********'  # Masked password for display
                })

            return jsonify({'success': True, 'data': bus_data_list}), 200

        except mysql.connector.Error as error:
            print(f"DB error: {error}")
            return jsonify({'success': False, 'message': f'Database error: {error}'}), 500

        finally:
            if cursor:
                cursor.close()
            if conn and conn.is_connected():
                conn.close()

    except Exception as e:
        print(f"Request error: {e}")
        return jsonify({'success': False, 'message': f'Request error: {e}'}), 500
    # ---------End of Get bus information route-------

    #-------------------------------DELETE ROUTE------------------------------------

@app.route('/delete_bus_info/<bus_id>', methods=['DELETE'])
def delete_bus_info(bus_id):
    """Deletes bus information from all related tables, including assignment."""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection failed.'}), 500
    cursor = conn.cursor()
    try:
        # Find the conductor_id associated with the bus_id
        cursor.execute("""
            SELECT conductor_id
            FROM conductor_info
            WHERE bus_id = %s
        """, [bus_id])
        conductor_result = cursor.fetchone()
        conductor_id_to_delete = conductor_result[0] if conductor_result else None

        # Find the login_id associated with the bus_id
        cursor.execute("""
            SELECT login_id
            FROM conductor_info
            WHERE bus_id = %s
        """, [bus_id])
        conductor_login_result = cursor.fetchone()
        login_id_to_delete = conductor_login_result[0] if conductor_login_result else None

        # Delete records from assignment based on bus_id
        cursor.execute("DELETE FROM assignment WHERE bus_id = %s", [bus_id])
        assignment_deleted_by_bus = cursor.rowcount > 0

        # Delete records from assignment based on conductor_id
        assignment_deleted_by_conductor = False
        if conductor_id_to_delete:
            cursor.execute("DELETE FROM assignment WHERE conductor_id = %s", [conductor_id_to_delete])
            assignment_deleted_by_conductor = cursor.rowcount > 0

        # Delete records from conductor_info for the given bus_id
        cursor.execute("DELETE FROM conductor_info WHERE bus_id = %s", [bus_id])
        conductor_deleted = cursor.rowcount > 0

        # Delete the record from bus_info
        cursor.execute("DELETE FROM bus_info WHERE bus_id = %s", [bus_id])
        bus_deleted = cursor.rowcount > 0

        # Delete the corresponding record from qc_login if login_id was found
        login_deleted = False
        if login_id_to_delete:
            cursor.execute("DELETE FROM qc_login WHERE login_id = %s", [login_id_to_delete])
            login_deleted = cursor.rowcount > 0

        conn.commit()

        if bus_deleted or conductor_deleted or login_deleted or assignment_deleted_by_bus or assignment_deleted_by_conductor:
            return jsonify({'success': True, 'message': f'Information for Bus ID {bus_id} and related records deleted successfully.'}), 200
        else:
            return jsonify({'success': False, 'message': f'No information found for Bus ID {bus_id}.'}), 404

    except mysql.connector.Error as error:
        if conn:
            conn.rollback()
        print(f"Database error during deletion: {error}")
        return jsonify({'success': False, 'message': f'Database error during deletion: {error}'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()

#-------------------------------END OF DELETE ROUTE------------------------------------

#-------------------------------UPDATE STATUS BY EMAIL ROUTE (CORRECTED WITH EVEN MORE LOGGING)------------------------------------
@app.route('/update_bus_status_by_email', methods=['POST'])
def update_bus_status_by_email():
    """Updates the status of a specific bus in the bus_info table based on the email in qc_login."""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection failed.'}), 500
    cursor = conn.cursor()
    try:
        data = request.get_json()
        email = data.get('email')
        new_status = data.get('bus_status')

        if not email:
            return jsonify({'success': False, 'message': 'Email address is required.'}), 400
        if not new_status or new_status not in ['active', 'inactive']:
            return jsonify({'success': False, 'message': 'Invalid bus status provided.'}), 400

        # First, let's execute the subquery separately to see what bus_id we get
        find_bus_id_sql = """
        SELECT ci.bus_id
        FROM conductor_info ci
        JOIN qc_login ql ON ci.login_id = ql.login_id
        WHERE ql.email = %s
        """
        cursor.execute(find_bus_id_sql, [email])
        bus_id_result = cursor.fetchone()

        if bus_id_result:
            found_bus_id = bus_id_result[0]
            print(f"Found bus_id from subquery: {found_bus_id}")  # Added log

            # Now, try to update the bus_status
            update_status_sql = "UPDATE bus_info SET bus_status = %s WHERE bus_id = %s"
            values = (new_status, found_bus_id)
            print(f"Executing UPDATE SQL: {update_status_sql}, with values: {values}")  # Added log

            cursor.execute(update_status_sql, values)
            rows_affected = cursor.rowcount
            print(f"Rows affected BEFORE commit: {rows_affected}")  # Added log

            conn.commit()
            print(f"Commit successful.")  # Added log
            print(f"Rows affected AFTER commit: {cursor.rowcount}") # Check again after commit

            if rows_affected > 0:
                return jsonify({'success': True, 'message': f'Status updated for bus associated with email {email} to {new_status}.'}), 200
            else:
                return jsonify({'success': False, 'message': f'No bus found with bus_id {found_bus_id} to update.'}), 404
        else:
            return jsonify({'success': False, 'message': f'No bus found associated with email {email}.'}), 404

    except mysql.connector.Error as error:
        if conn:
            conn.rollback()
        print(f"Database error during status update: {error}")
        return jsonify({'success': False, 'message': f'Database error during status update: {error}'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()

# ... (other routes remain the same) ...

#-------------------------------END OF UPDATE STATUS BY EMAIL ROUTE------------------------------------

if __name__ == '__main__':
    app.run()
