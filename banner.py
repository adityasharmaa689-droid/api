import logging
import requests
import os
from io import BytesIO
from flask import send_file
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv
import hashlib

load_dotenv()

logging.basicConfig(level=logging.INFO)

CACHE_DIR = "./image_cache"
FONT_FILENAME = "cached_font.ttf"
BADGE_FILENAME = "cached_badge.png"
FONT_URL = "https://raw.githubusercontent.com/Thong-ihealth/arial-unicode/main/Arial-Unicode-Bold.ttf"
BADGE_URL = "https://i.ibb.co/YBrt0j0m/icon.png"
FALLBACK_BANNER_ID = "900000014"
FALLBACK_AVATAR_ID = "900000013"

GITHUB_BASE_URL = os.getenv("GITHUB_BASE_URL", "https://raw.githubusercontent.com/AdityaSharma2403/image/main")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "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")

try:
    os.makedirs(CACHE_DIR, exist_ok=True)
except OSError as e:
    logging.error(f"Failed to create cache directory {CACHE_DIR}: {e}")
    CACHE_DIR = None

session = requests.Session()
if GITHUB_TOKEN:
    session.headers.update({'Authorization': f'token {GITHUB_TOKEN}'})

def get_cache_filename(url):
    if CACHE_DIR is None:
        return None
    return os.path.join(CACHE_DIR, hashlib.md5(url.encode()).hexdigest() + ".png")

def fetch_image(url):
    if CACHE_DIR is None:
        try:
            resp = session.get(url)
            resp.raise_for_status()
            return Image.open(BytesIO(resp.content)).convert("RGBA")
        except Exception as e:
            logging.error(f"Failed to fetch {url}: {str(e)}")
            return None

    cache_file = get_cache_filename(url)
    
    if os.path.exists(cache_file):
        try:
            img = Image.open(cache_file).convert("RGBA")
            return img
        except Exception as e:
            logging.warning(f"Failed to load cached image {cache_file}: {str(e)}")
            try:
                os.remove(cache_file)
            except:
                pass
    
    try:
        resp = session.get(url)
        resp.raise_for_status()
        img = Image.open(BytesIO(resp.content)).convert("RGBA")
        
        try:
            img.save(cache_file, format='PNG')
        except Exception as e:
            logging.warning(f"Failed to save image to cache {cache_file}: {str(e)}")
        
        return img
    except Exception as e:
        logging.error(f"Failed to fetch {url}: {str(e)}")
        return None

def download_and_cache_file(url, filename):
    if CACHE_DIR is None:
        return False
        
    try:
        response = session.get(url)
        response.raise_for_status()
        filepath = os.path.join(CACHE_DIR, filename)
        with open(filepath, 'wb') as f:
            f.write(response.content)
        logging.info(f"Successfully cached {filename}")
        return True
    except Exception as e:
        logging.error(f"Failed to download and cache {filename}: {e}")
        return False

def load_cached_file(filename):
    if CACHE_DIR is None:
        return None
        
    filepath = os.path.join(CACHE_DIR, filename)
    if os.path.exists(filepath):
        try:
            with open(filepath, 'rb') as f:
                return f.read()
        except Exception as e:
            logging.error(f"Error reading cached {filename}: {e}")
    return None

FONT_DATA = None
BADGE_DATA = None

FONT_DATA = load_cached_file(FONT_FILENAME)
if FONT_DATA is None:
    if download_and_cache_file(FONT_URL, FONT_FILENAME):
        FONT_DATA = load_cached_file(FONT_FILENAME)

BADGE_DATA = load_cached_file(BADGE_FILENAME)
if BADGE_DATA is None:
    if download_and_cache_file(BADGE_URL, BADGE_FILENAME):
        BADGE_DATA = load_cached_file(BADGE_FILENAME)

def get_custom_font(size):
    if FONT_DATA:
        try:
            return ImageFont.truetype(BytesIO(FONT_DATA), size)
        except Exception as e:
            logging.error(f"Error loading truetype font: {e}")
    return ImageFont.load_default()

def get_banner_url(banner_id):
    return f"{GITHUB_BASE_URL}/BANNERS/{banner_id}.png"

def get_avatar_url(avatar_id):
    return f"{GITHUB_BASE_URL}/AVATARS/{avatar_id}.png"

def get_pin_url(pin_id):
    return f"{GITHUB_BASE_URL}/PINS/{pin_id}.png"

def get_prime_level_url(prime_level):
    return f"{GITHUB_BASE_URL}/PRIME-LEVEL/{prime_level}.png"

def generate_banner_image(params):
    try:
        headPic = str(params.get('headPic', FALLBACK_AVATAR_ID))
        bannerId = str(params.get('bannerId', FALLBACK_BANNER_ID))
        name = str(params.get('name', 'Unknown'))
        level = int(params.get('level', 1))
        guild = str(params.get('guild', ''))
        pin = str(params.get('pinId', '900000012'))
        celebrity = params.get('celebrity', '0')
        prime = str(params.get('primeLevel', ''))

        try:
            celeb_int = int(celebrity)
            celeb = 60 <= celeb_int <= 99999999
        except ValueError:
            celeb = str(celebrity).lower() in ['1', 'true', 'yes']

        avatar_img = fetch_image(get_avatar_url(str(headPic))) or fetch_image(get_avatar_url(FALLBACK_AVATAR_ID))
        banner_img = fetch_image(get_banner_url(str(bannerId))) or fetch_image(get_banner_url(FALLBACK_BANNER_ID))

        if not avatar_img or not banner_img:
            return None

        w, h = 2048, 512
        aw = 512
        bw = w - aw
        av = avatar_img.resize((aw, h), Image.LANCZOS)
        bn = banner_img.resize((bw, h), Image.LANCZOS)
        canvas = Image.new("RGBA", (w, h))
        canvas.paste(av, (0, 0), av)
        canvas.paste(bn, (aw, 0), bn)

        draw = ImageDraw.Draw(canvas)
        font = get_custom_font(120)
        draw.text((aw + 50, 50), name, font=font, fill="white")
        if guild:
            draw.text((aw + 50, 300), guild, font=font, fill="white")

        lvl_txt = f"Lvl. {level}"
        lx = aw + bw - (335 if level < 10 else 380 if level < 100 else 435)
        draw.text((lx, 370), lvl_txt, font=font, fill="white")

        if pin and pin.lower() != "default":
            pin_img = fetch_image(get_pin_url(str(pin)))
            if pin_img:
                pin_img = pin_img.resize((150, 150), Image.LANCZOS)
                canvas.paste(pin_img, (10, 350), pin_img)

        if celeb and BADGE_DATA:
            bd = Image.open(BytesIO(BADGE_DATA)).convert("RGBA").resize((150, 150), Image.LANCZOS)
            canvas.paste(bd, (350, 10), bd)
        elif prime:
            prime_img = fetch_image(get_prime_level_url(str(prime)))
            if prime_img:
                prime_img = prime_img.resize((150, 150), Image.LANCZOS)
                canvas.paste(prime_img, (350, 10), prime_img)

        buf = BytesIO()
        canvas.save(buf, format='PNG')
        buf.seek(0)
        return buf

    except Exception as e:
        logging.error(f"Error generating banner: {str(e)}")
        return None