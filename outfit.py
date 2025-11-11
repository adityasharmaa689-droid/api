import logging
import requests
import os
import json
from io import BytesIO
from PIL import Image
from dotenv import load_dotenv
import hashlib
import functools

load_dotenv()

logging.basicConfig(level=logging.INFO)

DEFAULT_BG_IMAGE_URL = "https://i.ibb.co/ynTHrcHG/IMG-20251007-181920-834.jpg"

ITEM_DATA_URL = "https://raw.githubusercontent.com/0xMe/ItemID2/main/assets/itemData.json"
FREEFIRE_ICON_URL = "https://freefiremobile-a.akamaihd.net/common/Local/PK/FF_UI_Icon/{item_icon}.png"

IMAGE_CACHE_DIR = "./image_cache"
os.makedirs(IMAGE_CACHE_DIR, exist_ok=True)
session = requests.Session()

def make_hashable(obj):
    if isinstance(obj, (str, int, float, bool)):
        return obj
    elif isinstance(obj, dict):
        return frozenset((k, make_hashable(v)) for k, v in obj.items())
    elif isinstance(obj, (list, tuple)):
        return tuple(make_hashable(x) for x in obj)
    return obj

def infinite_cache(func):
    cache = {}
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        key = (make_hashable(args), make_hashable(kwargs))
        if key not in cache:
            cache[key] = func(*args, **kwargs)
        return cache[key]
    return wrapper

def get_cache_filename(url):
    return os.path.join(IMAGE_CACHE_DIR, hashlib.md5(url.encode()).hexdigest() + ".png")

@infinite_cache
def fetch_image(url):
    if not url:
        return None
    cache_file = get_cache_filename(url)
    if os.path.exists(cache_file):
        try:
            return Image.open(cache_file).convert("RGBA").copy()
        except Exception:
            os.remove(cache_file)
    try:
        resp = session.get(url)
        resp.raise_for_status()
        img = Image.open(BytesIO(resp.content)).convert("RGBA")
        img.save(cache_file, format='PNG')
        return img.copy()
    except Exception as e:
        logging.error(f"Failed to fetch image: {url}, error: {e}")
        return None

CACHED_DEFAULT_BG = fetch_image(DEFAULT_BG_IMAGE_URL)

@infinite_cache
def load_item_data():
    try:
        resp = requests.get(ITEM_DATA_URL)
        resp.raise_for_status()
        return {str(item['itemID']): item['icon'] for item in resp.json()}
    except Exception as e:
        logging.error(f"Failed to load ITEM_DATA: {e}")
        return {}

ITEM_DATA = load_item_data()

def get_item_icon_image(item_id):
    icon_name = ITEM_DATA.get(str(item_id))
    if not icon_name:
        logging.warning(f"Item ID {item_id} not found in ITEM_DATA")
        return None
    url = FREEFIRE_ICON_URL.format(item_icon=icon_name)
    return fetch_image(url)

def get_item_icon_image_by_icon(icon_name):
    url = FREEFIRE_ICON_URL.format(item_icon=icon_name)
    return fetch_image(url)

IMAGE_POSITIONS = {
    "HEADS": {"x": 225, "y": 110, "w": 100, "h": 100},
    "FACEPAINTS": {"x": 55, "y": 260, "w": 100, "h": 100},
    "MASKS": {"x": 55, "y": 480, "w": 100, "h": 100},
    "TOPS": {"x": 950, "y": 110, "w": 100, "h": 100},
    "SECOND_TOP": {"x": 1120, "y": 640, "w": 100, "h": 100},
    "BOTTOMS": {"x": 1120, "y": 260, "w": 100, "h": 100},
    "SHOES": {"x": 1120, "y": 480, "w": 100, "h": 100},
    "ANIMATION": {"x": 950, "y": 650, "w": 100, "h": 100},
    "WEAPON": {"x": 235, "y": 665, "w": 75, "h": 60},
    "CHARACTER": {"x": 300, "y": 100, "w": 600, "h": 900},
}

OTHER_WEAPON_POSITION = {"x": 210, "y": 685, "w": 125, "h": 40}

SPECIAL_CHARACTER_POSITIONS = {
"102000004": {"x": 200, "y": 25, "w": 900, "h": 900},
"101000001": {"x": 200, "y": 25, "w": 900, "h": 900},
}

FALLBACK_ITEMS = {
    "HEADS": "211000000",
    "MASKS": "208000000",
    "FACEPAINTS": "214000000",
    "TOPS": "203000000",
    "SECOND_TOP": "212000000",
    "BOTTOMS": "204000000",
    "SHOES": "205000000",
    "ANIMATION": "900000015",
    "WEAPON": "Icon_HUD_G18",
}

