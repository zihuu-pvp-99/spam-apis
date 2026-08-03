from flask import Flask, request, Response
import json
import threading
import requests
from google.protobuf.json_format import MessageToJson
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import binascii
from collections import OrderedDict
import danger_count_pb2
import danger_generator_pb2
from byte import Encrypt_ID, encrypt_api

app = Flask(__name__)

# Region configuration mapping
REGION_CONFIG = {
    'ind': {'domain': 'client.ind.freefiremobile.com', 'token_file': 'tokens_ind.json'},
    'br': {'domain': 'client.us.freefiremobile.com', 'token_file': 'tokens_br.json'},
    'us': {'domain': 'client.us.freefiremobile.com', 'token_file': 'tokens_us.json'},
    'na': {'domain': 'client.us.freefiremobile.com', 'token_file': 'tokens_na.json'},
    'sac': {'domain': 'client.us.freefiremobile.com', 'token_file': 'tokens_sac.json'},
    'pk': {'domain': 'clientbp.ggpolarbear.com', 'token_file': 'tokens_pk.json'},
    'sg': {'domain': 'clientbp.ggpolarbear.com', 'token_file': 'tokens_sg.json'},
    'bd': {'domain': 'clientbp.ggpolarbear.com', 'token_file': 'tokens_bd.json'},
    'vn': {'domain': 'clientbp.ggpolarbear.com', 'token_file': 'tokens_vn.json'},
    'me': {'domain': 'clientbp.ggpolarbear.com', 'token_file': 'tokens_me.json'},
    'eu': {'domain': 'clientbp.ggpolarbear.com', 'token_file': 'tokens_eu.json'},
    'id': {'domain': 'clientbp.ggpolarbear.com', 'token_file': 'tokens_id.json'},
    'th': {'domain': 'clientbp.ggpolarbear.com', 'token_file': 'tokens_th.json'},
    'tw': {'domain': 'clientbp.ggpolarbear.com', 'token_file': 'tokens_tw.json'},
    'ru': {'domain': 'clientbp.ggpolarbear.com', 'token_file': 'tokens_ru.json'}
}

def load_tokens(region):
    """Load tokens for specific region"""
    try:
        config = REGION_CONFIG.get(region)
        if not config:
            return None
            
        with open(config['token_file'], "r") as f:
            return json.load(f)
    except:
        return None

def encrypt_message(plaintext_bytes):
    """AES encryption for all regions"""
    key = b'Yg&tc%DEuh6%Zc^8'
    iv = b'6oyZDr22E3ychjM%'
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded = pad(plaintext_bytes, AES.block_size)
    encrypted = cipher.encrypt(padded)
    return binascii.hexlify(encrypted).decode('utf-8')

def create_uid_protobuf(uid):
    """Create protobuf message for UID"""
    msg = danger_generator_pb2.danger_generator()
    msg.saturn_ = int(uid)
    msg.garena = 1
    return msg.SerializeToString()

def enc(uid):
    """Encrypt UID for API request"""
    pb = create_uid_protobuf(uid)
    return encrypt_message(pb)

def decode_player_info(binary):
    """Decode player info from protobuf"""
    info = danger_count_pb2.Danger_ff_like()
    info.ParseFromString(binary)
    return info

