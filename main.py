from flask import Flask, flash, render_template, request, redirect, url_for, session, send_from_directory,jsonify,send_file
import sqlite3
import os
import user_functions




if not os.path.exists('media'):
    os.mkdir('media')   # Medya klasörünü oluştur
#sqlite3.connect('database.db') # Veritabanı dosyasını oluştur
conn = sqlite3.connect('database.db')
cursor = conn.cursor()
cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY AUTOINCREMENT,username varchar(20), password varchar(70), storage_limit INTEGER default 500)')
cursor.execute('CREATE TABLE IF NOT EXISTS files (file_id INTEGER PRIMARY KEY AUTOINCREMENT, file_name varchar(70),title varchar(100), file_size INTEGER, user_id INTEGER, FOREIGN KEY(user_id) REFERENCES users(user_id))')
cursor.execute('CREATE TABLE IF NOT EXISTS folders (folder_id INTEGER PRIMARY KEY AUTOINCREMENT, folder_name varchar(50), user_id INTEGER, FOREIGN KEY(user_id) REFERENCES users(user_id))')
cursor.execute('CREATE TABLE IF NOT EXISTS shared_files (shared_id INTEGER PRIMARY KEY AUTOINCREMENT, file_id INTEGER, user_id INTEGER, FOREIGN KEY(file_id) REFERENCES files(file_id), FOREIGN KEY(user_id) REFERENCES users(user_id))')
cursor.execute('CREATE TABLE IF NOT EXISTS shared_folders (folder_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, permissions varchar(5), FOREIGN KEY(user_id) REFERENCES users(user_id))')
#permissions: "rud" read upload delete 
#if someone has "ru" permission read + upload but can't delete the file


conn.commit()
cursor.close()
conn.close()

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Güvenli bir oturum anahtarı
MAGIC_STRING = b"!@#$%^&*()_+"



@app.route('/')
def index():
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        username = username.lower()

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, user_functions.string_to_sha256(password)))
        user = cursor.fetchone()
        conn.close()

        if user is not None:
            session['logged_in'] = True
            session['username'] = user[1] 
            session['user_id'] = user[0]

            session.permanent = False
            return redirect(url_for('home'))
        else:
            return render_template('login.html', error="Invalid Username or Password")

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    session.pop('user_id', None)

    return redirect(url_for('login'))


@app.route('/create-account', methods=['GET', 'POST'])
def create_user():
    return user_functions.create_user(request)


@app.route('/home', methods=['GET', 'POST'])
def home():
    if 'logged_in' not in session or not session['logged_in']:
        return redirect(url_for('login'))
    else:
        return render_template('main.html')    
    
@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if 'logged_in' not in session or not session['logged_in']:
        return redirect(url_for('login'))
    else:
        return render_template('settings.html',username = session['username'])    


@app.route('/my_drive', methods=['GET', 'POST'])
def my_drive():
    if 'logged_in' not in session or not session['logged_in']:
        return redirect(url_for('login'))
    else:
        return redirect(url_for('browse_folder', path=str(session['user_id'])))

@app.route("/browse_folder/<path:path>", methods=["POST", "GET"])
def browse_folder(path):
    if 'logged_in' not in session or not session['logged_in']:
        return redirect(url_for('login'))
    else:
        if session['user_id'] != int(path.split('/')[0]):
            #return jsonify({"success": False, "message": "You are not authorized to view this folder"})
            return render_template("my_drive.html", error = "You are not authorized to view this folder")
        actual_path = 'media/' + path
        if not os.path.exists(actual_path):
            return jsonify({"success": False, "message": "Folder not found"})
        
        items = os.listdir(actual_path)
        item_list = []
        for i in items:
            item_list.append({
                'name': i,
                'is_file': os.path.isfile(actual_path + '/' + i),
                'id': 1,
                'file_size_in_bytes': os.path.getsize(actual_path + '/' + i),
                'file_size': user_functions.find_appropriate_file_size(os.path.getsize(actual_path + '/' + i)),
                'path' : path + '/' + i

            })

        path_list = []
        split_path = path.split('/')
        p = split_path[0]

        for i in range(len(split_path)):
            if i == 0:
                continue
            p+= '/' + split_path[i]
            path_list.append({"name": split_path[i], "path": p})
            
        return render_template("my_drive.html", item_list=item_list, path_list=path_list,current_folder_path = path)


@app.route("/browse_file<path:path>", methods=["POST", "GET"])
def browse_file(path):
    if 'logged_in' not in session or not session['logged_in']:
        return redirect(url_for('login'))
    else:
        if not os.path.isfile('media/' + path):
            return jsonify({"success": False, "message": "File not found"})
        
        with open('media/' + path, "rb") as f:
            file_data = f.read()

        if file_data.startswith(MAGIC_STRING):
            file_data = file_data[len(MAGIC_STRING):]  # Başındaki özel karakterleri kaldır
        else:
            return "kanka bu iste bi is var ya dosya sifreli degil gonderemem kb"

        import io
        decrypted_file_io = io.BytesIO(file_data)
        decrypted_file_io.seek(0)


        
        return send_file(decrypted_file_io, as_attachment=True, download_name=path.split('/')[-1])
        #return send_file('media/'+ path, as_attachment=True, mimetype="application/octet-stream")
        #return send_from_directory('media/', path)


@app.route("/create_folder/<path:path>", methods=["POST"])
def create_folder(path):
    folder_name = request.json.get("name")
    folder_name = folder_name.replace(' ', '_')
    if user_functions.is_valid_filename(folder_name):
        os.mkdir('media/' + path + '/' + folder_name)
    else:
        return jsonify({"success": False, "message": "Invalid folder name"})

    return jsonify({"success": True, "message": "Folder created"})

@app.route("/delete<path:path>", methods=["POST"])
def delete_item(path):
    if os.path.isfile('media/' + path):
        os.remove('media/' + path)
    else:
        os.rmdir('media/' + path)
    return jsonify({"success": True, "message": f"Item {path} deleted"})




@app.route("/update/<path:path>", methods=["POST"])
def update_item(path):
    new_name = request.json.get("name")
    last = path.split('/')[-1]
    if os.path.isfile('media/' + path):
        os.rename('media/' + path, 'media/' + path[:len(path)-len(last)]+new_name+"."+last.split('.')[-1])
    else:
        path_ = path[:len(path)-len(last)]
        print('media/' + path_+new_name)
        os.rename('media/' + path, 'media/' + path_+new_name)

    return jsonify({"success": True, "message": f"Item {path} updated"})



"""
@app.route("/upload_file/<path:path>", methods=["POST"])
def upload_file(path):
    file = request.files['file']
    file.save('media/' + path + '/' + file.filename)
    return jsonify({"success": True, "message": "File uploaded"})
"""


@app.route("/upload_file/<path:path>", methods=["POST", "GET"])
def upload_file(path):
    if "logged_in" not in session or not session["logged_in"]:
        return redirect(url_for("login"))
    if request.method == "POST":
        files = request.files.getlist('file')  # Tüm dosyaları al
        print(files)


        for file in files:
            if file.filename == '':
                return jsonify({"error": "No selected file"}), 400

            file_path = 'media/' + path + '/' + file.filename
            file_data = file.read()
            with open(file_path, "wb") as f:
                f.write(MAGIC_STRING + file_data)

        return jsonify({"message": "File stored securely"}), 200
    


def __main__():
    app.run(host='0.0.0.0', port=8000,debug=True)

if __name__ == '__main__':  
    __main__()
