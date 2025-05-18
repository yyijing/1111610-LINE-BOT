import sqlite3

def init_db():
    conn = sqlite3.connect('chat_history.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS history
                (id INTEGER PRIMARY KEY, user_id TEXT, message TEXT)''')
    conn.commit()
    conn.close()

def save_message(user_id, message):
    conn = sqlite3.connect('chat_history.db')
    c = conn.cursor()
    c.execute("INSERT INTO history (user_id, message) VALUES (?, ?)", (user_id, message))
    conn.commit()
    conn.close()

def delete_history(user_id):
    conn = sqlite3.connect('chat_history.db')
    c = conn.cursor()
    c.execute("DELETE FROM history WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()