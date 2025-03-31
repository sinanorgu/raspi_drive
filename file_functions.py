from flask import Flask, flash, render_template, request, redirect, url_for, session, send_from_directory,jsonify,send_file
import os
import sqlite3
import user_functions

MAGIC_STRING = b"!@#$%^&*()_+"
ALLOWED_MIME_TYPES = {'image/jpeg', 'image/png', 'image/gif', 'application/pdf', 'video/mp4'}



def browse_file(path):



    if not os.path.isfile('media/' + path):
        return jsonify({"success": False, "message": "File not found"})
    
    with open('media/' + path, "rb") as f:
        file_data = f.read()
    signature = file_data[:8]  # İlk 100 baytı oku

    if file_data.startswith(MAGIC_STRING):
        file_data = file_data[len(MAGIC_STRING):]  # Başındaki özel karakterleri kaldır
    else:
        if detect_mime_type_with_signature(signature) not in ALLOWED_MIME_TYPES:
            return "kanka bu iste bi is var ya dosya sifreli degil gonderemem kb"
        else:
            return send_from_directory('media/', path)



    import io
    decrypted_file_io = io.BytesIO(file_data)
    decrypted_file_io.seek(0)

    
    

    
    return send_file(decrypted_file_io, as_attachment=True, download_name=path.split('/')[-1])
    #return send_file('media/'+ path, as_attachment=True, mimetype="application/octet-stream")
    #return send_from_directory('media/', path)


def upload_file(path,request):
    
    
    if path.split('/')[0] != str(session['user_id']):
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        #cursor.execute('SELECT folder_name,permissions from folders,shared_folders where folders.folder_id = shared_folders.folder_id and folders.folder_id =  (select folder_id from shared_folders WHERE user_id = ? )',(session['user_id'],))
        cursor.execute('SELECT * from (SELECT folder_name,permissions,shared_folders.user_id from folders,shared_folders where folders.folder_id = shared_folders.folder_id ) where user_id = ? ',(session['user_id'],))
        
        shared_folders = cursor.fetchall()
        cursor.close()
        conn.close()
        #shared_folders = [i[0] for i in shared_folders]
        #print(shared_folders)
        authorized = False
        for i in shared_folders:
            if path.startswith(i[0]) and 'u' in i[1]:
                print("authorized:",i)
                authorized = True
                break
        if not authorized:
            return jsonify({"error": "You are not authorized to upload files to this folder"}), 403

    if request.method == "POST":
        files = request.files.getlist('file')  # Tüm dosyaları al
        #print(files)


        for file in files:
            if file.filename == '':
                return jsonify({"error": "No selected file"}), 400



            file_data = file.read()
            signature = file_data[:8]  # İlk 8 baytı oku

            
            #print(type(file_data))
            #print(len(file_data))
            

            conn = sqlite3.connect('database.db')
            cursor = conn.cursor()
            cursor.execute('SELECT storage_limit FROM users WHERE user_id = ?', (path.split("/")[0] ,))
            storage_limit = cursor.fetchone()[0]

            used_storage = 0 # needs to be calculated
            used_storage = user_functions.get_used_storage(session['user_id'])


            if used_storage + len(file_data) > storage_limit*1000*1000: # Mb to bytes
                cursor.close()
                conn.close()
                return jsonify({"error": "Storage limit exceeded"}), 400
            

            
            file_path = 'media/' + path + '/' + file.filename
        
            if detect_mime_type_with_signature(signature) in ALLOWED_MIME_TYPES:
                with open(file_path, "wb") as f:
                    f.write(file_data)
            else:
                with open(file_path, "wb") as f:
                    f.write(MAGIC_STRING + file_data)

            cursor.execute('INSERT INTO files (file_name, title, file_size, user_id) VALUES (?, ?, ?, ?)', (file.filename, file.filename, len(file_data), session['user_id']))
            conn.commit()
            cursor.execute("INSERT INTO shared_files (file_id, user_id) VALUES (?, ?)", (cursor.lastrowid, session['user_id']))
            conn.commit()
            cursor.close()
            conn.close()


        

        return jsonify({"message": "File stored securely"}), 200
    


def get_file_signature(file_path, num_bytes=8):
    """Dosyanın ilk 'num_bytes' baytını okuyarak dosya imzasını döner."""
    with open(file_path, 'rb') as f:
        signature = f.read(num_bytes)  # İlk birkaç baytı oku
    return signature

def detect_mime_type(file_path):
    """Dosyanın imzasına göre MIME türünü belirler."""
    # Bilinen dosya imzaları (magic numbers)
    signature_to_mime = {
        b'\xFF\xD8\xFF\xE0': 'image/jpeg',
        b'\xFF\xD8\xFF\xE1': 'image/jpeg',  # Alternatif JPEG
        b'\x89\x50\x4E\x47\x0D\x0A\x1A\x0A': 'image/png',
        b'\x47\x49\x46\x38\x39\x61': 'image/gif',  # GIF89a
        b'\x47\x49\x46\x38\x37\x61': 'image/gif',  # GIF87a
        b'\x25\x50\x44\x46': 'application/pdf',  # PDF dosyası
        b'\x50\x4B\x03\x04': 'application/zip',  # ZIP dosyası
        b'\x00\x00\x00\x18\x66\x74\x79\x70': 'video/mp4',  # MP4 dosyası
        b'\x4D\x5A': 'application/x-dosexec',  # EXE dosyası
        b'\x23\x21\x2F\x62\x69\x6E\x2F': 'text/x-shellscript'  # Shell script
    }

    # Dosya imzasını oku
    signature = get_file_signature(file_path, num_bytes=8)

    # İmza ile eşleşen MIME türünü kontrol et
    for magic_number, mime_type in signature_to_mime.items():
        if signature.startswith(magic_number):
            return mime_type

    # Bilinmeyen dosya türü
    return "unknown/unknown"


def detect_mime_type_with_signature(signature):
    signature_to_mime = {
        b'\xFF\xD8\xFF\xE0': 'image/jpeg',
        b'\xFF\xD8\xFF\xE1': 'image/jpeg',  # Alternatif JPEG
        b'\x89\x50\x4E\x47\x0D\x0A\x1A\x0A': 'image/png',
        b'\x47\x49\x46\x38\x39\x61': 'image/gif',  # GIF89a
        b'\x47\x49\x46\x38\x37\x61': 'image/gif',  # GIF87a
        b'\x25\x50\x44\x46': 'application/pdf',  # PDF dosyası
        b'\x50\x4B\x03\x04': 'application/zip',  # ZIP dosyası
        b'\x00\x00\x00\x18\x66\x74\x79\x70': 'video/mp4',  # MP4 dosyası
        b'\x4D\x5A': 'application/x-dosexec',  # EXE dosyası
        b'\x23\x21\x2F\x62\x69\x6E\x2F': 'text/x-shellscript'  # Shell script
    }    
    # İmza ile eşleşen MIME türünü kontrol et
    for magic_number, mime_type in signature_to_mime.items():
        if signature.startswith(magic_number):
            return mime_type

    # Bilinmeyen dosya türü
    return "unknown/unknown"


# Örnek kullanım
""" file_path = "example.jpg"  # Test dosyanı buraya koy
mime_type = detect_mime_type(file_path)
print(f"Dosya MIME Türü: {mime_type}") """




def main():
    # Test dosyası
    file_path = "media/1/aaa.jpg"  # Test dosyanı buraya koy
    mime_type = detect_mime_type(file_path)
    print(f"Dosya MIME Türü: {mime_type}")


if __name__ == "__main__":
    main()