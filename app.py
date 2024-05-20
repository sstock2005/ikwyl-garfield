from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip, AudioFileClip, TextClip
from config import PRIVATE_API_KEY, TEMPORARY_DIR, MAX_STORAGE, VIDEO_FILE
from flask import Flask, send_file, render_template, request
from urllib.parse import unquote
from PIL import Image
from io import BytesIO
import numpy as np
import hashlib
import shutil
import requests
import base64
import os

app = Flask(__name__)

ip_list = []
rate_limited = []

def map_img(address):
    address = address.replace(" ", "+")
    url = f"https://maps.googleapis.com/maps/api/staticmap?center={address}&zoom=13&size=590x330&maptype=satellite&markers=size:large%7Ccolor:red%7Clabel:X%7C{address}&key={PRIVATE_API_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        image = Image.open(BytesIO(response.content))
        img_io = BytesIO()
        image.save(img_io, 'PNG')
        img_io.seek(0)
        return img_io
    else:
        print("make sure you set an API Key in config.py!")
        exit()
      
def overlay(video, img_io, address):
    
    dir_size = sum(os.path.getsize(os.path.join(TEMPORARY_DIR, f)) for f in os.listdir(TEMPORARY_DIR) if os.path.isfile(os.path.join(TEMPORARY_DIR, f)))
    dir_mb = dir_size / (1024 * 1024)
    
    if dir_mb > MAX_STORAGE:
        for filename in os.listdir(TEMPORARY_DIR):
            file_path = os.path.join(TEMPORARY_DIR, filename)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print("error deleting files")
                
    img_io.seek(0)
    img_hash = hashlib.md5(img_io.read()).hexdigest()
    temp_path = f"{TEMPORARY_DIR}{img_hash}.mp4"

    if not os.path.exists(temp_path):
        video = VideoFileClip(video)
        img_io.seek(0)
        img = Image.open(img_io).convert("RGB")
        img_array = np.array(img)
        image = ImageClip(img_array)
        image = image.resize(height=int(video.size[1] * 0.51)).set_duration(video.duration - 3.8 + 0.05) # 10 - 3.8 + 0.05
        image = image.set_position((430, 230))
        image = image.set_start(3.8)
        image = image.fadein(0.2)
        image = image.fadeout(1)
        text = TextClip(f"{address}", fontsize=70, color='white', stroke_color='black', stroke_width=1)
        text_pos = ('center', image.size[1] * 0.1)
        text = text.set_start(3.8)
        text = text.set_position(text_pos)
        text = text.set_duration(video.duration)
        text = text.fadein(0.2)
        text = text.fadeout(1)
        video = video.fadeout(1)
        result = CompositeVideoClip([video, image, text])
        audio = AudioFileClip(video.audio.filename)
        audio.write_audiofile(f"{TEMPORARY_DIR}{img_hash}.aac", codec='aac')
        result.audio = AudioFileClip(f"{TEMPORARY_DIR}{img_hash}.aac")
        result.write_videofile(temp_path, codec='libx264', audio_codec='aac')
            
    with open(temp_path, 'rb') as f:
        binary_io = BytesIO(f.read())

    return binary_io
 
@app.route("/<encoded>.mp4", methods=['GET'])
def convert(encoded):
    
    client_ip = request.headers.get('cf-connecting-ip', request.remote_addr) # for cloudflare
    ip_list.append(client_ip)
    
    if ip_list.count(client_ip) > 50 or rate_limited.count(client_ip) > 0:
        rate_limited.append(client_ip)
        for n in ip_list:
            if n == client_ip:
                ip_list.remove(n)
        return "ratelimited, try again tomorrow", 500
    
    address = unquote(base64.b64decode(encoded).decode())
    img_io = map_img(address)
    video_io = overlay(VIDEO_FILE, img_io, address)

    try:
        return send_file(video_io, mimetype="video/mp4", download_name="ikwyl.mp4")
    except:
        return "error", 500

@app.route("/", methods=['GET'])
def index():
    return render_template('index.html')
    
if __name__ == '__main__':
    app.run("0.0.0.0", 80, False, threaded=True, use_reloader=False) # ssl if you want: ssl_context=('cert.pem', 'key.pem')
