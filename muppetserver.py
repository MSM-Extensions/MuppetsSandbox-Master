from flask import Flask, request, jsonify, g, send_from_directory, abort
import secrets
import sqlite3
import hashlib
import time
import random
import os

app = Flask(__name__)

CONTENT_ROOT = os.path.join(os.path.dirname(__file__), "files")

DATABASE = "player_data.db"

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def md5_sum(input_string):
    encoded_string = input_string.encode('utf-8')

    md5_hash = hashlib.md5(encoded_string)

    return md5_hash.hexdigest()

def md5_file(path):
    hash_md5 = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def generate_game_info(length):
    chars = "bcdfghjkmnpqrstvwxyz23456789"
    return ''.join(random.choice(chars) for _ in range(length))

def create_new_anon_account(client_version, platform, device_id, mac_address, ip):
    db = get_db()
    cur = db.cursor()

    username = md5_sum(f"{device_id}{mac_address}")
    password = md5_sum(f"{device_id}{mac_address}67")

    cur.execute("SELECT bbb_id FROM users WHERE username = ?", (username,))
    existing_row = cur.fetchone()

    if existing_row:
        bbb_id = existing_row[0]
        return username, password, bbb_id

    timestamp = int(time.time())
    insert_values = (username, password, timestamp, ip)
    cur.execute("INSERT INTO users (username, password, date_created, ip) VALUES (?, ?, ?, ?)", insert_values)
    db.commit()

    cur.execute("SELECT bbb_id FROM users WHERE username = ?", (username,))
    bbb_id_row = cur.fetchone()
    bbb_id = bbb_id_row[0] if bbb_id_row else None

    return username, password, bbb_id

@app.route('/', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'HEAD'])
@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'HEAD'])
def catch_all(path):
    print("----- Incoming Request -----")
    print("Method:", request.method)
    print("Path:", "/" + path)
    print("Remote Addr:", request.remote_addr)

    print("\nHeaders:")
    for k, v in request.headers.items():
        print(f"  {k}: {v}")

    print("\nQuery Params:")
    print(request.args.to_dict())

    print("\nBody:")
    try:
        print(request.get_data(as_text=True))
    except Exception as e:
        print("Could not read body:", e)

    print("----- End Request -----\n")

    return "OK\n", 200

GAME_SERVER_IP = "192.168.1.16"

def generate_sessid(length=32):
    return secrets.token_hex(length)

@app.route('/auth.php', methods=['GET'])
def auth():
    q = request.args
    username = q.get("u")
    password = q.get("p")
    login_type = q.get("t")
    bbb_id = q.get("bbb_id")
    game = int(q.get("g"))
    
    lang = q.get("lang")
    client_version = q.get("client_version")
    mac_address = q.get("mac")
    platform = q.get("platform")
    device_id = q.get("devid")
    application_id = q.get("aid")

    print(game)

    if game == 5 or client_version == "1.3.0":
        username, password, bbb_id = create_new_anon_account(
            client_version, platform, device_id, mac_address, request.remote_addr
        )
        
        response = {
            "ok": True,
            "success": True,
            "login_type": login_type,
            "anon_name": username,
            "anon_pass": password,
            "anon_bbb_id": bbb_id,
            "username": bbb_id,
            "account_id": bbb_id,
            "auto_login": True,
            "serverIp": GAME_SERVER_IP
        }
        
        return jsonify(response)
    elif game == 1:
        response = {
            "ok": True,
            "bbbId": "1",
            "sessId": generate_sessid(),
            "serverIp": GAME_SERVER_IP,
            "cmd": "sync"
        }

        return jsonify(response)

        '''
        /auth.php?u=&p=&t=bbb&g=1&lang=en&client_version=1.0.2&oudid=

        {
            "ok": true,
            "bbbId": "12345",
            "sessId": "abcdef",
            "serverIp": "1.2.3.4",
            "cmd": "sync"
        }
        '''

@app.route('/friends.php', methods=['GET'])
def friends():
    fid = request.args.get('fid', "")
    cmd = request.args.get('c', "")

    response = {
        "add": "1",
        "sync": "1",
        "remove": "1",
        "fid": fid,
        "c": cmd,
        "ok": True
    }

    return jsonify(response)

updates_data = []

@app.route('/content/<ver>/files.json', methods=['GET'])
def get_updates(ver):
    files_list = []

    for root, dirs, files in os.walk(CONTENT_ROOT):
        for file in files:
            full_path = os.path.join(root, file)

            relative_path = os.path.relpath(full_path, CONTENT_ROOT).replace("\\", "/")

            checksum = md5_file(full_path)

            files_list.append({
                "localName": relative_path,
                "serverName": relative_path,
                "checksum": checksum
            })

    return jsonify(files_list)

@app.route('/content/<ver>/<path:filename>', methods=['GET'])
def serve_file(ver, filename):
    full_path = os.path.join(CONTENT_ROOT, filename)

    if os.path.isfile(full_path):
        return send_from_directory(CONTENT_ROOT, filename)
    else:
        abort(404)

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=900,
        debug=True
    )
