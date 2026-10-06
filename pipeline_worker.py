from PyQt6.QtCore import QThread, pyqtSignal
from datetime import datetime
import multiprocessing
import sys
import os
import re
import tempfile
import time
import shutil
import subprocess
import urllib.parse
import requests
from bs4 import BeautifulSoup
import libtorrent as lt
import login
import ctypes

def create_hardlink_safe(src, dst):
    try:
        os.link(src, dst)
        print(f"[STAGING] Hardlink created: {dst}")
        return True
    except (OSError, NotImplementedError) as e:
        print(f"[STAGING] Hardlink failed ({e}), will use copy as fallback")
        return False

def hide_directory_as_system(path):
    try:
        ctypes.windll.kernel32.SetFileAttributesW(path, 0x04 | 0x02)
        return True
    except Exception as e:
        return False

def _torrent_process_target(
    file_input, 
    settings, 
    create_sheets, 
    mode, 
    additional_assets, 
    queue,
    main_category=None,
    sub_categories=None,
    torrent_title="",
    torrent_descr="",
    pictures=None
):
    # --- Redirect Subprocess Print Statements to the Existing Log ---
    log_filepath = settings.get("log_filepath")
    if log_filepath:
        class SubprocessTee:
            def __init__(self, filepath):
                self.terminal = sys.stdout
                self.log = open(filepath, "a", encoding="utf-8")  # Append mode

            def write(self, message):
                if self.terminal:
                    try:
                        self.terminal.write(message)
                        self.terminal.flush()
                    except Exception:
                        pass
                self.log.write(message)
                self.log.flush()

            def flush(self):
                if self.terminal:
                    try:
                        self.terminal.flush()
                    except Exception:
                        pass
                self.log.flush()

        sys.stdout = SubprocessTee(log_filepath)
        sys.stderr = sys.stdout  # Also captures error tracebacks

    staging_dir = None
    try:
        if create_sheets:
            t_range = (50, 75)
            p_range = (76, 85)
            u_range = (86, 95)
            s_range = (96, 100)
        else:
            t_range = (0, 70)
            p_range = (71, 80)
            u_range = (81, 90)
            s_range = (91, 100)

        queue.put(('progress', int(t_range[0]), "Creating torrent with libtorrent..."))

        fs = lt.file_storage()
        
        if mode == "folder":
            if isinstance(file_input, (list, tuple)):
                target_path = os.path.abspath(file_input[0])
            else:
                target_path = os.path.abspath(str(file_input))
                
            print(f"[LIBTORRENT] Target path: {target_path}")
                
            if os.path.isfile(target_path):
                all_sources = [target_path] + [os.path.abspath(p) for p in additional_assets if os.path.isfile(p)]
                print(f"[LIBTORRENT] Target is a single file with additional assets. Total sources: {len(all_sources)}")
                if len(all_sources) == 1:
                    lt.add_files(fs, target_path)
                    parent_dir = os.path.dirname(target_path)
                else:
                    try:
                        common_base = os.path.commonpath(all_sources)
                    except ValueError:
                        common_base = os.path.dirname(all_sources[0])

                    staging_dir = os.path.join(common_base, f".qtm_staging_{int(time.time())}")
                    os.makedirs(staging_dir, exist_ok=True)
                    hide_directory_as_system(staging_dir)
                    queue.put(('staging_dir', staging_dir))
                    print(f"[LIBTORRENT] Created staging directory: {staging_dir}")

                    root_folder_name = os.path.basename(common_base) or "Torrent_Files"
                    root_folder_path = os.path.join(staging_dir, root_folder_name)
                    os.makedirs(root_folder_path, exist_ok=True)

                    for abs_path in all_sources:
                        try:
                            rel_path = os.path.relpath(abs_path, common_base)
                            if rel_path.startswith(".."):
                                rel_path = os.path.basename(abs_path)
                        except ValueError:
                            rel_path = os.path.basename(abs_path)

                        dest_path = os.path.join(root_folder_path, rel_path)
                        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                        
                        if not os.path.exists(dest_path):
                            if not create_hardlink_safe(abs_path, dest_path):
                                print(f"[STAGING] Copying file: {abs_path} -> {dest_path}")
                                shutil.copy2(abs_path, dest_path)

                    lt.add_files(fs, root_folder_path)
                    if fs.num_files() == 0:
                        raise Exception("No valid files could be added to libtorrent storage.")
                    parent_dir = staging_dir
            elif os.path.isdir(target_path):
                print(f"[LIBTORRENT] Adding directory structure: {target_path}")
                lt.add_files(fs, target_path)
                if fs.num_files() == 0:
                    raise Exception("The selected folder is empty!")
                parent_dir = os.path.dirname(target_path)
            else:
                raise Exception(f"Path is neither a valid file nor directory: {target_path}")

            t = lt.create_torrent(fs, 0, lt.create_torrent.v1_only)
            t.set_priv(True)

        elif mode == "files":
            input_paths = [os.path.abspath(p) for p in file_input if os.path.isfile(p)]
            asset_paths = [os.path.abspath(p) for p in additional_assets if os.path.isfile(p)]
            all_valid_paths = input_paths + asset_paths

            print(f"[LIBTORRENT] Files mode: {len(input_paths)} input + {len(asset_paths)} assets")
            
            if not all_valid_paths:
                raise Exception("No valid files found to add.")

            if len(all_valid_paths) == 1:
                lt.add_files(fs, all_valid_paths[0])
                parent_dir = os.path.dirname(all_valid_paths[0])
            else:
                try:
                    common_base = os.path.commonpath(all_valid_paths)
                except ValueError:
                    common_base = os.path.dirname(all_valid_paths[0])

                staging_dir = os.path.join(common_base, f".qtm_staging_{int(time.time())}")
                os.makedirs(staging_dir, exist_ok=True)
                hide_directory_as_system(staging_dir)
                queue.put(('staging_dir', staging_dir))
                print(f"[LIBTORRENT] Created staging directory inside common_base: {staging_dir}")

                root_folder_name = os.path.basename(common_base) or "Torrent_Files"
                root_folder_path = os.path.join(staging_dir, root_folder_name)
                os.makedirs(root_folder_path, exist_ok=True)

                for abs_path in all_valid_paths:
                    try:
                        rel_path = os.path.relpath(abs_path, common_base)
                        if rel_path.startswith(".."):
                            rel_path = os.path.basename(abs_path)
                    except ValueError:
                        rel_path = os.path.basename(abs_path)

                    dest_path = os.path.join(root_folder_path, rel_path)
                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                    
                    if not os.path.exists(dest_path):
                        if not create_hardlink_safe(abs_path, dest_path):
                            print(f"[STAGING] Copying file: {abs_path} -> {dest_path}")
                            shutil.copy2(abs_path, dest_path)

                lt.add_files(fs, root_folder_path)
                if fs.num_files() == 0:
                    raise Exception("No valid files added to torrent from staging directory.")
                
                parent_dir = staging_dir
            
            t = lt.create_torrent(fs, 0, lt.create_torrent.v1_only)
            t.set_priv(True)
        
        else:
            raise Exception(f"Unknown mode: {mode}")

        trackers = settings.get("trackers", ["http://gaytor.rent:2710/announce"])
        for tracker in trackers:
            t.add_tracker(str(tracker))

        t.set_creator("GayTorrent Uploader")

        queue.put(('progress', int(t_range[0]), "Hashing pieces via libtorrent..."))
        total_pieces = t.num_pieces()
        print(f"[LIBTORRENT] Total pieces to hash: {total_pieces}")
        
        def hashing_progress_callback(piece_index):
            if total_pieces > 0:
                span = t_range[1] - t_range[0]
                current_pct = t_range[0] + int(span * (piece_index / total_pieces))
                queue.put(('progress', current_pct, f"Hashing pieces ({piece_index}/{total_pieces})..."))

        lt.set_piece_hashes(t, str(parent_dir), hashing_progress_callback)
        print("[LIBTORRENT] Piece hashing completed successfully.")

        torrent_entry = t.generate()
        torrent_data = lt.bencode(torrent_entry)

        # --- CLEAN TITLE & SET OUTPUT FILE ---
        if torrent_title:
            cleaned = re.sub(r'[,!_<>:"/\\|?*\']', '', str(torrent_title))
            torrent_title_cleaned = re.sub(r'\s+', ' ', cleaned).strip().lower()
        else:
            torrent_title_cleaned = "TORRENT UPLOAD TEST TITLE"
        
        torrent_filename = f"gtupl_{torrent_title_cleaned}.torrent"
        output_file = os.path.join(tempfile.gettempdir(), torrent_filename)
        
        with open(output_file, "wb") as f:
            f.write(torrent_data)
        
        queue.put(('output_file', output_file))
        queue.put(('progress', int(t_range[1]), "Torrent creation complete."))
        time.sleep(3.0)

        # --- UPLOAD WORKFLOW ---
        queue.put(('progress', int(p_range[0]), "Connecting and fetching CSRF token..."))
        session = requests.Session()
        
        cookie_dict = {}
        try:
            session_data = login.get_stored_session()
            if session_data and "cookies" in session_data:
                for cookie in session_data["cookies"]:
                    if "name" in cookie and "value" in cookie:
                        cookie_dict[cookie["name"]] = cookie["value"]
        except Exception as e:
            print(f"[ERROR] Could not fetch session from Keyring: {e}")

        if not cookie_dict:
            cookie_dict = settings.get("cookies", {})

        session.cookies.update(cookie_dict)
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:157.0) Gecko/20100101 Firefox/157.0",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Referer": "https://www.gaytor.rent/doupload.php",
            "Origin": "https://www.gaytor.rent"
        })

        try:
            print("[UPLOAD] Sending GET request to https://www.gaytor.rent/doupload.php")
            page_resp = session.get("https://www.gaytor.rent/doupload.php", timeout=30)
            print(f"[UPLOAD] Upload page HTTP status: {page_resp.status_code}")
            
            soup = BeautifulSoup(page_resp.text, "html.parser")
            token_meta = soup.find("meta", {"name": "csrf-token"}) or soup.find("input", {"name": "csrf-token"})
            
            if token_meta:
                csrf_token = token_meta.get("content") or token_meta.get("value")
            else:
                match = re.search(r'["\']x-csrf-token["\']\s*:\s*["\']([a-f0-9]{64})["\']', page_resp.text)
                csrf_token = match.group(1) if match else None

            if csrf_token:
                session.headers.update({"x-csrf-token": csrf_token})
            else:
                csrf_token = page_resp.headers.get("x-csrf-token")
                if csrf_token:
                    session.headers.update({"x-csrf-token": csrf_token})
                else:
                    print("[ERROR] Could not find CSRF token")
        except Exception as e:
            print(f"[ENDPOINT ERROR] Error fetching CSRF token: {e}")

        queue.put(('progress', int(p_range[0]), "Uploading pictures..."))
        pid_list = []
        file_tuples = []
        opened_files = []
        
        try:
            pic_sources = pictures if pictures else additional_assets
            print(f"[UPLOAD] Preparing pictures for upload. Total sources identified: {len(pic_sources)}")
            for pic in pic_sources:
                if pic and os.path.exists(pic):
                    f = open(pic, "rb")
                    opened_files.append(f)
                    file_tuples.append(("ulpic[]", (os.path.basename(pic), f, "image/jpeg")))
                    print(f"[UPLOAD] Added picture file: {pic}")
            
            if file_tuples:
                resp = session.post("https://www.gaytor.rent/api/v1/uploads/pics", files=file_tuples, timeout=60)
                print(f"[UPLOAD] Picture upload HTTP status code: {resp.status_code}")
                data = resp.json()
                
                if data.get("ok") and "data" in data:
                    for p in data["data"].get("pics", []):
                        pid = str(p.get("id"))
                        if pid and pid not in pid_list:
                            pid_list.append(pid)
        finally:
            for f in opened_files:
                f.close()

        queue.put(('progress', int(u_range[0]), "Uploading torrent file and metadata..."))
        
        sub_list = sub_categories or []
        files_payload = {
            "MAX_FILE_SIZE": (None, "75000000"),
            "type": (None, str(main_category) if main_category is not None else "62"),
            "scat1": (None, str(sub_list[0]) if len(sub_list) > 0 else "0"),
            "scat2": (None, str(sub_list[1]) if len(sub_list) > 1 else "0"),
            "scat3": (None, str(sub_list[2]) if len(sub_list) > 2 else "0"),
            "scat4": (None, str(sub_list[3]) if len(sub_list) > 3 else "0"),
            "name": (None, str(torrent_title) if torrent_title else "TORRENT UPLOAD TEST TITLE"),
            "descr": (None, str(torrent_descr) if torrent_descr else "TORRENT UPLOAD TEST DESCRIPTION"),
            "infourl": (None, "")
        }
        
        for pid in pid_list:
            files_payload[f"uplpic{pid}"] = (None, pid)

        print(f"[PAYLOAD] Prepared torrent metadata payload. Title: '{files_payload['name'][1]}', Main Category: {files_payload['type'][1]}")

        with open(output_file, "rb") as tf:
            files_payload["file"] = (os.path.basename(output_file), tf, "application/x-bittorrent")
            api_url = "https://www.gaytor.rent/api/v1/torrents"
            print(f"[UPLOAD] Sending final torrent data submission to API...")
            response = session.post(api_url, files=files_payload, timeout=60)
            
            print(f"[UPLOAD] Torrent submission HTTP response status: {response.status_code}")

            resp_data = {}
            try:
                resp_data = response.json()
            except Exception:
                pass
            
            if response.status_code != 200 or (resp_data and not resp_data.get("ok", True) and "error" in resp_data):
                error_msg = f"Upload failed with status {response.status_code}: {response.text}"
                print(f"[ERROR] {error_msg}")
                raise Exception(error_msg)
            
            torrent_info = resp_data.get("data", {})
            torrent_id = resp_data.get("id") or torrent_info.get("id")
            redirect_url = resp_data.get("redirect") or torrent_info.get("redirect", "")
            
            encrypted_id = None
            if "id=" in str(redirect_url):
                try:
                    encrypted_id = str(redirect_url).split("id=")[1].split("&")[0]
                except Exception:
                    pass

            print(f"[UPLOAD] UPLOAD SUCCESS! Torrent ID: {torrent_id}, Details Page: {redirect_url}")

        # --- AUTOMATIC SEEDING WORKFLOW ---
        if settings.get("save_seeding", False) and encrypted_id:
            queue.put(('progress', int(s_range[0]), "Waiting for torrent to register on server..."))
            time.sleep(15.0)
            
            queue.put(('progress', int(s_range[0]), "Downloading torrent file for seeding..."))
            try:
                download_url = f"https://www.gaytor.rent/download.php?id={encrypted_id}"
                print(f"[AUTOSEED] Requesting generated torrent file download from: {download_url}")
                
                dl_resp = session.get(download_url, timeout=30)
                print(f"[AUTOSEED] Download response HTTP status: {dl_resp.status_code}")
                
                program_dir = os.path.dirname(os.path.abspath(__file__))
                torrents_dir = os.path.join(program_dir, "downloaded_torrents")
                os.makedirs(torrents_dir, exist_ok=True)
                
                if dl_resp.status_code == 200:
                    seeded_torrent_path = os.path.join(torrents_dir, f"gtupl_{torrent_title_cleaned}.torrent")
                    with open(seeded_torrent_path, "wb") as f_dl:
                        f_dl.write(dl_resp.content)
                    print(f"[AUTOSEED] Successfully saved downloaded torrent file to: {seeded_torrent_path}")
                    
                    client_path = settings.get("torrent_client_path", "")
                    client_name = settings.get("torrent_client", "")
                    
                    if client_path and client_path != "WebUI" and os.path.exists(client_path):
                        if mode == "folder":
                            if isinstance(file_input, (list, tuple)):
                                target_path = os.path.abspath(file_input[0])
                            else:
                                target_path = os.path.abspath(str(file_input))
                            
                            if os.path.isfile(target_path):
                                save_path = os.path.dirname(target_path)
                            else:
                                save_path = os.path.dirname(target_path)
                        elif mode == "files":
                            input_paths = [os.path.abspath(p) for p in file_input if os.path.isfile(p)]
                            if len(input_paths) == 1:
                                save_path = os.path.dirname(input_paths[0])
                            else:
                                try:
                                    common_base = os.path.commonpath(input_paths)
                                    save_path = os.path.dirname(common_base)
                                except ValueError:
                                    save_path = os.path.dirname(input_paths[0])
                        else:
                            save_path = os.path.abspath(str(file_input))
                            if os.path.isfile(save_path):
                                save_path = os.path.dirname(save_path)
                            else:
                                save_path = os.path.dirname(save_path)

                        cmd = [
                            client_path,
                            "--skip-dialog=true",
                            f"--save-path={save_path}",
                            "--seed-mode",
                            seeded_torrent_path
                        ]
                        
                        queue.put(('progress', int(s_range[0]), f"Launching {client_name} for seeding..."))
                        subprocess.Popen(cmd)
                        time.sleep(1.0)
                else:
                    print(f"[ERROR] Failed to download torrent file for seeding: HTTP {dl_resp.status_code}")
            except Exception as e_seed:
                print(f"[ERROR] Error starting automatic seeding: {e_seed}")

        queue.put(('progress', int(s_range[0]), "Upload complete! Configuring cleanup..."))
        print("[CLEANUP] Pipeline completed successfully. Dispatching finished state")
        queue.put(('finished', True, {
            "output_file": output_file,
            "redirect": redirect_url
        }))

    except Exception as e:
        import traceback
        err_trace = traceback.format_exc()
        print(f"\n[ERROR] Pipeline failed with exception:\n{err_trace}")
        queue.put(('finished', False, str(e)))
    finally:
        if 'output_file' in locals() and output_file and os.path.exists(output_file):
            try:
                os.remove(output_file)
            except Exception as e_del:
                pass

        if staging_dir and os.path.exists(staging_dir):
            shutil.rmtree(staging_dir, ignore_errors=True)

