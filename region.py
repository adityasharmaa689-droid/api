import asyncio
import time
import json
import base64
import httpx
import logging
from collections import defaultdict
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from google.protobuf import json_format
from google.protobuf.message import Message
from dotenv import load_dotenv

load_dotenv()

from proto import FreeFire_pb2
import uid_generator_pb2
from region_pb2 import AccountPersonalShowInfo, Data, Response

logging.basicConfig(level=logging.INFO)
cached_tokens = defaultdict(dict)

MAIN_KEY = base64.b64decode("WWcmdGMlREV1aDYlWmNeOA==")
MAIN_IV = base64.b64decode("Nm95WkRyMjJFM3ljaGpNJQ==")
RELEASE_VERSION = "OB51"
USER_AGENT = "Dalvik/2.1.0 (Linux; U; Android 13; CPH2095 Build/RKQ1.211119.001)"
TOKEN_EXPIRY = 25200

REGIONS = [
    {
        "uid": "4044412477",
        "password": "FC061D3BBEECF1DECA36E66F6D53C5B80A1D652155ED9D72274916975C650CCE",
        "endpoint": "https://clientbp.ggblueshark.com"
    },
    {
        "uid": "3761105000",
        "password": "D984C330F36BAC2C6556ACE2A590AFF4BF8B09F3B8F7FCD998FD58AB12ED3F54",
        "endpoint": "https://client.ind.freefiremobile.com"
    },
    {
        "uid": "4044415099",
        "password": "612F032C88ED16389DFD6B01D938AFF1CF01448A121D4EDB82483865875A7DDD",
        "endpoint": "https://client.us.freefiremobile.com"
    }
]

def aes_encrypt_data(data: bytes) -> bytes:
    return AES.new(MAIN_KEY, AES.MODE_CBC, MAIN_IV).encrypt(pad(data, AES.block_size))

def decode_proto(data: bytes, message_type: Message):
    obj = message_type()
    obj.ParseFromString(data)
    return obj

async def json_to_proto(data: dict, proto_message: Message) -> bytes:
    json_format.ParseDict(data, proto_message)
    return proto_message.SerializeToString()

def create_uid_proto(uid: int) -> bytes:
    msg = uid_generator_pb2.uid_generator()
    msg.accountid = uid
    msg.request = 1
    return msg.SerializeToString()

async def get_access_token(uid: str, password: str):
    url = "https://ffmconnect.live.gop.garenanow.com/oauth/guest/token/grant"
    payload = (
        f"uid={uid}&password={password}&response_type=token&client_type=2&"
        "client_secret=2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3&client_id=100067"
    )
    headers = {
        "User-Agent": USER_AGENT,
        "Connection": "Keep-Alive",
        "Accept-Encoding": "gzip",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, data=payload, headers=headers)
            data = resp.json()
            return data.get("access_token"), data.get("open_id")
    except Exception as e:
        logging.error(f"Failed to get access token: {str(e)}")
        return None, None

