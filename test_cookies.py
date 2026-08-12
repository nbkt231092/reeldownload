import sqlite3
import os

db_path = r'D:\Just9stories\PROFILE_DATA\412d2c74-76e7-4b02-a42e-32b59176acea\Default\Network\Cookies'
if not os.path.exists(db_path):
    print(f"DB not found: {db_path}")
else:
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT host_key, name, length(value), length(encrypted_value) FROM cookies WHERE host_key LIKE '%facebook.com'")
        for row in cursor.fetchall():
            print(row)
    except Exception as e:
        print(e)