@infinite_cache
def assign_outfits(clothes):
    outfits = {k: [] if k in ["HEADS", "MASKS"] else None for k in IMAGE_POSITIONS if k != "CHARACTER"}
    for cid in clothes or []:
        s = str(cid)
        if s.startswith("211"):
            if not outfits["HEADS"]:
                outfits["HEADS"] = s
            else:
                outfits["MASKS"] = s
        elif s.startswith("214") and not outfits["FACEPAINTS"]:
            outfits["FACEPAINTS"] = s
        elif s.startswith("203"):
            if not outfits["TOPS"]:
                outfits["TOPS"] = s
            else:
                outfits["SECOND_TOP"] = s
        elif s.startswith("204") and not outfits["BOTTOMS"]:
            outfits["BOTTOMS"] = s
        elif s.startswith("205") and not outfits["SHOES"]:
            outfits["SHOES"] = s
        elif s.startswith("912") and not outfits["ANIMATION"]:
            outfits["ANIMATION"] = s
        elif s.startswith("907") and not outfits["WEAPON"]:
            outfits["WEAPON"] = s
    return outfits

@infinite_cache
def load_outfit_image(category, candidate_ids, fallback_id):
    ids = candidate_ids or []
    if not isinstance(ids, list):
        ids = [ids]
      
    for cid in ids:
        img = get_item_icon_image(cid)
        if img:
            return img

    if category == "WEAPON" and fallback_id.startswith("Icon_"):
        return get_item_icon_image_by_icon(fallback_id)
    return get_item_icon_image(fallback_id)

GITHUB_TOKEN = "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"

@infinite_cache
def get_character_image(avatar_id):
    try:
        url = f"https://raw.githubusercontent.com/AdityaSharma2403/OUTFIT-S/main/CHARACTERS/{avatar_id}.png"
        headers = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
        resp = session.get(url, headers=headers)
        resp.raise_for_status()
        img = Image.open(BytesIO(resp.content)).convert("RGBA")
        return img
    except Exception as e:
        logging.error(f"Character image fetch failed: {e}")
        return None

@infinite_cache    
def overlay_images(outfits_dict, avatar_id, custom_bg_url=None):
    outfits = dict(outfits_dict) if isinstance(outfits_dict, frozenset) else outfits_dict
    
    bg_image = fetch_image(custom_bg_url) if custom_bg_url else CACHED_DEFAULT_BG.copy()
    if not bg_image:
        raise RuntimeError("Background failed to load.")
    
    bg_image = bg_image.resize((1280, 1058), Image.LANCZOS)

    for cat, pos in IMAGE_POSITIONS.items():
        if cat == "CHARACTER":
            continue
              
        img = load_outfit_image(cat, outfits.get(cat), FALLBACK_ITEMS[cat])
        if img:
            if cat == "WEAPON":
                if outfits.get("WEAPON"):
                    weapon_pos = OTHER_WEAPON_POSITION
                else:
                    weapon_pos = pos
                img = img.resize((weapon_pos['w'], weapon_pos['h']), Image.LANCZOS)
                bg_image.paste(img, (weapon_pos['x'], weapon_pos['y']), img)
            else:
                img = img.resize((pos['w'], pos['h']), Image.LANCZOS)
                bg_image.paste(img, (pos['x'], pos['y']), img)

    char_img = get_character_image(avatar_id)
    if char_img:
        pos = SPECIAL_CHARACTER_POSITIONS.get(str(avatar_id), IMAGE_POSITIONS['CHARACTER'])
        char_img = char_img.resize((pos['w'], pos['h']), Image.LANCZOS)
        bg_image.paste(char_img, (pos['x'], pos['y']), char_img)
    
    return bg_image

def generate_outfit_image(params):
    try:
        avatar_id = params.get('avatar_id', '102000004')
        clothes_raw = params.get('clothes', '[211000000, 212000000, 214000000, 208000000, 204000000, 203000000, 205000000, 900000015]')
        custom_bg_url = params.get('bg')

        try:
            clothes = json.loads(clothes_raw)
            if not isinstance(clothes, list):
                clothes = [str(clothes)]
        except json.JSONDecodeError:
            clothes = [c.strip() for c in clothes_raw.split(',') if c.strip().isdigit()]

        outfits = assign_outfits(tuple(clothes))
        hashable_outfits = frozenset((k, tuple(v) if isinstance(v, list) else v) for k, v in outfits.items())
        image = overlay_images(hashable_outfits, avatar_id, custom_bg_url)

        img_buf = BytesIO()
        image.save(img_buf, format='PNG')
        img_buf.seek(0)
        return img_buf

    except Exception as e:
        logging.error(f"Image generation error: {str(e)}", exc_info=True)
        return None