def get_player_info(uid, region):
    """Get player info from specific region"""
    try:
        tokens = load_tokens(region)
        if tokens is None or len(tokens) == 0:
            return None, None, region

        token = tokens[0]['token']
        config = REGION_CONFIG.get(region)
        url = f"https://{config['domain']}/GetPlayerPersonalShow"

        encrypted_uid = enc(uid)
        edata = bytes.fromhex(encrypted_uid)

        headers = {
            'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 13; SM-S918B Build/TP1A.220624.014)",
            'Connection': "Keep-Alive",
            'Accept-Encoding': "gzip",
            'Authorization': f"Bearer {token}",
            'Content-Type': "application/octet-stream",
            'X-Unity-Version': "2018.4.11f1",
            'X-GA': "v1 1",
            'ReleaseVersion': "OB54"
        }

        response = requests.post(url, data=edata, headers=headers, verify=False, timeout=10)

        if response.status_code != 200:
            return None, None, region

        info = decode_player_info(response.content)
        data = json.loads(MessageToJson(info))

        # Try to get account info from different possible paths
        account = data.get("AccountInfo", {})
        if not account:
            # Some responses might have different structure
            account = data.get("accountInfo", {})
        
        if not account:
            # Try direct fields
            player_name = data.get("PlayerNickname", "Unknown")
            player_uid = data.get("UID", uid)
        else:
            player_name = account.get("PlayerNickname", "Unknown")
            player_uid = account.get("UID", uid)

        return player_name, player_uid, region
        
    except Exception as e:
        print(f"Error in get_player_info: {e}")
        return None, None, region

def send_friend_request(uid, token, domain, results, lock):
    """Send friend request to specific domain"""
    try:
        encrypted_id = Encrypt_ID(uid)
        payload = f"08a7c4839f1e10{encrypted_id}1801"
        encrypted_payload = encrypt_api(payload)
        
        url = f"https://{domain}/RequestAddingFriend"

        headers = {
            "Authorization": f"Bearer {token}",
            "X-Unity-Version": "2018.4.11f1",
            "X-GA": "v1 1",
            "ReleaseVersion": "OB54",
            "Content-Type": "application/octet-stream",
            "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 13; SM-S918B Build/TP1A.220624.014)"
        }

        response = requests.post(url, data=bytes.fromhex(encrypted_payload), headers=headers, timeout=10)

        with lock:
            if response.status_code == 200:
                results['success'] += 1
                print(f"Friend request sent successfully to {domain}")
            else:
                results['failed'] += 1
                print(f"Failed to send friend request to {domain}: {response.status_code}")

    except Exception as e:
        print(f"Error in send_friend_request: {e}")
        with lock:
            results['failed'] += 1

@app.route("/send_requests", methods=["GET"])
def handle_friend_request():
    """Handle friend requests with region support"""
    uid = request.args.get("uid")
    region = request.args.get("region", "bd")  # Default to BD if not specified

    if not uid:
        return Response(json.dumps({"error": "uid required"}), mimetype="application/json")

    # Validate region
    if region not in REGION_CONFIG:
        return Response(json.dumps({"error": f"Invalid region. Supported: {', '.join(REGION_CONFIG.keys())}"}), 
                       mimetype="application/json")

    tokens = load_tokens(region)
    if tokens is None or len(tokens) == 0:
        return Response(json.dumps({"error": f"Token file for region {region} not found or empty"}), 
                       mimetype="application/json")

    player_name, player_uid, region = get_player_info(uid, region)

    config = REGION_CONFIG.get(region)
    domain = config['domain']

    results = {"success": 0, "failed": 0}
    lock = threading.Lock()
    threads = []

    # Limit to available tokens
    max_tokens = min(100, len(tokens))
    
    for i in range(max_tokens):
        token = tokens[i]['token']
        thread = threading.Thread(target=send_friend_request, args=(uid, token, domain, results, lock))
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()

    # Determine status
    if results["success"] > 0:
        status = 1  # Success
    elif results["failed"] > 0:
        status = 2  # Failed
    else:
        status = 3  # Unknown

    output = OrderedDict([
        ("PlayerName", player_name if player_name else "Unknown"),
        ("UID", player_uid if player_uid else uid),
        ("Region", region.upper()),
        ("Success", results["success"]),
        ("Failed", results["failed"]),
        ("Status", status)
    ])

    return Response(json.dumps(output), mimetype="application/json")

@app.route("/regions", methods=["GET"])
def list_regions():
    """List all available regions"""
    regions = [{"code": code, "domain": config['domain'], "token_file": config['token_file']} 
               for code, config in REGION_CONFIG.items()]
    return Response(json.dumps({"regions": regions}), mimetype="application/json")

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)