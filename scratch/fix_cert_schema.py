from app import app, db, Certificate
import sqlite3

def fix_schema():
    with app.app_context():
        # Get the path to the database
        db_path = 'instance/bluereef.db'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        try:
            # 1. Rename existing table
            cursor.execute("ALTER TABLE certificate RENAME TO certificate_old")

            # 2. Create new table with user_id NULLABLE
            cursor.execute("""
                CREATE TABLE certificate (
                    id INTEGER NOT NULL, 
                    user_id INTEGER, 
                    course_name VARCHAR(100) NOT NULL, 
                    issue_date DATETIME, 
                    cert_ref VARCHAR(50), 
                    customer_email VARCHAR(100), 
                    PRIMARY KEY (id), 
                    FOREIGN KEY(user_id) REFERENCES user (id), 
                    UNIQUE (cert_ref)
                )
            """)

            # 3. Copy data
            # Note: We'll try to guess customer_email from user table if it's missing in old table
            cursor.execute("""
                INSERT INTO certificate (id, user_id, course_name, issue_date, cert_ref, customer_email)
                SELECT c.id, c.user_id, c.course_name, c.issue_date, c.cert_ref, 
                       COALESCE(c.customer_email, u.email)
                FROM certificate_old c
                LEFT JOIN user u ON c.user_id = u.id
            """)

            # 4. Drop old table
            cursor.execute("DROP TABLE certificate_old")

            conn.commit()
            print("Successfully updated certificate table schema and backfilled emails!")
        except Exception as e:
            conn.rollback()
            print(f"Error: {e}")
        finally:
            conn.close()

if __name__ == "__main__":
    fix_schema()
