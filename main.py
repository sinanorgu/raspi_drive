from flask import Flask, flash, render_template, request, redirect, url_for, session, send_from_directory,jsonify,send_file
import sqlite3
import os
import user_functions
import file_functions
from file_functions import MAGIC_STRING


if not os.path.exists('media'):
    os.mkdir('media')   # Medya klasörünü oluştur
#sqlite3.connect('database.db') # Veritabanı dosyasını oluştur
conn = sqlite3.connect('database.db')
cursor = conn.cursor()
cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY AUTOINCREMENT,username varchar(20), password varchar(70), storage_limit INTEGER default 500 , email varchar(50), is_admin BOOLEAN default 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
cursor.execute('CREATE TABLE IF NOT EXISTS files (file_id INTEGER PRIMARY KEY AUTOINCREMENT, file_name varchar(70),title varchar(100), file_size INTEGER, user_id INTEGER, FOREIGN KEY(user_id) REFERENCES users(user_id) on delete set null)')
cursor.execute('CREATE TABLE IF NOT EXISTS folders (folder_id INTEGER PRIMARY KEY AUTOINCREMENT, folder_name varchar(50), user_id INTEGER, FOREIGN KEY(user_id) REFERENCES users(user_id))')
cursor.execute('CREATE TABLE IF NOT EXISTS shared_files (shared_id INTEGER PRIMARY KEY AUTOINCREMENT, file_id INTEGER, user_id INTEGER, FOREIGN KEY(file_id) REFERENCES files(file_id) ON DELETE CASCADE, FOREIGN KEY(user_id) REFERENCES users(user_id) on delete set null)')
cursor.execute('CREATE TABLE IF NOT EXISTS shared_folders (shared_id INTEGER PRIMARY KEY AUTOINCREMENT,folder_id INTEGER, user_id INTEGER, permissions varchar(5), FOREIGN KEY(user_id) REFERENCES users(user_id) on delete set null,  FOREIGN KEY(folder_id) REFERENCES folders(folder_id) on delete CASCADE) ')

#permissions: "rud" read upload delete 
#if someone has "ru" permission read + upload but can't delete the file


conn.commit()
cursor.close()
conn.close()

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Güvenli bir oturum anahtarı



@app.route('/')
def index():
    if 'logged_in' not in session or not session['logged_in']:
        return redirect(url_for('login'))
    else:
        return redirect(url_for('home'))
    

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        return user_functions.login(request)

    return render_template('login.html')



@app.route('/confirm_email/<token>', methods=['GET', 'POST'])
def confirm_email(token):
    if user_functions.check_token(token) == True:
        return render_template('login.html', message="Your account is confirmed. You can login now")
    else:
        return render_template('login.html', error="Your token is invalid or expired. Please try again later")
    

@app.route('/logout')
def logout():
    print(session)
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
        return render_template('settings.html',username = session['username'],
                               storage_size = user_functions.find_appropriate_file_size(session['storage_limit']*1000*1000),
                               used_storage = user_functions.find_appropriate_file_size(session['used_storage']),
                               usage_proportion = str(round((session['used_storage']*100)/(session['storage_limit']*1000*1000),2)) + "%",
                               email = session['email']  )    


@app.route('/my_drive', methods=['GET', 'POST'])
def my_drive():
    if 'logged_in' not in session or not session['logged_in']:
        return redirect(url_for('login'))
    else:
        return redirect(url_for('browse_folder', path=str(session['user_id'])))