async def create_jwt(region):
    token_val, open_id = await get_access_token(region["uid"], region["password"])
    if not token_val:
        return None
    
    body = {
        "open_id": open_id,
        "open_id_type": "4",
        "login_token": token_val,
        "orign_platform_type": "4"
    }
    proto_bytes = await json_to_proto(body, FreeFire_pb2.LoginReq())
    payload = aes_encrypt_data(proto_bytes)
    headers = {
        "User-Agent": USER_AGENT,
        "Connection": "Keep-Alive",
        "Accept-Encoding": "gzip",
        "Content-Type": "application/octet-stream",
        "Expect": "100-continue",
        "X-Unity-Version": "2018.4.11f1",
        "X-GA": "v1 1",
        "ReleaseVersion": RELEASE_VERSION
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post("https://loginbp.ggblueshark.com/MajorLogin", data=payload, headers=headers)
            msg = decode_proto(resp.content, FreeFire_pb2.LoginRes)
            msg_dict = json.loads(json_format.MessageToJson(msg))
            cached_tokens[region["endpoint"]] = {
                "token": f"Bearer {msg_dict.get('token', '')}",
                "server_url": msg_dict.get("serverUrl", ""),
                "expires_at": time.time() + TOKEN_EXPIRY
            }
            return True
    except Exception as e:
        logging.error(f"Failed to create JWT for {region['endpoint']}: {str(e)}")
        return False

async def get_token(region):
    cache = cached_tokens.get(region["endpoint"])
    if cache and time.time() < cache["expires_at"]:
        return cache["token"], cache["server_url"]
    
    success = await create_jwt(region)
    if not success:
        return None, None
        
    info = cached_tokens.get(region["endpoint"], {})
    return info.get("token", ""), info.get("server_url", "")

async def fetch_player(region, encrypted_payload: bytes):
    token, _ = await get_token(region)
    if not token:
        return None
    headers = {
        "User-Agent": USER_AGENT,
        "Connection": "Keep-Alive",
        "Authorization": token,
        "X-Unity-Version": "2018.4.11f1",
        "X-GA": "v1 1",
        "ReleaseVersion": RELEASE_VERSION,
        "Content-Type": "application/x-www-form-urlencoded"
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(region["endpoint"] + "/GetPlayerPersonalShow", headers=headers, data=encrypted_payload)
            if resp.status_code == 200 and resp.content:
                data = decode_proto(resp.content, AccountPersonalShowInfo)
                if data.basic_info.account_id:
                    return {"region": region["endpoint"], "player_data": data}
            return None
    except Exception as e:
        logging.error(f"Failed to fetch player from {region['endpoint']}: {str(e)}")
        return None

async def fetch_workshop(uid, region_endpoint):
    region = next((r for r in REGIONS if r["endpoint"] == region_endpoint), None)
    if not region:
        return None
    token, _ = await get_token(region)
    if not token:
        return None
    data = Data(account_id=int(uid), language=b'en')
    ciphertext = aes_encrypt_data(data.SerializeToString())
    headers = {
        "User-Agent": USER_AGENT,
        "Connection": "Keep-Alive",
        "Authorization": token,
        "X-Unity-Version": "2018.4.11f1",
        "X-GA": "v1 1",
        "ReleaseVersion": RELEASE_VERSION,
        "Content-Type": "application/x-www-form-urlencoded"
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(region_endpoint + "/GetWorkshopAuthorInfo", headers=headers, data=ciphertext)
            if resp.status_code == 200 and resp.content:
                workshop_proto = decode_proto(resp.content, Response)
                workshop_dict = json.loads(json_format.MessageToJson(workshop_proto, preserving_proto_field_name=True))

                for _, map_obj in workshop_dict.get("map", {}).items():
                    if "map_direction" in map_obj and "map_code" in map_obj["map_direction"]:
                        code = map_obj["map_direction"]["map_code"]
                        if not code.startswith("#FREEFIRE"):
                            map_obj["map_direction"]["map_code"] = f"#FREEFIRE{code}"
                return workshop_dict
            return None
    except Exception as e:
        logging.error(f"Failed to fetch workshop from {region_endpoint}: {str(e)}")
        return None

def region_lookup_internal(uid):
    if not uid or not uid.isdigit():
        return {"error": "Invalid or missing UID"}
    
    uid_int = int(uid)
    payload = aes_encrypt_data(create_uid_proto(uid_int))
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    tasks = [fetch_player(region, payload) for region in REGIONS]
    results = loop.run_until_complete(asyncio.gather(*tasks))
    found = next((r for r in results if r), None)
    if not found:
        loop.close()
        return {"error": "Player not found"}
    
    region_endpoint = found["region"]
    player_proto = found["player_data"]
    workshop_json = loop.run_until_complete(fetch_workshop(uid_int, region_endpoint))
    loop.close()
    
    response_dict = json.loads(json_format.MessageToJson(player_proto, preserving_proto_field_name=True))
    if workshop_json:
        response_dict["workshop"] = workshop_json
    
    return response_dict