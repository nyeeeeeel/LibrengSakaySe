import cx_Oracle
from flask import current_app

class Database:
    def __init__(self, user, password, host, port, service_name):
        self.user = user
        self.password = password
        self.host = host
        self.port = port
        self.service_name = service_name
        self.connection = None

    def connect(self):
        try:
            dsn_tns = cx_Oracle.makedsn(self.host, self.port, service_name=self.service_name)
            self.connection = cx_Oracle.connect(self.user, self.password, dsn_tns)
            current_app.logger.info("Database connection established.")
            return self.connection
        except cx_Oracle.Error as error:
            current_app.logger.error(f"Error connecting to Oracle: {error}")
            return None

    def execute_query(self, query, params=None, fetchone=False):
        cursor = None
        try:
            if self.connection:
                cursor = self.connection.cursor()
                cursor.execute(query, params or {})
                if fetchone:
                    return cursor.fetchone()
                else:
                    return cursor.fetchall()
            else:
                current_app.logger.error("No database connection.")
                return None
        except cx_Oracle.Error as error:
            current_app.logger.error(f"Error executing query '{query}': {error}")
            return None
        finally:
            if cursor:
                cursor.close()

    def close(self):
        if self.connection:
            self.connection.close()
            current_app.logger.info("Database connection closed.")
            self.connection = None

# Example usage (you might initialize this in your app.py):
# db = Database(user='your_user', password='your_password', host='your_host', port=1521, service_name='your_service_name')