@app.route("/browse_folder/<path:path>", methods=["POST", "GET"])
def browse_folder(path):

    authorized = {
        "read": False,
        "upload": False,
        "delete": False
    }


    if 'logged_in' not in session or not session['logged_in']:
        return redirect(url_for('login'))
    else:
        if session['user_id'] != int(path.split('/')[0]):
            #return jsonify({"success": False, "message": "You are not authorized to view this folder"})        
        
            conn = sqlite3.connect('database.db')
            cursor = conn.cursor()
            
            cursor.execute('SELECT * from (SELECT folder_name,permissions,shared_folders.user_id from folders,shared_folders where folders.folder_id = shared_folders.folder_id ) where user_id = ? ',(session['user_id'],))
        
            shared_folders = cursor.fetchall()
            cursor.close()
            conn.close()
            #shared_folders = [i[0] for i in shared_folders]
            print(shared_folders)
            for i in shared_folders:
                if path.startswith(i[0]) and 'r' in i[1]:
                    print("authorized: to read",i)
                    authorized['read'] = True
                
                if path.startswith(i[0]) and 'u' in i[1]:
                    print("authorized: to upload",i)
                    authorized['upload'] = True
                
                if path.startswith(i[0]) and 'd' in i[1]:
                    print("authorized: to read",i)
                    authorized['delete'] = True
                
                if (False not in authorized.values()) :
                    break

            if authorized['read'] == False:
                return render_template("my_drive.html", error = "You are not authorized to view this folder")

        else: #if the user is the owner of the folder
            authorized = {
                "read": True,
                "upload": True,
                "delete": True
            }

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
        

        cursor = sqlite3.connect('database.db').cursor()
        cursor.execute('SELECT username FROM users WHERE user_id = ?', (int(path.split('/')[0]),))
        author_name = cursor.fetchone()[0]
        author_id = int(path.split('/')[0])
        cursor.close()

        if session['user_id'] == author_id:
            author = None
        else:
            author = {
                'name': author_name,
                'id': author_id
            }
        return render_template("my_drive.html", item_list=item_list, path_list=path_list,
                               current_folder_path = path,author = author,authorized = authorized)



@app.route("/browse_file<path:path>", methods=["POST", "GET"])
def browse_file(path):
    if 'logged_in' not in session or not session['logged_in']:
        return redirect(url_for('login'))
    else:
        return file_functions.browse_file(path)
    
        


@app.route("/create_folder/<path:path>", methods=["POST"])
def create_folder(path):
    if "logged_in" not in session or not session["logged_in"]:
        return redirect(url_for("login"))
    
    if path.split('/')[0] != str(session['user_id']):
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        #cursor.execute('SELECT folder_name,permissions from folders,shared_folders where folders.folder_id = shared_folders.folder_id and folders.folder_id =  (select folder_id from shared_folders WHERE user_id = ? )',(session['user_id'],))
        cursor.execute('SELECT * from (SELECT folder_name,permissions,shared_folders.user_id from folders,shared_folders where folders.folder_id = shared_folders.folder_id ) where user_id = ? ',(session['user_id'],))
        
        shared_folders = cursor.fetchall()
        cursor.close()
        conn.close()
        #shared_folders = [i[0] for i in shared_folders]
        print(shared_folders)
        authorized = False
        for i in shared_folders:
            if path.startswith(i[0]) and 'u' in i[1]:
                print("authorized:",i)
                authorized = True
                break
        if not authorized:
            print("not authorized to create folder")
            return jsonify({"error": "You are not authorized to create a folder to this folder"}), 403

    
    
    print("create folder is running")
    folder_name = request.json.get("name")
    print(folder_name)
    folder_name = folder_name.replace(' ', '_')
    
    if user_functions.is_valid_filename(folder_name):
        print("valid folder name",folder_name)
        os.mkdir('media/' + path + '/' + folder_name)
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO folders (folder_name, user_id) VALUES (?, ?)', (path + '/' + folder_name, session['user_id']))
        conn.commit()
        cursor.execute("INSERT INTO shared_folders (folder_id,user_id, permissions) VALUES (?,?,?)", (cursor.lastrowid, session['user_id'], "rud"))
        conn.commit()

        cursor.close()
        conn.close()
    else:
        print("invalid folder name",folder_name)
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
    else:
        return file_functions.upload_file(path,request)


def __main__():
    app.run(host='0.0.0.0', port=8000,debug=True)

if __name__ == '__main__':  
    __main__()
