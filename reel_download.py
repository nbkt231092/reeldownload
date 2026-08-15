import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import yt_dlp
import pandas as pd
import os
import whisper
import datetime
import time
import concurrent.futures
import json
import shutil
import sys
import torch

# Đảm bảo ffmpeg có sẵn cho Whisper
if not shutil.which("ffmpeg"):
    try:
        import imageio_ffmpeg
        ffmpeg_src = imageio_ffmpeg.get_ffmpeg_exe()
        if ffmpeg_src and os.path.exists(ffmpeg_src):
            local_ffmpeg = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffmpeg.exe")
            if not os.path.exists(local_ffmpeg):
                shutil.copy(ffmpeg_src, local_ffmpeg)
            os.environ["PATH"] += os.pathsep + os.path.dirname(os.path.abspath(__file__))
    except ImportError:
        pass

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("FB Reels Downloader - Ultimate Version")
        self.geometry("850x920")

        self.cookie_path = ctk.StringVar(value="Chưa chọn file cookie...")
        self.split_enabled = ctk.IntVar(value=0)
        self.split_base_dir = ctk.StringVar(value=os.path.abspath(os.path.dirname(__file__)))
        self.model = None

        self.label_title = ctk.CTkLabel(self, text="FB REELS AUTOMATION", font=("Roboto", 24, "bold"))
        self.label_title.pack(pady=10)

        # 1. Hộp chứa danh sách Link
        self.label_instruct = ctk.CTkLabel(self, text="Dán danh sách link Reels vào đây (Mỗi link 1 dòng) hoặc tải từ file:")
        self.label_instruct.pack()
        
        self.btn_load_links = ctk.CTkButton(self, text="Tải link từ file .txt", command=self.load_links_from_file)
        self.btn_load_links.pack(pady=(0, 5))

        self.textbox_urls = ctk.CTkTextbox(self, width=750, height=120)
        self.textbox_urls.pack(pady=5)

        # 2. Cấu hình Mạng & Xác thực (Proxy + Cookie)
        self.frame_network = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_network.pack(pady=10, fill="x", padx=50)

        self.label_proxy = ctk.CTkLabel(self.frame_network, text="Proxy (Tùy chọn):")
        self.label_proxy.grid(row=0, column=0, padx=5, sticky="e")
        self.entry_proxy = ctk.CTkEntry(self.frame_network, width=350, placeholder_text="VD: ip:port:user:password")
        self.entry_proxy.grid(row=0, column=1, padx=5, sticky="w")

        self.btn_cookie = ctk.CTkButton(self.frame_network, text="Chọn file cookies.txt", command=self.select_cookie, width=150)
        self.btn_cookie.grid(row=1, column=0, padx=5, pady=5, sticky="e")
        
        self.btn_profile = ctk.CTkButton(self.frame_network, text="Chọn thư mục Profile", command=self.select_profile_dir, width=150)
        self.btn_profile.grid(row=2, column=0, padx=5, pady=5, sticky="e")

        self.label_cookie = ctk.CTkLabel(self.frame_network, textvariable=self.cookie_path, font=("Iosevka", 10))
        self.label_cookie.grid(row=1, column=1, rowspan=2, padx=5, pady=5, sticky="w")

        self.label_threads = ctk.CTkLabel(self.frame_network, text="Số luồng (Threads):")
        self.label_threads.grid(row=3, column=0, padx=5, pady=5, sticky="e")
        self.entry_threads = ctk.CTkEntry(self.frame_network, width=100)
        self.entry_threads.grid(row=3, column=1, padx=5, pady=5, sticky="w")
        self.entry_threads.insert(0, "3")

        self.label_ua = ctk.CTkLabel(self.frame_network, text="User-Agent (GPM):")
        self.label_ua.grid(row=4, column=0, padx=5, pady=5, sticky="e")
        self.entry_ua = ctk.CTkEntry(self.frame_network, width=350, placeholder_text="Mặc định của yt-dlp nếu để trống")
        self.entry_ua.grid(row=4, column=1, padx=5, pady=5, sticky="w")

        # 2.5. Phân chia Thư mục
        self.frame_split = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_split.pack(pady=5, fill="x", padx=50)
        
        self.check_split = ctk.CTkCheckBox(self.frame_split, text="Bật chế độ tự động chia thư mục", variable=self.split_enabled, command=self.toggle_split_ui)
        self.check_split.grid(row=0, column=0, columnspan=3, padx=5, pady=5, sticky="w")
        
        self.label_base_dir = ctk.CTkLabel(self.frame_split, text="Thư mục gốc:")
        self.label_base_dir.grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.entry_base_dir = ctk.CTkEntry(self.frame_split, textvariable=self.split_base_dir, width=350, state="disabled")
        self.entry_base_dir.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        self.btn_base_dir = ctk.CTkButton(self.frame_split, text="Chọn", command=self.select_base_dir, width=60, state="disabled")
        self.btn_base_dir.grid(row=1, column=2, padx=5, pady=5, sticky="w")
        
        self.label_prefix = ctk.CTkLabel(self.frame_split, text="Tiền tố thư mục:")
        self.label_prefix.grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.entry_prefix = ctk.CTkEntry(self.frame_split, width=100)
        self.entry_prefix.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        self.entry_prefix.insert(0, "temp")
        self.entry_prefix.configure(state="disabled")

        self.label_start = ctk.CTkLabel(self.frame_split, text="Chỉ số bắt đầu:")
        self.label_start.grid(row=3, column=0, padx=5, pady=5, sticky="e")
        self.entry_start = ctk.CTkEntry(self.frame_split, width=100)
        self.entry_start.grid(row=3, column=1, padx=5, pady=5, sticky="w")
        self.entry_start.insert(0, "43")
        self.entry_start.configure(state="disabled")

        self.label_chunk = ctk.CTkLabel(self.frame_split, text="Số video / thư mục:")
        self.label_chunk.grid(row=4, column=0, padx=5, pady=5, sticky="e")
        self.entry_chunk = ctk.CTkEntry(self.frame_split, width=100)
        self.entry_chunk.grid(row=4, column=1, padx=5, pady=5, sticky="w")
        self.entry_chunk.insert(0, "11")
        self.entry_chunk.configure(state="disabled")

        # 3. Hộp Log
        self.log_box = ctk.CTkTextbox(self, width=750, height=200)
        self.log_box.pack(pady=10)

        # 4. Khung chứa các nút bấm chính
        self.frame_buttons = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_buttons.pack(pady=10)

        # Nút Tải Về
        self.btn_download = ctk.CTkButton(self.frame_buttons, text="TẢI VỀ & TẠO SUB", 
                                       command=lambda: self.start_process_thread("download"), 
                                       fg_color="green", hover_color="darkgreen", font=("Roboto", 14, "bold"), height=40)
        self.btn_download.grid(row=0, column=0, padx=15)

        # Nút Cập Nhật Data
        self.btn_update = ctk.CTkButton(self.frame_buttons, text="CẬP NHẬT DATA", 
                                        command=lambda: self.start_process_thread("update"), 
                                        fg_color="#cf8e13", hover_color="#a8720e", font=("Roboto", 14, "bold"), height=40)
        self.btn_update.grid(row=0, column=1, padx=15)

        self.btn_stop = ctk.CTkButton(self.frame_buttons, text="DỪNG LẠI", 
                                        command=self.stop_process, 
                                        fg_color="#c0392b", hover_color="#922b21", font=("Roboto", 14, "bold"), height=40, state="disabled")
        self.btn_stop.grid(row=0, column=2, padx=15)

        self.stop_event = threading.Event()

        self.config_file = "config.json"
        self.load_config()

    def toggle_split_ui(self):
        state = "normal" if self.split_enabled.get() == 1 else "disabled"
        self.btn_base_dir.configure(state=state)
        # Entry requires special handling for state
        self.entry_prefix.configure(state=state)
        self.entry_start.configure(state=state)
        self.entry_chunk.configure(state=state)

    def select_base_dir(self):
        path = filedialog.askdirectory(title="Chọn thư mục gốc để lưu")
        if path:
            self.split_base_dir.set(path)
            self.save_config()

    def stop_process(self):
        self.log("\n⚠️ Đang yêu cầu dừng... Các tiến trình đang tải/xử lý dở sẽ hoàn thành nốt, vui lòng đợi!")
        self.stop_event.set()
        self.btn_stop.configure(state="disabled")

    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    if "proxy" in config and config["proxy"]:
                        self.entry_proxy.insert(0, config["proxy"])
                    if "cookie" in config and config["cookie"] != "Chưa chọn file cookie...":
                        self.cookie_path.set(config["cookie"])
                    if "threads" in config:
                        self.entry_threads.delete(0, "end")
                        self.entry_threads.insert(0, str(config["threads"]))
                    if "user_agent" in config and config["user_agent"]:
                        self.entry_ua.insert(0, config["user_agent"])
                        
                    if "split_enabled" in config:
                        self.split_enabled.set(config["split_enabled"])
                        self.toggle_split_ui()
                    if "split_base_dir" in config and config["split_base_dir"]:
                        self.split_base_dir.set(config["split_base_dir"])
                    
                    # Temporarily enable entry to modify
                    self.entry_prefix.configure(state="normal")
                    self.entry_start.configure(state="normal")
                    self.entry_chunk.configure(state="normal")
                    
                    if "split_prefix" in config:
                        self.entry_prefix.delete(0, "end")
                        self.entry_prefix.insert(0, str(config["split_prefix"]))
                    if "split_start" in config:
                        self.entry_start.delete(0, "end")
                        self.entry_start.insert(0, str(config["split_start"]))
                    if "split_chunk" in config:
                        self.entry_chunk.delete(0, "end")
                        self.entry_chunk.insert(0, str(config["split_chunk"]))
                    
                    self.toggle_split_ui()
            except Exception as e:
                pass

    def save_config(self):
        try:
            config = {
                "proxy": self.entry_proxy.get().strip(),
                "cookie": self.cookie_path.get(),
                "threads": self.entry_threads.get().strip(),
                "user_agent": self.entry_ua.get().strip(),
                "split_enabled": self.split_enabled.get(),
                "split_base_dir": self.split_base_dir.get(),
                "split_prefix": self.entry_prefix.get().strip(),
                "split_start": self.entry_start.get().strip(),
                "split_chunk": self.entry_chunk.get().strip()
            }
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4)
        except Exception:
            pass

    def log(self, message):
        def _append():
            self.log_box.insert("end", f"{message}\n")
            self.log_box.see("end")
        self.after(0, _append)

    def select_cookie(self):
        path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        if path:
            self.cookie_path.set(path)
            self.save_config()
            
    def select_profile_dir(self):
        path = filedialog.askdirectory(title="Chọn thư mục Profile của GPM/Chrome")
        if path:
            self.cookie_path.set(path)
            self.save_config()

    def load_links_from_file(self):
        path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                    self.textbox_urls.delete("1.0", "end")
                    self.textbox_urls.insert("1.0", content)
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không thể đọc file: {e}")

    def format_timestamp(self, seconds):
        td = datetime.timedelta(seconds=seconds)
        total_seconds = int(td.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds_int = divmod(remainder, 60)
        milliseconds = int(td.microseconds / 1000)
        return f"{hours:02d}:{minutes:02d}:{seconds_int:02d},{milliseconds:03d}"

    def start_process_thread(self, mode):
        self.save_config()
        self.stop_event.clear()
        self.btn_download.configure(state="disabled")
        self.btn_update.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        threading.Thread(target=self.run_main_logic, args=(mode,), daemon=True).start()

    def run_main_logic(self, mode):
        raw_urls = self.textbox_urls.get("1.0", "end-1c").strip()
        proxy_val = self.entry_proxy.get().strip()
        user_agent_val = self.entry_ua.get().strip()
        cookie = self.cookie_path.get()
        
        try:
            num_threads = int(self.entry_threads.get().strip())
            if num_threads < 1:
                num_threads = 3
        except ValueError:
            num_threads = 3

        # Chuẩn bị danh sách Task và Data per folder
        folder_data_map = {}
        tasks = []

        is_split = self.split_enabled.get() == 1
        try:
            base_dir = self.split_base_dir.get().strip() if is_split else os.path.abspath('.')
            prefix = self.entry_prefix.get().strip() if is_split else 'fb_data'
            start_idx = int(self.entry_start.get().strip()) if is_split else 0
            chunk_size = int(self.entry_chunk.get().strip()) if is_split else len(url_list)
        except ValueError:
            self.log("❌ Lỗi: Cấu hình chia thư mục không hợp lệ (Phải là số nguyên). Dùng mặc định.")
            is_split = False
            base_dir = os.path.abspath('.')
            prefix = 'fb_data'
            start_idx = 0
            chunk_size = len(url_list)

        for i, url in enumerate(url_list):
            if is_split:
                group = i // chunk_size
                folder_name = f"{prefix}{start_idx + group}"
            else:
                folder_name = prefix

            folder_path = os.path.join(base_dir, folder_name)
            local_idx = (i % chunk_size) + 1
            tasks.append((url, folder_path, local_idx))

            if folder_path not in folder_data_map:
                if not os.path.exists(folder_path):
                    os.makedirs(folder_path)
                csv_p = os.path.join(folder_path, 'report.csv')
                existing_data = {}
                if os.path.exists(csv_p):
                    try:
                        df_old = pd.read_csv(csv_p)
                        for _, row in df_old.iterrows():
                            link = str(row.get('Link', '')).strip()
                            if link and link != 'nan':
                                existing_data[link] = row.to_dict()
                    except Exception as e:
                        self.log(f"⚠️ Không thể đọc file CSV cũ {csv_p}: {e}")
                
                folder_data_map[folder_path] = {
                    'csv_path': csv_p,
                    'existing_data': existing_data,
                    'data_list': [],
                    'csv_lock': threading.Lock()
                }

        # --- CẤU HÌNH YT-DLP ---
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'get_comments': True, 
        }
        
        if os.path.isfile(cookie):
            ydl_opts['cookiefile'] = cookie
            self.log(f"🍪 Đang dùng file cookies: {cookie}")
        elif os.path.isdir(cookie):
            # Chrome/GPM Chromium profile
            ydl_opts['cookiesfrombrowser'] = ('chrome', cookie, None, None)
            self.log(f"🍪 Đang dùng cookie từ thư mục Profile: {cookie}")

        # Tích hợp Proxy nếu người dùng có nhập
        if proxy_val:
            parts = proxy_val.split(':')
            if len(parts) == 4:
                ip, port, user, password = parts
                formatted_proxy = f"http://{user}:{password}@{ip}:{port}"
            else:
                formatted_proxy = proxy_val
            ydl_opts['proxy'] = formatted_proxy
            self.log(f"🌐 Đang sử dụng Proxy: {formatted_proxy}")

        if user_agent_val:
            ydl_opts['http_headers'] = {
                'User-Agent': user_agent_val,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9,vi;q=0.8'
            }
            self.log(f"🕵️ Đang sử dụng User-Agent: {user_agent_val[:50]}...")

        if mode == "download":
            ydl_opts.update({
                'format': 'best',
            })
            self.log(f"\n🚀 BẮT ĐẦU TẢI VỀ ({len(url_list)} link)")
        else:
            ydl_opts.update({
                'skip_download': True, 
            })
            self.log(f"\n🔄 BẮT ĐẦU CẬP NHẬT DATA ({len(url_list)} link)")

        try:
            if mode == "download" and self.model is None:
                self.log("Đang nạp AI Whisper vào bộ nhớ...")
                self.model = whisper.load_model("base")

            whisper_lock = threading.Lock()

            def process_video(url, folder_path, index):
                if self.stop_event.is_set():
                    return
                
                import glob
                video_base = os.path.join(folder_path, str(index))
                srt_file = os.path.join(folder_path, f"{index}.srt")
                
                f_data = folder_data_map[folder_path]
                existing_data = f_data['existing_data']
                csv_path = f_data['csv_path']
                data_list = f_data['data_list']
                csv_lock = f_data['csv_lock']
                
                # Bỏ qua nếu đã tải (Check trùng lặp)
                if mode == "download" and url in existing_data:
                    existing_files = glob.glob(f"{video_base}.*")
                    video_files = [f for f in existing_files if not f.endswith('.srt')]
                    if video_files:
                        self.log(f"⏭️ [{os.path.basename(folder_path)}] Bỏ qua Video {index}: Đã tải trước đó.")
                        with csv_lock:
                            data_list.append(existing_data[url])
                            pd.DataFrame(data_list).to_csv(csv_path, index=False, encoding='utf-8-sig')
                        return

                self.log(f"--------------------------------------")
                self.log(f"🎬 [{os.path.basename(folder_path)}] [Video {index}] Đang trích xuất dữ liệu...")
                
                thread_ydl_opts = ydl_opts.copy()
                thread_ydl_opts['outtmpl'] = {'default': f"{video_base}.%(ext)s"}

                try:
                    info = None
                    with yt_dlp.YoutubeDL(thread_ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=(mode == "download"))
                        
                    # FALLBACK: Nếu tải bằng Cookie thất bại, thử tải lại không dùng Cookie (Dành cho video Public)
                    if not info and ('cookiefile' in thread_ydl_opts or 'cookiesfrombrowser' in thread_ydl_opts):
                        self.log(f"   > ⚠️ Lỗi với Cookie. Đang thử tải lại không dùng Cookie (Public Mode)...")
                        fallback_opts = thread_ydl_opts.copy()
                        fallback_opts.pop('cookiefile', None)
                        fallback_opts.pop('cookiesfrombrowser', None)
                        fallback_opts.pop('http_headers', None)
                        with yt_dlp.YoutubeDL(fallback_opts) as ydl:
                            info = ydl.extract_info(url, download=(mode == "download"))

                    if not info:
                        self.log(f"   > ❌ Bỏ qua video này (Lỗi link/Bị ẩn/Bị chặn).")
                        if url in existing_data:
                            with csv_lock:
                                data_list.append(existing_data[url])
                                pd.DataFrame(data_list).to_csv(csv_path, index=False, encoding='utf-8-sig')
                        return
                        
                    # Trích xuất toàn bộ thông tin
                    title = info.get('title', f'Video_{index}')
                    caption = info.get('description', 'Không có caption')
                    duration = info.get('duration', 0)
                    
                    comments = info.get('comments', [])
                    first_comment = comments[0].get('text') if comments else "Không có comment"

                    view_count = info.get('view_count', 0)
                    like_count = info.get('like_count', 0)
                    comment_count = info.get('comment_count', 0)
                    share_count = info.get('repost_count', 0) 

                    sub_status = existing_data.get(url, {}).get('Subtitle AI', 'Chưa tạo')

                    # Chạy AI tạo Subtitle nếu ở chế độ Tải về
                    if mode == "download":
                        actual_video_file = None
                        try:
                            actual_video_file = ydl.prepare_filename(info)
                        except:
                            pass
                            
                        if not actual_video_file or not os.path.exists(actual_video_file):
                            vid_files = glob.glob(f"{video_base}.*")
                            vid_files = [f for f in vid_files if not f.endswith('.srt')]
                            if vid_files:
                                actual_video_file = vid_files[0]
                                
                        retry = 0
                        while actual_video_file and not os.path.exists(actual_video_file) and retry < 15:
                            time.sleep(1)
                            retry += 1

                        if actual_video_file and os.path.exists(actual_video_file):
                            if not os.path.exists(srt_file):
                                self.log(f"   > Đang AI Transcribe âm thanh...")
                                try:
                                    with whisper_lock:
                                        result = self.model.transcribe(actual_video_file, fp16=torch.cuda.is_available())
                                    with open(srt_file, "w", encoding="utf-8") as f:
                                        for i, segment in enumerate(result['segments'], start=1):
                                            start = self.format_timestamp(segment['start'])
                                            end = self.format_timestamp(segment['end'])
                                            f.write(f"{i}\n{start} --> {end}\n{segment['text'].strip()}\n\n")
                                    self.log(f"   > ✅ Tạo Sub thành công.")
                                    sub_status = "Thành công"
                                except Exception as e:
                                    self.log(f"   > ⚠️ Lỗi Whisper: {e}")
                                    sub_status = "Lỗi AI"
                            else:
                                self.log(f"   > Đã có sẵn Subtitle, bỏ qua AI.")
                                sub_status = "Đã có sẵn"
                        else:
                            sub_status = "Lỗi tải video"

                    # Lưu vào List
                    row_data = {
                        'STT': index,
                        'Tiêu đề': title,
                        'Caption': caption,
                        'Lượt View': view_count,
                        'Lượt Like': like_count,
                        'Tổng Comment': comment_count,
                        'Lượt Share': share_count,
                        'Comment đầu tiên': first_comment,
                        'Thời lượng (s)': duration,
                        'Link': url,
                        'Subtitle AI': sub_status
                    }
                    
                    with csv_lock:
                        data_list.append(row_data)
                        pd.DataFrame(data_list).to_csv(csv_path, index=False, encoding='utf-8-sig')

                    if mode == "update":
                        self.log(f"   > ✅ Đã cập nhật xong data cho video {index}.")

                except Exception as loop_err:
                     self.log(f"   > ❌ Lỗi: {loop_err}")

            with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
                futures = [executor.submit(process_video, url, fpath, l_idx) for url, fpath, l_idx in tasks]
                for future in concurrent.futures.as_completed(futures):
                    future.result()

            # Lưu file CSV & Báo cáo
            total_processed = sum(len(f_data['data_list']) for f_data in folder_data_map.values())
            if total_processed > 0:
                self.log(f"\n✅ HOÀN TẤT! Dữ liệu đã được lưu an toàn vào {len(folder_data_map)} thư mục.")
                self.after(0, lambda: messagebox.showinfo("Thành công", f"Đã xử lý xong tổng cộng {total_processed} video!"))
            else:
                self.log(f"\n⚠️ KHÔNG CÓ DỮ LIỆU ĐỂ LƯU!")
                self.log(f"Nguyên nhân: Link bị lỗi, nhập sai định dạng hoặc bị Facebook chặn.")
                self.after(0, lambda: messagebox.showwarning("Cảnh báo", "Không tạo được file CSV vì không có video nào tải/cập nhật thành công. Hãy thử dùng File Cookie hoặc Proxy."))

        except Exception as e:
            self.log(f"\n❌ Lỗi hệ thống: {str(e)}")
        
        self.enable_buttons()

    def enable_buttons(self):
        self.btn_download.configure(state="normal")
        self.btn_update.configure(state="normal")
        self.btn_stop.configure(state="disabled")

if __name__ == "__main__":
    app = App()
    app.mainloop()