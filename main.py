from flask import Flask, flash, render_template, request, redirect, url_for, session, send_from_directory,jsonify,send_file
import sqlite3
import os
import shutil
import user_functions
import file_functions
from file_functions import MAGIC_STRING


if not os.path.exists('media'):
    os.mkdir('media')   # Medya klasörünü oluştur
#sqlite3.connect('database.db') # Veritabanı dosyasını oluştur
conn = sqlite3.connect('database.db')
cursor = conn.cursor()
cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY AUTOINCREMENT, username varchar(20) , password varchar(70), storage_limit INTEGER default 500 , email varchar(50) UNIQUE, is_admin BOOLEAN default 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
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


def user_has_permission_for_path(user_id, path, required_permission):
    owner_id = path.split('/')[0]
    if str(user_id) == owner_id:
        return True

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute(
        '''
        SELECT folders.folder_name, shared_folders.permissions
        FROM shared_folders
        JOIN folders ON folders.folder_id = shared_folders.folder_id
        WHERE shared_folders.user_id = ?
        ''',
        (user_id,)
    )
    shares = cursor.fetchall()
    cursor.close()
    conn.close()

    for folder_name, permissions in shares:
        if path.startswith(folder_name) and required_permission in permissions:
            return True
    return False



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
        used_storage_in_byte = user_functions.get_used_storage(session['user_id'])
        return render_template('settings.html',username = session['username'],
                               storage_size = user_functions.find_appropriate_file_size(session['storage_limit']*1000*1000),
                               
                               used_storage = user_functions.find_appropriate_file_size(used_storage_in_byte),
                               usage_proportion = str(round((used_storage_in_byte*100)/(session['storage_limit']*1000*1000),2)) + "%",
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
            #print("shared_folders:",shared_folders)
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
                return render_template("my_drive.html", error = "You are not authorized to view this folder", can_share=False, shareable_users=[])

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
                'path' : path + '/' + i,
                'is_image': user_functions.is_previewable_image(i)

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

        can_share = session['user_id'] == author_id
        shareable_users = []
        share_info = []
        inherited_share_info = []
        if can_share:
            conn = sqlite3.connect('database.db')
            cursor = conn.cursor()
            cursor.execute('SELECT user_id, username FROM users WHERE user_id != ?', (session['user_id'],))
            shareable_users = [{'id': row[0], 'name': row[1]} for row in cursor.fetchall()]
            cursor.execute('SELECT folder_id FROM folders WHERE folder_name = ?', (path,))
            folder_row = cursor.fetchone()
            if folder_row:
                folder_id = folder_row[0]
                cursor.execute(
                    '''
                    SELECT users.user_id, users.username, shared_folders.permissions
                    FROM shared_folders
                    JOIN users ON users.user_id = shared_folders.user_id
                    WHERE shared_folders.folder_id = ? AND users.user_id != ?
                    ''',
                    (folder_id, session['user_id'])
                )
                share_info = [
                    {
                        "user_id": row[0],
                        "username": row[1],
                        "permissions": row[2]
                    }
                    for row in cursor.fetchall()
                ]
                segments = path.split('/')
                for i in range(len(segments)-1):
                    parent_path = '/'.join(segments[:i+1])
                    cursor.execute('SELECT folder_id FROM folders WHERE folder_name = ?', (parent_path,))
                    parent_row = cursor.fetchone()
                    if parent_row:
                        cursor.execute(
                            '''
                            SELECT users.user_id, users.username, shared_folders.permissions
                            FROM shared_folders
                            JOIN users ON users.user_id = shared_folders.user_id
                            WHERE shared_folders.folder_id = ? AND users.user_id != ?
                            ''',
                            (parent_row[0], session['user_id'])
                        )
                        for row in cursor.fetchall():
                            inherited_share_info.append({
                                "user_id": row[0],
                                "username": row[1],
                                "permissions": row[2],
                                "source_folder": parent_path
                            })
            cursor.close()
            conn.close()
        else:
            share_info = []
            inherited_share_info = []

        return render_template("my_drive.html", item_list=item_list, path_list=path_list,
                               current_folder_path = path,author = author,authorized = authorized,
                               can_share = can_share, shareable_users = shareable_users,
                               share_info = share_info, inherited_share_info = inherited_share_info)


@app.route("/browse_file<path:path>", methods=["POST", "GET"])
def browse_file(path):
    if 'logged_in' not in session or not session['logged_in']:
        return redirect(url_for('login'))
    else:
        return file_functions.browse_file(path)
    
        


@app.route("/preview_file/<path:path>", methods=["GET"])
def preview_file(path):
    if 'logged_in' not in session or not session['logged_in']:
        return redirect(url_for('login'))
    else:
        return file_functions.preview_file(path)


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

@app.route("/delete/<path:path>", methods=["POST"])
def delete_item(path):
    if "logged_in" not in session or not session["logged_in"]:
        return jsonify({"success": False, "error": "You must be logged in to delete items"}), 401

    if not user_has_permission_for_path(session['user_id'], path, 'd'):
        return jsonify({"success": False, "error": "You are not authorized to delete this item"}), 403

    owner_id = path.split('/')[0]
    if path == owner_id and '/' not in path:
        return jsonify({"success": False, "error": "You cannot delete the root directory"}), 400

    target_path = os.path.join('media', path)
    if not os.path.exists(target_path):
        return jsonify({"success": False, "error": "Item not found"}), 404

    owner_id_int = int(owner_id)

    try:
        if os.path.isfile(target_path):
            os.remove(target_path)
            conn = sqlite3.connect('database.db')
            cursor = conn.cursor()
            cursor.execute('DELETE FROM files WHERE file_name = ? AND user_id = ?', (os.path.basename(path), owner_id_int))
            conn.commit()
            cursor.close()
            conn.close()
        else:
            files_to_delete = set()
            for root, dirs, files in os.walk(target_path):
                for file in files:
                    files_to_delete.add(file)

            conn = sqlite3.connect('database.db')
            cursor = conn.cursor()
            for filename in files_to_delete:
                cursor.execute('DELETE FROM files WHERE file_name = ? AND user_id = ?', (filename, owner_id_int))

            cursor.execute('SELECT folder_id FROM folders WHERE folder_name = ? OR folder_name LIKE ?', (path, path + '/%'))
            folder_ids = [row[0] for row in cursor.fetchall()]

            if folder_ids:
                cursor.executemany('DELETE FROM shared_folders WHERE folder_id = ?', [(fid,) for fid in folder_ids])
                placeholders = ','.join(['?'] * len(folder_ids))
                cursor.execute(f'DELETE FROM folders WHERE folder_id IN ({placeholders})', folder_ids)

            conn.commit()
            cursor.close()
            conn.close()

            shutil.rmtree(target_path)

    except Exception as e:
        print("delete error:", e)
        return jsonify({"success": False, "error": "An error occurred while deleting the item"}), 500

    return jsonify({"success": True, "message": f"Item {path} deleted"})




@app.route("/update/<path:path>", methods=["POST"])
def update_item(path):
    if "logged_in" not in session or not session["logged_in"]:
        return jsonify({"success": False, "error": "You must be logged in to update items"}), 401

    if not user_has_permission_for_path(session['user_id'], path, 'u'):
        return jsonify({"success": False, "error": "You are not authorized to rename this item"}), 403

    new_name = (request.json.get("name") or "").strip()
    if not new_name:
        return jsonify({"success": False, "error": "Yeni isim geçersiz"}), 400

    full_target_path = os.path.join('media', path)
    if not os.path.exists(full_target_path):
        return jsonify({"success": False, "error": "Item not found"}), 404

    parts = path.split('/')
    last = parts[-1]
    parent = '/'.join(parts[:-1])
    owner_id = int(parts[0])
    is_file = os.path.isfile(full_target_path)

    if is_file:
        extension = ""
        if '.' in last and '.' not in new_name:
            extension = '.' + last.split('.')[-1]
        new_full_name = new_name if '.' in new_name else new_name + extension
    else:
        new_full_name = new_name

    new_path = (parent + '/' if parent else '') + new_full_name
    os.rename(full_target_path, os.path.join('media', new_path))

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    if is_file:
        cursor.execute('UPDATE files SET file_name = ?, title = ? WHERE file_name = ? AND user_id = ?', (new_full_name, new_full_name, last, owner_id))
    else:
        cursor.execute('UPDATE folders SET folder_name = ? WHERE folder_name = ?', (new_path, path))
        cursor.execute('UPDATE folders SET folder_name = REPLACE(folder_name, ?, ?) WHERE folder_name LIKE ?', (path + '/', new_path + '/', path + '/%'))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"success": True, "message": f"Item {path} updated", "new_path": new_path, "new_name": new_full_name, "is_file": is_file})



