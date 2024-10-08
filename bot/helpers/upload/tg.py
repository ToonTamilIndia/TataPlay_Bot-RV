import os
import time
import threading
from bot.helpers.utils import humanbytes, get_duration, get_thumbnail, progress_for_pyrogram

class tgUploader:
    def __init__(self, app, msg):
        self.app = app
        self.msg = msg
        self.upload_semaphore = threading.Semaphore(3)  # Limit to 3 parallel uploads

    def upload_file(self, file_path):
        def upload_task(file_path):
            try:
                file_name = os.path.basename(file_path)  
                duration = get_duration(file_name)
                thumb = get_thumbnail(file_name, "", duration / 2)

                file_size = humanbytes(os.stat(file_path).st_size)

                caption = '''<code>{}</code>'''.format(file_name)

                progress_args_text = "<code>[+]</code> <b>{}</b>\n<code>{}</code>".format("Uploading", file_name)

                self.app.send_video(
                    video=file_path, 
                    chat_id=self.msg.chat.id, 
                    caption=caption, 
                    progress=progress_for_pyrogram, 
                    progress_args=(
                            progress_args_text,
                            self.msg, 
                            time.time()
                    ), thumb=thumb, duration=duration, width=1280, height=720
                )
                os.remove(file_path)
                os.remove(thumb)
                self.msg.delete()
            except Exception as e:
                print(e)
                self.msg.edit(f"`{e}`")
            finally:
                self.upload_semaphore.release()  # Release the semaphore after finishing

        self.upload_semaphore.acquire()  # Acquire the semaphore before starting the upload
        threading.Thread(target=upload_task, args=(file_path,)).start()  # Start a new thread for the upload

