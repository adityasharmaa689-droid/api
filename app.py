import logging
import json
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from concurrent.futures import ThreadPoolExecutor
from banner import generate_banner_image
from region import region_lookup_internal
from outfit import generate_outfit_image

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
CORS(app)
executor = ThreadPoolExecutor()

@app.route('/banner-image', methods=['GET'])
def banner_image():
    try:
        uid = request.args.get('uid')
        if not uid or not uid.isdigit():
            return jsonify({"error": "Invalid or missing UID"}), 400
        
        player_data = region_lookup_internal(uid)
        if "error" in player_data:
            return jsonify(player_data), 404
        
        basic_info = player_data.get("basic_info", {})
        clan_info = player_data.get("clan_basic_info", {})
        
        params = {
            'headPic': str(basic_info.get("head_pic", "")),
            'bannerId': str(basic_info.get("banner_id", "")),
            'name': basic_info.get("nickname", "Unknown"),
            'level': basic_info.get("level", 1),
            'guild': clan_info.get("clan_name", ""),
            'pinId': str(basic_info.get("pin_id", "")),
            'celebrity': basic_info.get("celebrity_status", 0),
            'primeLevel': str(basic_info.get("prime_level", {}).get("level", 0))
        }
        
        buf = generate_banner_image(params)
        if buf:
            return send_file(buf, mimetype='image/png')
        else:
            return jsonify({"error": "Failed to generate banner image"}), 500

    except Exception as e:
        logging.error(f"Error in banner image endpoint: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/outfit-image', methods=['GET'])
def outfit_image():
    try:
        uid = request.args.get('uid')
        if uid and uid.isdigit():
            player_data = region_lookup_internal(uid)
            if "error" in player_data:
                return jsonify(player_data), 404
            
            profile_info = player_data.get("profile_info", {})
            basic_info = player_data.get("basic_info", {})
            
            clothes = profile_info.get("clothes", [])
            weapon_skins = basic_info.get("weapon_skin_shows", [])
            
            all_items = clothes + weapon_skins
            
            params = {
                'avatar_id': str(profile_info.get("avatar_id", "102000004")),
                'clothes': json.dumps(all_items),
                'bg': request.args.get('bg')
            }
        else:
            params = {
                'avatar_id': request.args.get('avatar_id', '102000004'),
                'clothes': request.args.get('clothes', '[211000000, 212000000, 214000000, 208000000, 204000000, 203000000, 205000000, 900000015]'),
                'bg': request.args.get('bg')
            }
        
        buf = generate_outfit_image(params)
        if buf:
            return send_file(buf, mimetype='image/png')
        else:
            return jsonify({"error": "Failed to generate outfit image"}), 500

    except Exception as e:
        logging.error(f"Error in outfit image endpoint: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/region", methods=["GET"])
def region_lookup():
    uid = request.args.get("uid")
    if not uid or not uid.isdigit():
        return jsonify({"error": "Invalid or missing UID"}), 400
    
    try:
        result = region_lookup_internal(uid)
        if "error" in result:
            return jsonify(result), 404
            
        return app.response_class(
            response=json.dumps(result, indent=2, sort_keys=True),
            status=200,
            mimetype="application/json"
        )
    except Exception as e:
        logging.error(f"Error in region lookup: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "service": "Free Fire API Server"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)