@app.route("/share_folder", methods=["POST"])
def share_folder():
    if "logged_in" not in session or not session["logged_in"]:
        return jsonify({"error": "You need to login to share folders"}), 401

    data = request.get_json() or {}
    folder_path = data.get("folder_path")
    target_user_id = data.get("user_id")
    permissions = data.get("permissions", "")

    if not folder_path or target_user_id is None:
        return jsonify({"error": "Folder and user information is required"}), 400

    try:
        target_user_id = int(target_user_id)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid user information"}), 400

    owner_id = folder_path.split('/')[0]
    if str(session['user_id']) != owner_id:
        return jsonify({"error": "Only the owner can share this folder"}), 403

    allowed_perms = ''.join([p for p in "rud" if p in permissions])
    if not allowed_perms:
        return jsonify({"error": "At least one permission must be selected"}), 400

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT folder_id FROM folders WHERE folder_name = ?', (folder_path,))
    folder = cursor.fetchone()
    if not folder:
        cursor.close()
        conn.close()
        return jsonify({"error": "Folder information could not be found in database"}), 404

    cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (target_user_id,))
    user_exists = cursor.fetchone()
    if not user_exists:
        cursor.close()
        conn.close()
        return jsonify({"error": "Selected user does not exist"}), 404

    folder_id = folder[0]
    cursor.execute('SELECT shared_id FROM shared_folders WHERE folder_id = ? AND user_id = ?', (folder_id, target_user_id))
    existing = cursor.fetchone()

    if existing:
        cursor.execute('UPDATE shared_folders SET permissions = ? WHERE shared_id = ?', (allowed_perms, existing[0]))
    else:
        cursor.execute('INSERT INTO shared_folders (folder_id, user_id, permissions) VALUES (?, ?, ?)', (folder_id, target_user_id, allowed_perms))

    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"success": True, "message": "Folder shared successfully"})


