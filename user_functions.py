import hashlib
import sqlite3
from flask import Flask, flash, render_template, request, redirect, url_for, session, send_from_directory
import os
import time
import random
import email_functions

class track_incorrect_login:
    def __init__(self):
        self.connected_ips = {}

    def add_ip(self, ip):
        if ip not in self.connected_ips.keys():
            self.connected_ips[ip] = [time.time()]
        else:
            self.connected_ips[ip].append(time.time())
    def remove_ip(self, ip):
        if ip in self.connected_ips:
            del self.connected_ips[ip]

    def is_connected(self, ip):
        return ip in self.connected_ips
    def is_ip_blocked(self, ip,t = time.time()):    
        if ip in self.connected_ips:
            timestamps = self.connected_ips[ip]
            # 5 dakika içinde 5 deneme varsa engelle
            if len(timestamps) >= 5 and (time.time() - timestamps[-5] ) <= 300:
                return True
        return False
    
accounts_waiting_for_confirmation = {}

def add_account_waiting_for_confirmation(username,email,password,token):
   accounts_waiting_for_confirmation[token] = {
        'username': username,
        'email': email,
        'password_sha': string_to_sha256(password)
   }
   print(accounts_waiting_for_confirmation)

def add_account_to_database(username,email,password_sha):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    try:
        cursor.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)', (username, email, password_sha))
        conn.commit()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        id = cursor.fetchone()[0]
        os.mkdir('media/' + str(id))
        conn.close()
        return True

    except sqlite3.IntegrityError as e:
        # Eğer UNIQUE kısıtlaması ihlali olursa
        print(f"Hata: {e}. Email zaten mevcut!")
        conn.close()

        return False

    

    


my_track_incorrect_login = track_incorrect_login()


def string_to_sha256(input_string):
    sha256_hash = hashlib.sha256()
    sha256_hash.update(input_string.encode('utf-8'))
    return sha256_hash.hexdigest()

def create_user(request ):
    
    if request.method == 'POST':
        username = request.form['username']
        username = username.strip().lower()
        password1 = request.form['password1']
        password2 = request.form['password2']
        email = request.form['email']
        email = email.strip().lower()   
        local, domain = email.split("@")
        if "+" in local:
            local = local.split("+")[0]  # "+" işaretinden öncesini al
        email = f"{local}@{domain}"

        

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ? or email = ?', (username,email))
        user = cursor.fetchone()
        
        
        if user is None:
            if password1 == password2:
                #cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, string_to_sha256(password1)))
                #conn.commit()
                #cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
                #id = cursor.fetchone()[0]
                #os.mkdir('media/' + str(id))

                #create token for email confirmation
                token = string_to_sha256(username + password1 + str(time.time())+str(random.randint(0,100000)))
                add_account_waiting_for_confirmation(username, email, password1, token)
                #send email
                email_functions.send_token_to_email(email, token)
               

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
            if user[1] == username:
                return render_template('create_user.html', error="Username already exists")
            elif user[4] == email:
                return render_template('create_user.html', error="Email already exists")
            
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





def login(request):
    username = request.form['username']
    password = request.form['password']
    username = username.lower()

    ip = request.remote_addr
    # Check if the IP is blocked
    if my_track_incorrect_login.is_ip_blocked(ip):
        return render_template('login.html', error="Too many incorrect login attempts You are blocked. Please try again later.")
    else:
        my_track_incorrect_login.add_ip(ip)

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, string_to_sha256(password)))
    user = cursor.fetchone()
    conn.close()

    if user is not None:
        session['logged_in'] = True
        session['username'] = user[1] 
        session['user_id'] = user[0]
        session['email'] = user[4]
        session['used_storage'] = int(get_used_storage(user[0]))
        session['storage_limit'] = user[3]
        session.permanent = False
        return redirect(url_for('home'))
    else:
        return render_template('login.html', error="Invalid Username or Password")
    


def check_token(token):
    if token in accounts_waiting_for_confirmation.keys():
        value = accounts_waiting_for_confirmation[token]
        username = value['username']    
        email = value['email']
        password_sha = value['password_sha']
        # Add the account to the database
        is_success = add_account_to_database(username,email,password_sha)
        if not is_success:
            return "This email is already registered"
        #os.mkdir('media/' + str(id))
        # Remove the account from the waiting list
        del accounts_waiting_for_confirmation[token]
        return True
    else:
        return False