class TorrentPipelineWorker(QThread):
    progress_signal = pyqtSignal(int, str)
    finished_signal = pyqtSignal(bool, object)
    history_signal = pyqtSignal(str, str, str, str)

    def __init__(
        self, 
        file_input, 
        settings, 
        create_sheets: bool, 
        mode: str = "folder", 
        additional_assets: list = None,
        main_category=None,
        sub_categories=None,
        torrent_title="",
        torrent_descr="",
        pictures=None
    ):
        super().__init__()
        self.file_input = file_input
        self.mode = mode
        self.settings = settings
        self.create_sheets = create_sheets
        self.additional_assets = additional_assets or []
        self.main_category = main_category
        self.sub_categories = sub_categories or []
        self.torrent_title = torrent_title or "Untitled Torrent"
        self.torrent_descr = torrent_descr
        self.pictures = pictures or []
        self.queue = multiprocessing.Queue()
        self.process = None
        self.temp_torrent_path = None
        self.start_time_str = None
        self.is_canceled = False
        self.staging_dir = None
        self.output_file = None

    def run(self):
        self.start_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.process = multiprocessing.Process(
            target=_torrent_process_target,
            args=(
                self.file_input,
                self.settings,
                self.create_sheets,
                self.mode,
                self.additional_assets,
                self.queue,
                self.main_category,
                self.sub_categories,
                self.torrent_title,
                self.torrent_descr,
                self.pictures
            )
        )
        self.process.start()

        while self.process.is_alive():
            try:
                while not self.queue.empty():
                    msg = self.queue.get_nowait()
                    if msg[0] == 'staging_dir':
                        self.staging_dir = msg[1]
                    elif msg[0] == 'output_file':  # ---> ADD THIS BLOCK <---
                        self.output_file = msg[1]
                    elif msg[0] == 'progress' and not self.is_canceled:
                        self.progress_signal.emit(msg[1], msg[2])
                    elif msg[0] == 'finished':
                        success, data = msg[1], msg[2]
                        redirect_url = ""
                        if success:
                            self.temp_torrent_path = data.get("output_file") if isinstance(data, dict) else data
                            self.torrent_result = data
                            if isinstance(data, dict):
                                redirect_url = data.get("redirect", "")
                        
                        status = "success" if success else "failed"
                        if not self.is_canceled:
                            self.history_signal.emit(self.start_time_str, self.torrent_title, status, redirect_url)
                        self.finished_signal.emit(success, data)
            except Exception as q_err:
                pass
            time.sleep(0.05)

        try:
            while not self.queue.empty():
                msg = self.queue.get_nowait()
                if msg[0] == 'staging_dir':
                    self.staging_dir = msg[1]
                elif msg[0] == 'progress' and not self.is_canceled:
                    self.progress_signal.emit(msg[1], msg[2])
                elif msg[0] == 'finished':
                    success, data = msg[1], msg[2]
                    redirect_url = ""
                    if success:
                        self.temp_torrent_path = data.get("output_file") if isinstance(data, dict) else data
                        self.torrent_result = data
                        if isinstance(data, dict):
                            redirect_url = data.get("redirect", "")
                    
                    status = "success" if status else "failed"
                    if not self.is_canceled:
                        self.history_signal.emit(self.start_time_str, self.torrent_title, status, redirect_url)
                    self.finished_signal.emit(success, data)
        except Exception as q_err:
            pass

    def cancel(self):
        print("[WORKER] Cancel command issued to worker thread.")
        self.is_canceled = True
        if self.process and self.process.is_alive():
            print(f"[WORKER] Terminating active multiprocessing process PID: {self.process.pid}")
            self.process.terminate()
            self.process.join()
        
        while not self.queue.empty():
            try:
                msg = self.queue.get_nowait()
                if msg[0] == 'staging_dir':
                    self.staging_dir = msg[1]
            except Exception:
                break

        if self.staging_dir and os.path.exists(self.staging_dir):
            try:
                shutil.rmtree(self.staging_dir, ignore_errors=True)
                print(f"[CLEANUP] Successfully removed staging directory: {self.staging_dir}")
            except Exception as e:
                print(f"[ERROR] Failed to remove staging directory: {e}")
        
        if self.output_file and os.path.exists(self.output_file):
            try:
                os.remove(self.output_file)
                print(f"[CLEANUP] Successfully removed temporary torrent file: {self.output_file}")
            except Exception as e:
                print(f"[ERROR] Failed to remove temporary torrent file: {e}")

        self.progress_signal.emit(0, "Cancelled")
        
        if self.start_time_str:
            self.history_signal.emit(self.start_time_str, self.torrent_title, "canceled", "")

        print("[WORKER] Worker finished signal emitted following cancellation.")
        self.finished_signal.emit(False, {"status": "canceled"})