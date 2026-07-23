import sqlite3

conn = sqlite3.connect('blog.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
print("ACTIVE DATABASE TABLES:", [row[0] for row in cursor.fetchall()])
conn.close()