@app.route("/unshare_folder", methods=["POST"])
def unshare_folder():
    if "logged_in" not in session or not session["logged_in"]:
        return jsonify({"error": "You need to login to update sharing settings"}), 401

    data = request.get_json() or {}
    folder_path = data.get("folder_path")
    target_user_id = data.get("user_id")

    if not folder_path or target_user_id is None:
        return jsonify({"error": "Folder and user information is required"}), 400

    owner_id = folder_path.split('/')[0]
    if str(session['user_id']) != owner_id:
        return jsonify({"error": "Only the owner can update sharing settings"}), 403

    try:
        target_user_id = int(target_user_id)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid user information"}), 400

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT folder_id FROM folders WHERE folder_name = ?', (folder_path,))
    folder = cursor.fetchone()
    if not folder:
        cursor.close()
        conn.close()
        return jsonify({"error": "Folder not found"}), 404

    cursor.execute('DELETE FROM shared_folders WHERE folder_id = ? AND user_id = ?', (folder[0], target_user_id))
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"success": True, "message": "Kullanıcı paylaşımından çıkarıldı"})


@app.route("/upload_file/<path:path>", methods=["POST", "GET"])
def upload_file(path):
    if "logged_in" not in session or not session["logged_in"]:
        return redirect(url_for("login"))
    else:
        return file_functions.upload_file(path,request)




@app.route('/shared_with_me', methods=['GET', 'POST'])
def shared_with_me():
    if 'logged_in' not in session or not session['logged_in']:
        return redirect(url_for('login'))
    else:
        shared_folder_list = user_functions.get_shared_folders(session['user_id'])
        return render_template('shared_with_me.html', folder_list = shared_folder_list)

        #return redirect(url_for('browse_folder', path=str(session['user_id'])))




def __main__():
    app.run(host='0.0.0.0', port=8000,debug=True)

if __name__ == '__main__':  
    __main__()
