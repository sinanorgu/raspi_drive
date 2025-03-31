import hashlib
import sqlite3
from flask import Flask, flash, render_template, request, redirect, url_for, session, send_from_directory
import os
def string_to_sha256(input_string):
    sha256_hash = hashlib.sha256()
    sha256_hash.update(input_string.encode('utf-8'))
    return sha256_hash.hexdigest()

def create_user(request ):
    
    if request.method == 'POST':
        username = request.form['username']
        password1 = request.form['password1']
        password2 = request.form['password2']
        

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        
        if user is None:
            if password1 == password2:
                cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, string_to_sha256(password1)))
                conn.commit()

                cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
                id = cursor.fetchone()[0]
                os.mkdir('media/' + str(id))

                cursor.close()
                conn.close()
                return render_template('create_user.html', message="User created successfully")

            else:
                cursor.close()
                conn.close()
                return render_template('create_user.html', error="Passwords do not match")
       
        else:
            cursor.close()
            conn.close()

            return render_template('create_user.html', error="Username already exists")

    return render_template('create_user.html')

def find_appropriate_file_size(file_size_byte):
    if file_size_byte < 1024:
        return str(file_size_byte) + " Byte"
    elif file_size_byte < 1000 * 1000:
        return str(round(file_size_byte / 1000,2)) + " KB"
    elif file_size_byte < 1000 * 1000 * 1000:
        return str(round(file_size_byte / (1000 * 1000),2)) + " MB"
    else:
        return str(round(file_size_byte / (1000 * 1000 * 1000),2)) + " GB"



def is_valid_filename(filename):
    invalid_chars = r'\/:*?"<>|'
    
    if any(char in filename for char in invalid_chars):
        return False
    return True


def get_used_storage(user_id):
    storage = 0
    for root, dirs, files in os.walk('media/' + str(user_id)):
        for file in files:
            storage += os.path.getsize(os.path.join(root, file))
    return storage