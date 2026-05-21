import os
import sqlite3

def view_sqlite_db(db_file):
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        # Get a list of all tables in the database
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()

        if not tables:
            print(f"No tables found in {db_file}")
            return

        print(f"Tables in '{db_file}':")
        for table_name_tuple in tables:
            table_name = table_name_tuple[0]
            print(f"\n--- Table: {table_name} ---")

            # Get column names
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns_info = cursor.fetchall()
            column_names = [col[1] for col in columns_info]
            print(f"Columns: {', '.join(column_names)}")

            # Fetch and print some data (e.g., first 10 rows)
            try:
                cursor.execute(f"SELECT * FROM {table_name} LIMIT 10;")
                rows = cursor.fetchall()
                if rows:
                    for row in rows:
                        print(row)
                else:
                    print("(No data in this table or no rows returned)")
            except sqlite3.OperationalError as e:
                print(f"Error querying table {table_name}: {e}")

    except sqlite3.Error as e:
        print(f"Error connecting to or querying database: {e}")
    finally:
        if conn:
            conn.close()

# --- Usage ---
# Replace 'your_database.db' with the actual path to your SQLite database file
db_path = os.environ.get('META_DB_PATH', 'screencaps.db')
view_sqlite_db(db_path)