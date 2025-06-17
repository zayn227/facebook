 import os
 import random
 import cloudinary
 import cloudinary.api
 import cloudinary.uploader
 from moviepy.editor import VideoFileClip, AudioFileClip, CompositeVideoClip, ImageClip
 import requests
 import gc
 
 # --- Google API aur YouTube Upload ke liye Imports ---
 from google.oauth2.credentials import Credentials
 from google.auth.transport.requests import Request
 from googleapiclient.discovery import build
 from googleapiclient.http import MediaFileUpload
 
 # --- Cloudinary ka Setup ---
 # Yeh credentials aapko apne Cloudinary account se milenge
 cloudinary.config(
     cloud_name="decqrz2gm",
     api_key="288795273313996",
     api_secret="Q2anv-1fJKaF6zMSyfhzVEz-kWc",
     secure=True
 )
 
 # --- Folder aur File ke Paths ---
 CLOUDINARY_AUDIO_FOLDER = "krishanjivoice"
 CLOUDINARY_VIDEO_FOLDER = "krishanjiedits"
 OUTPUT_LOCAL_FOLDER = "output_videos"
 TEMP_DOWNLOAD_FOLDER = "temp_downloads"
 
 # Image files jo script ke saath same folder me honi chahiye
 IMAGE_OVERLAY_PATH = "says.png"
 TEXT_OVERLAY_PATH = "transparent_text.png"
 
 # --- YouTube API ka Setup ---
 YOUTUBE_API_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
 YOUTUBE_API_SERVICE_NAME = "youtube"
 YOUTUBE_API_VERSION = "v3"
 
 # --- Temp aur Output folders banana ---
 os.makedirs(OUTPUT_LOCAL_FOLDER, exist_ok=True)
 os.makedirs(TEMP_DOWNLOAD_FOLDER, exist_ok=True)
 
 
 def get_youtube_service():
     """Google se authenticate karta hai GitHub Secrets ka istemal karke."""
     print("Google credentials ko load kiya ja raha hai...")
     
     # Yeh secrets GitHub Actions environment se aayenge
     client_id = os.environ.get("GOOGLE_CLIENT_ID")
     client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
     refresh_token = os.environ.get("GOOGLE_REFRESH_TOKEN")
 
     if not all([client_id, client_secret, refresh_token]):
         raise ValueError("Ek ya zyada Google secrets (CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN) nahi mile.")
 
     creds = Credentials(
         token=None,
         refresh_token=refresh_token,
         token_uri="https://oauth2.googleapis.com/token",
         client_id=client_id,
         client_secret=client_secret,
         scopes=YOUTUBE_API_SCOPES
     )
 
     try:
         creds.refresh(Request())
         print("Google access token safaltapurvak refresh ho gaya.")
         return build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, credentials=creds)
     except Exception as e:
         print(f"Access token refresh karne me error: {e}")
         raise
 
 def upload_to_youtube(video_path, title, description, tags):
     """Video ko YouTube par upload karta hai."""
     try:
         print("\n--- YouTube Upload process shuru ho raha hai ---")
         youtube = get_youtube_service()
 
         body = {
             'snippet': {
                 'title': title,
                 'description': description,
                 'tags': tags,
                 'categoryId': '22'   # People & Blogs
             },
             'status': {
                 'privacyStatus': 'public'   # 'private', 'public', ya 'unlisted'
             }
         }
 
         media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
 
         print(f"Video '{title}' YouTube par upload ho rahi hai...")
         request = youtube.videos().insert(
             part=','.join(body.keys()),
             body=body,
             media_body=media
         )
         response = request.execute()
         print(f"Video safaltapurvak upload ho gayi! Video ID: {response['id']}")
 
     except Exception as e:
         print(f"YouTube upload ke dauran error: {e}")
 
 # Yeh naya function hai Facebook par upload karne ke liye
 def upload_to_facebook(video_path, title):
     """Video ko Facebook Page par upload karta hai."""
     print("\n--- Facebook Upload process shuru ho raha hai ---")
     
     page_id = os.environ.get("FACEBOOK_PAGE_ID")
     page_access_token = os.environ.get("FACEBOOK_PAGE_ACCESS_TOKEN")
 
     if not page_id or not page_access_token:
         print("Facebook Page ID ya Access Token nahi mila. Upload skip kiya ja raha hai.")
         return
 
     # Facebook Graph API ka video endpoint
     url = f"https://graph-video.facebook.com/v20.0/{page_id}/videos"
     
     files = {
         'source': open(video_path, 'rb')
     }
     params = {
         'description': title,
         'access_token': page_access_token
     }
 
     try:
         print(f"Video '{title}' Facebook Page par upload ho rahi hai...")
         response = requests.post(url, files=files, params=params)
         response.raise_for_status()   # Agar koi error ho (jaise 400 ya 500) to exception raise karega
         result = response.json()
         print(f"Video safaltapurvak Facebook par post ho gayi! Post ID: {result.get('id')}")
     except Exception as e:
         print(f"Facebook upload ke dauran error: {e}")
         print("Response:", response.text)
 
 def get_random_cloudinary_asset(folder, resource_type):
     """Cloudinary folder se random audio ya video nikalta hai."""
     try:
         result = cloudinary.api.resources(
             type="upload",
             prefix=f"{folder}/",
             resource_type=resource_type,
             max_results=500
         )
         assets = result.get('resources', [])
         if not assets:
             print(f"Cloudinary folder '{folder}' me koi {resource_type} file nahi mili.")
             return None
         return random.choice(assets)
     except Exception as e:
         print(f"Cloudinary se files fetch karne me error: {e}")
         return None
 
 def download_file(url, local_path):
     """File ko URL se download karke local path par save karta hai."""
     try:
         print(f"Downloading: {url}")
         response = requests.get(url, stream=True)
         response.raise_for_status()
         with open(local_path, 'wb') as f:
             for chunk in response.iter_content(chunk_size=8192):
                 f.write(chunk)
         print("Download complete.")
         return True
     except Exception as e:
         print(f"Download karne me error: {e}")
         return False
 
 def merge_audio_video_and_cut():
     """Main function jo saare kaam karta hai: merge, overlay, save, aur upload."""
     print("--- Video-Audio Merging process shuru ---")
     audio_clip, video_clip, final_video_clip = None, None, None
     local_audio_path, local_video_path = None, None
 
     try:
         # 1. Cloudinary se random audio aur video get karna
         audio_asset = get_random_cloudinary_asset(CLOUDINARY_AUDIO_FOLDER, "video")
         video_asset = get_random_cloudinary_asset(CLOUDINARY_VIDEO_FOLDER, "video")
         if not audio_asset or not video_asset:
             return
 
         audio_url = audio_asset['secure_url']
         video_url = video_asset['secure_url']
         audio_filename = os.path.basename(audio_url).split('?')[0]
         video_filename = os.path.basename(video_url).split('?')[0]
         local_audio_path = os.path.join(TEMP_DOWNLOAD_FOLDER, audio_filename)
         local_video_path = os.path.join(TEMP_DOWNLOAD_FOLDER, video_filename)
 
         # 2. Audio aur video download karna
         if not download_file(audio_url, local_audio_path) or not download_file(video_url, local_video_path):
             return
 
         # 3. Clips load karna aur video ko audio ki duration ke hisab se cut karna
         print("\nClips ko process kiya ja raha hai...")
         audio_clip = AudioFileClip(local_audio_path)
         video_clip = VideoFileClip(local_video_path)
         final_video_clip = video_clip.subclip(0, audio_clip.duration).set_audio(audio_clip)
 
         # 4. Overlays add karna
         logo_clip = (ImageClip(IMAGE_OVERLAY_PATH)
                      .set_duration(5.0)
                      .set_start(0.5)
                      .crossfadein(1.0).crossfadeout(1.0)
                      .set_pos(('center', (final_video_clip.h / 2) - (ImageClip(IMAGE_OVERLAY_PATH).h / 2) - 600))) # Vertical offset -600
         
         text_clip = (ImageClip(TEXT_OVERLAY_PATH)
                      .set_duration(3.0)
                      .set_start(final_video_clip.duration - 3.0)
                      .crossfadein(1.0)
                      .set_pos(('center', 'center')))
 
         final_clip = CompositeVideoClip([final_video_clip, logo_clip, text_clip])
 
         # 5. Final video file save karna
         output_filename = f"final_video_{os.path.splitext(audio_filename)[0]}.mp4"
         output_filepath = os.path.join(OUTPUT_LOCAL_FOLDER, output_filename)
         print(f"\nFinal video yahan save ho rahi hai: {output_filepath}")
         
         final_clip.write_videofile(
             output_filepath,
             codec='libx264',
             audio_codec='aac',
             temp_audiofile=os.path.join(TEMP_DOWNLOAD_FOLDER, 'temp-audio.m4a'),
             remove_temp=True,
             fps=final_clip.fps if final_clip.fps else 24
         )
         print("Final video safaltapurvak save ho gayi.")
 
         # 6. Final video ko YouTube par upload karna
         video_title = "Inspirational - Lord Krishna Says 🥰"
         video_description = "Ek chhota prerna bhara video..."
         video_tags = ["motivation", "krishanji", "lord krishna"]
         upload_to_youtube(output_filepath, video_title, video_description, video_tags)
         # Ab video ko Facebook par upload karein
         upload_to_facebook(output_filepath, video_title)
 
     except Exception as e:
         print(f"Main process me error: {e}")
     finally:
         # 7. Saari media clips ko close karna
         print("\nSaari media clips close ki ja rahi hain...")
         for clip in [audio_clip, video_clip, final_video_clip, final_clip]:
             if clip:
                 try:
                     clip.close()
                 except Exception:
                     pass
         gc.collect()
 
         # 8. Temporary downloaded files ko delete karna
         print("\nTemporary files clean ki ja rahi hain...")
         for path in [local_audio_path, local_video_path]:
             if path and os.path.exists(path):
                 try:
                     os.remove(path)
                     print(f"Removed: {path}")
                 except Exception as e:
                     print(f"Temp file {path} delete karne me error: {e}")
 
 if __name__ == "__main__":
     # IMPORTANT: Yahan apne secrets (keys) mat daalna.
     # Inhe GitHub Secrets me daalna hai, jaisa neeche bataya gaya hai.
     # Yeh script ab GitHub Actions ke environment se secrets lega.
     merge_audio_video_and_cut()
