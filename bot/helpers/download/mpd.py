import subprocess
import threading
import time
import os
import requests
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from bot.config import ytdlp, mp4decrypt, aria2c, proxies
from bot.config import UPLOAD_CONGIF
from bot.helpers.utils import parse_file_name
from bot.helpers.parser.mpd import MPD
from bot.helpers.utils import get_group_tag
from bot.config import PROXY_CONFIG, dl_folder
from bot.helpers.upload.gdrive import GoogleDriveUploader
from bot.helpers.upload.ftp import ftpUploader
from bot.helpers.upload.tg import tgUploader

class Processor():
    def __init__(self, app, message, link, split, video_resolution=None, video_quality=None, audio_codec=None, audio_quality=None, alang=None, fallback_language=None, init_file_name=None, ott=None, headers= None,  parse_subs = True):
        self.app = app
        self.message = message
        self.link = link
        self.split = split # Store the split variable
        self.video_resolution = video_resolution
        self.video_quality = video_quality
        self.audio_codec = audio_codec
        self.audio_quality = audio_quality
        self.alang = alang
        self.fallback_language = fallback_language
        self.init_file_name = init_file_name
        self.ott = ott
        self.dl_headers = headers
        self.custom_group_tag = get_group_tag(str(self.message.from_user.id))

        self.process_start = time.time()
        self.end_code = str(time.time()).replace(".", "")

        
        self.msg = self.message.reply_text(f'''Processing...''')

        result, self.final_file_name = MPD(
            link, init_file_name, ott, self.custom_group_tag, parse_subs=parse_subs).refine(video_resolution=self.video_resolution, video_quality=self.video_quality, audio_codec=self.audio_codec, audio_quality=self.audio_quality, audio_languages=None, fallback_language=self.fallback_language)
        
        self.video_data = result.get('video')
        self.audio_data = result.get('audio')
        self.subtitles_data = result.get('subtitle')

        file_info = parse_file_name(init_file_name, video_resolution= "{}p".format(self.video_data['height']), GR = self.custom_group_tag)
        self.path = file_info.get('path')


    def download_audio_stream(self, stream_format, filename):
        dest = os.path.join(dl_folder, f"{filename}.m4a")
        try:
            cmd = [
                f"{ytdlp}"
            ]

            if PROXY_CONFIG.proxy_url and PROXY_CONFIG.proxy_url.strip() and PROXY_CONFIG.USE_PROXY_WHILE_DOWNLOADING:  # Check if PROXY_CONFIG.proxy_url is not empty or None
                cmd.extend(["--proxy", PROXY_CONFIG.proxy_url])

            

            cmd.extend(["--allow-unplayable-formats",
                        "-f", str(stream_format)])
            


            if self.dl_headers is not None:
                for key, value in self.dl_headers.items():
                    cmd.extend(["--add-headers", f'{key}:{value}'])
                        


            cmd.extend(
                [
                    "--geo-bypass-country",
                    "IN",
                    f"{self.link}",
                    "-o",
                    dest,
                ])


            dl_process = subprocess.Popen(cmd)
            dl_process.wait()
        except Exception as e:
            self.msg.edit(f"Error Running YT-DLP Command {e}")
            return

    def mpd_download(self):
        threads = []

        for i, audio_info in enumerate(self.audio_data):
            stream_format = audio_info["id"]
            filename = f"enc_{stream_format}_{self.end_code}"
            thread = threading.Thread(
                target=self.download_audio_stream, args=(
                    stream_format, filename)
            )
            threads.append(thread)
            thread.start()
            print(
                f"[+] Downloading Audio Stream {i + 1} of {len(self.audio_data)}")

        try:
            video_format = self.video_data["id"]
            dest = os.path.join(
                dl_folder, f"enc_{video_format}_{self.end_code}.mp4")
            
            
            video_cmd = [
                f"{ytdlp}",
            ]

            if PROXY_CONFIG.proxy_url and PROXY_CONFIG.proxy_url.strip() and PROXY_CONFIG.USE_PROXY_WHILE_DOWNLOADING:  # Check if PROXY_CONFIG.proxy_url is not empty or None
                video_cmd.extend(["--proxy", PROXY_CONFIG.proxy_url])


            if self.dl_headers is not None:
                for key, value in self.dl_headers.items():
                    video_cmd.extend(["--add-headers", f'{key}:{value}'])


            video_cmd.extend([
                "--geo-bypass-country",
                "IN",
                "--allow-unplayable-formats",
                "-f",
                str(video_format),
                f"{self.link}",
                "-o",
                dest,
            ])

            print("[+] Downloading Video Stream")
            subprocess.call(video_cmd)
        except Exception as e:
            self.msg.edit(f"Error Downloading Video File {e}")
            return

        for thread in threads:
            thread.join()

        return self.end_code

    def decrypt(self):
         try:
             # AUDIO
             for audio_info in self.audio_data:
                 stream_format = audio_info["id"]

                 enc_dl_audio_file_name = os.path.join(
                     dl_folder, f"enc_{stream_format}_{self.end_code}.m4a"
                 )
                 dec_out_audio_file_name = os.path.join(
                     dl_folder, f"dec_{stream_format}_{self.end_code}.m4a"
                 )

                 # No decryption → rename file
                 if os.path.exists(enc_dl_audio_file_name):
                     os.rename(enc_dl_audio_file_name, dec_out_audio_file_name)

             # VIDEO
             video_format = self.video_data["id"]

             enc_dl_video_file_name = os.path.join(
                 dl_folder, f"enc_{video_format}_{self.end_code}.mp4"
             )
             dec_out_video_file_name = os.path.join(
                 dl_folder, f"dec_{video_format}_{self.end_code}.mp4"
             )

             # No decryption → rename file
             if os.path.exists(enc_dl_video_file_name):
                 os.rename(enc_dl_video_file_name, dec_out_video_file_name)

         except Exception as e:
             raise Exception("Error During Renaming: " + str(e))

         return self.end_code

    
    def dl_subs_v2(self):

        if self.subtitles_data is not None:

            for sub in self.subtitles_data:
                
                subs_lang = sub["lang"]
                subs_url = sub['baseURL']

                dest = os.path.join(
                    dl_folder, f"subtitle_{subs_lang}_{self.end_code}.vtt")


                print(f"[+] Downloading Subtitle - {subs_lang}")
                print(f"[+] URL - {subs_url}")

                request_headers = {
                    'user-agent' : "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
                }
                
                if self.dl_headers is not None:
                    for key, value in self.dl_headers.items():
                        request_headers[key] = value

                r = requests.get(subs_url, proxies=proxies, headers=request_headers, allow_redirects=True)
                open(dest, 'wb').write(r.content)

    def dl_subs(self):

        if self.subtitles_data is not None:

            for sub in self.subtitles_data:
                subs_lang = sub["lang"]
                subs_url = sub['baseURL'] + sub["url"]
                subs_dl_cmd = [
                    f"{ytdlp}",
                    "--geo-bypass-country",
                    "IN",
                    "--add-headers",
                    "user-agent:Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
                    f"{subs_url}",
                    "-o",
                    f"subtitle_{subs_lang}_{self.end_code}.vtt"
                ]
                print(f"[+] Downloading Subtitle - {sub['lang']}")
                print(f"[+] URL - {subs_url}")
                subprocess.call(subs_dl_cmd)

    def mux_video(self, startTime=None, endTime=None, custom_out_name=None):

        file_prefix = "enc" if self.key is None else "dec"

        dec_out_video_file_name = os.path.join(
            dl_folder, f"{file_prefix}_{self.video_data['id']}_{self.end_code}.mp4")
        audio_files = [
            os.path.join(
                dl_folder, f"{file_prefix}_{audio_info['id']}_{self.end_code}.m4a")
            for audio_info in self.audio_data
        ]

        ffmpeg_opts = ["ffmpeg", "-y", "-i", dec_out_video_file_name]

        for audio_file, audio_info in zip(audio_files, self.audio_data):
            lang = audio_info["lang"]
            ffmpeg_opts.extend(["-i", audio_file])

        if self.subtitles_data is not None:

            subs_file = [
                os.path.join(
                    dl_folder, f"subtitle_{sub['lang']}_{self.end_code}.vtt")
                for sub in self.subtitles_data
            ]

            for individual_subs_file in subs_file:
                ffmpeg_opts.extend(["-i", individual_subs_file])

        if startTime is not None and endTime is not None:
            ffmpeg_opts.extend(["-ss", f"{startTime}"])
            ffmpeg_opts.extend(["-to", f"{endTime}"])

        ffmpeg_opts.extend(["-map", "0:v:0"])

        for i in range(len(self.audio_data)):
            ffmpeg_opts.extend(["-map", f"{i+1}:a:0"])

        if self.subtitles_data is not None:
            for i in range(len(self.subtitles_data)):
                ffmpeg_opts.extend(["-map", f"{len(self.audio_data)+1}:s:0"])

        ffmpeg_opts.extend(
            ["-metadata", f"encoded_by={self.custom_group_tag}"])
        ffmpeg_opts.extend(["-metadata:s:a", f"title={self.custom_group_tag}"])
        ffmpeg_opts.extend(["-metadata:s:v", f"title={self.custom_group_tag}"])

        if self.subtitles_data is not None:
            ffmpeg_opts.extend(
                ["-metadata:s:s", f"title={self.custom_group_tag}"])

        for i, audio_info in enumerate(self.audio_data):
            lang = audio_info["lang"]
            ffmpeg_opts.extend(
                ["-metadata:s:a:{0}".format(i), f"language={lang}"])

        if self.subtitles_data is not None:
            for i in range(len(self.subtitles_data)):
                ffmpeg_opts.extend(
                    ["-metadata:s:s:{0}".format(i), f"language={self.subtitles_data[i]['lang']}"])

        out_name = f"{self.end_code}.mkv"
        
        # Determine final output name
        out_file_name = custom_out_name if custom_out_name else self.final_file_name
        
        ffmpeg_opts.extend(["-c", "copy", out_name])

        try:
            subprocess.check_call(ffmpeg_opts, stdout=subprocess.DEVNULL)
        except subprocess.CalledProcessError as e:
            raise Exception(f"FFMPEG Error: {e}")

        try:
            # If using custom_out_name, ensure it is in dl_folder if it's just a filename
            if custom_out_name and not os.path.isabs(custom_out_name):
                 out_file_name = os.path.join(dl_folder, custom_out_name)
            
            os.rename(out_name, out_file_name)
        except OSError as e:
            raise Exception(f"OSError: {e}",)

        for audio_file in audio_files:
            try:
                os.remove(audio_file)
            except OSError as e:
                print(f"OSError: {e}")
                pass
        try:
            os.remove(dec_out_video_file_name)
        except OSError as e:
            print(f"OSError: {e}")
            pass

        return out_file_name

    def merge_segments(self, segment_files):
        """Merge multiple MKV segments into one file using ffmpeg concat."""
        concat_file_path = os.path.join(dl_folder, f"concat_list_{self.end_code}.txt")
        
        with open(concat_file_path, "w") as f:
            for segment in segment_files:
                # Escape single quotes for ffmpeg concat demuxer
                escaped_path = segment.replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")

        out_file_name = self.final_file_name
        
        # Copy everything, including the metadata set in previous muxing steps
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", 
            "-i", concat_file_path, "-c", "copy", out_file_name
        ]
        
        try:
            subprocess.check_call(cmd, stdout=subprocess.DEVNULL)
        except subprocess.CalledProcessError as e:
            raise Exception(f"Error merging segments: {e}")
        finally:
            if os.path.exists(concat_file_path):
                os.remove(concat_file_path)
            # Clean up segment files
            for segment in segment_files:
                if os.path.exists(segment):
                    os.remove(segment)
        
        return out_file_name

    def start_process(self, startTime=None, endTime=None):
        task_start_time = time.time()
        self.key = "12345" # Placeholder for logic check later
        
        final_output_file = None

        # CHECK IF SPLIT IS REQUESTED
        if self.split and int(self.split) > 0:
            try:
                parsed_url = urlparse(self.link)
                query_params = parse_qs(parsed_url.query)
                
                # Ensure begin and end exist
                if 'begin' not in query_params or 'end' not in query_params:
                    raise ValueError("URL must contain 'begin' and 'end' timestamps for splitting.")

                origin_begin = int(query_params['begin'][0])
                origin_end = int(query_params['end'][0])
                split_duration_sec = int(self.split) * 60
                
                segment_files = []
                current_begin = origin_begin
                part_count = 1

                total_parts = (origin_end - origin_begin + split_duration_sec - 1) // split_duration_sec

                while current_begin < origin_end:
                    current_end = min(current_begin + split_duration_sec, origin_end)
                    
                    # Regenerate Unique ID for this segment to prevent file collision
                    self.end_code = str(time.time()).replace(".", "") + f"_{part_count}"

                    # Construct new URL for this segment
                    query_params['begin'] = [str(current_begin)]
                    query_params['end'] = [str(current_end)]
                    new_query = urlencode(query_params, doseq=True)
                    self.link = urlunparse(parsed_url._replace(query=new_query))

                    self.msg.edit(
                        f'<code>[+]</code> <b>Processing Part {part_count}/{total_parts}</b>\n'
                        f'Time: {current_begin} - {current_end}'
                    )

                    # 1. Download Subs (Only need to do this once strictly, but safe to do per loop or skip)
                    # Note: Usually subs are full file, but if they are segmented by URL, we call it.
                    # We will skip redownloading subs for optimization if they are static, 
                    # but if subs are also time-ranged, keep this. Assuming static subs for now or small enough.
                    if part_count == 1: 
                        self.dl_subs_v2()

                    # 2. Download Segment
                    self.mpd_download()

                    # 3. Decrypt Segment
                    self.decrypt()

                    # 4. Mux Segment to temp file
                    temp_segment_name = f"segment_{part_count}_{self.end_code}.mkv"
                    temp_full_path = self.mux_video(startTime, endTime, custom_out_name=temp_segment_name)
                    segment_files.append(temp_full_path)

                    current_begin = current_end
                    part_count += 1

                # Merge all parts
                self.msg.edit('<code>[+]</code> <b>Merging Segments...</b>')
                final_output_file = self.merge_segments(segment_files)

            except Exception as e:
                self.msg.edit(f"Error during split processing: {e}")
                return

        else:
            # STANDARD NO-SPLIT LOGIC
            self.msg.edit(
                '<code>[+]</code> <b>Downloading</b>\n<code>{}</code>'.format(self.final_file_name))
            
            self.dl_subs_v2()
            self.mpd_download()


            self.msg.edit('<code>[+]</code> <b>Decrypting</b>\n<code>{}</code>\n\n<code>[+]</code> <b>Using Keys\n<code>{}</code></b>'.format(
                self.final_file_name, "\n No Keys"))


            self.decrypt()

            self.msg.edit(
                '<code>[+]</code> <b>Muxing</b>\n<code>{}</code>'.format(self.final_file_name))

            final_output_file = self.mux_video(startTime, endTime)


        # UPLOAD LOGIC
        if final_output_file:
            self.msg.edit(
                '<code>[+]</code> <b>Uploading</b>\n<code>{}</code>'.format(self.final_file_name))
            
            upload_path = "BOT Uploads/{}/{}".format(self.ott, self.path)


            upload_to = UPLOAD_CONGIF.upload_to.lower() if UPLOAD_CONGIF.upload_to.lower() in ['tg', 'ftp', 'gdrive'] else UPLOAD_CONGIF.default_upload_to

            if upload_to == "tg":
                uploader = tgUploader(self.app, self.msg)
                uploader.upload_file(final_output_file)

            elif upload_to == "ftp":
                uploader = ftpUploader(self.app, self.msg, task_start_time)
                uploader.upload_file(final_output_file, upload_path, ott=self.ott)

            elif upload_to == "gdrive":
                uploader = GoogleDriveUploader(self.app, self.msg, task_start_time)
                uploader.upload_file(final_output_file, upload_path, ott=self.ott)


            return final_output_file