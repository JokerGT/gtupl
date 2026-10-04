from PyQt6.QtCore import QThread, pyqtSignal
import multiprocessing
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
    """Target function running in a separate multiprocessing.Process to bypass the GIL."""
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
                
            if os.path.isfile(target_path):
                all_sources = [target_path] + [os.path.abspath(p) for p in additional_assets if os.path.isfile(p)]
                if len(all_sources) == 1:
                    lt.add_files(fs, target_path)
                    parent_dir = os.path.dirname(target_path)
                else:
                    staging_dir = tempfile.mkdtemp(prefix="qtm_staging_")
                    common_base = os.path.dirname(target_path)
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
                            shutil.copy2(abs_path, dest_path)

                    time.sleep(2.0)
                    lt.add_files(fs, root_folder_path)
                    if fs.num_files() == 0:
                        raise Exception("No valid files could be added to libtorrent storage.")
                    parent_dir = staging_dir
            elif os.path.isdir(target_path):
                lt.add_files(fs, target_path)
                if fs.num_files() == 0:
                    raise Exception("The selected folder is empty!")
                parent_dir = os.path.dirname(target_path)
            else:
                raise Exception(f"Path is neither a valid file nor directory: {target_path}")

            t = lt.create_torrent(fs)
            t.set_priv(True)

        elif mode == "files":
            input_paths = [os.path.abspath(p) for p in file_input if os.path.isfile(p)]
            asset_paths = [os.path.abspath(p) for p in additional_assets if os.path.isfile(p)]
            all_valid_paths = input_paths + asset_paths

            if not all_valid_paths:
                raise Exception("No valid files found to add.")

            staging_dir = tempfile.mkdtemp(prefix="qtm_staging_")

            if len(all_valid_paths) == 1:
                target_path = all_valid_paths[0]
                lt.add_files(fs, target_path)
                parent_dir = os.path.dirname(target_path)
            else:
                try:
                    common_base = os.path.commonpath(all_valid_paths)
                except ValueError:
                    common_base = ""

                if not common_base or common_base == os.path.dirname(common_base):
                    common_base = os.path.dirname(all_valid_paths[0])

                root_folder_name = os.path.basename(common_base)
                if not root_folder_name or root_folder_name in ("", ".", "..", "C:", "D:"):
                    root_folder_name = "Torrent_Files"

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
                        shutil.copy2(abs_path, dest_path)

                time.sleep(2.0)
                lt.add_files(fs, root_folder_path)
                if fs.num_files() == 0:
                    raise Exception("No valid files could be added to libtorrent storage from staging directory.")

                parent_dir = staging_dir
            
            t = lt.create_torrent(fs)
            t.set_priv(True)
        
        else:
            raise Exception(f"Unknown mode: {mode}")

        trackers = settings.get("trackers", ["http://gaytor.rent:2710/announce"])
        for tracker in trackers:
            t.add_tracker(str(tracker))

        t.set_creator("GayTorrent Uploader")

        queue.put(('progress', int(t_range[0]), "Hashing pieces via libtorrent..."))
        total_pieces = t.num_pieces()
        
        def hashing_progress_callback(piece_index):
            if total_pieces > 0:
                span = t_range[1] - t_range[0]
                current_pct = t_range[0] + int(span * (piece_index / total_pieces))
                queue.put(('progress', current_pct, f"Hashing pieces ({piece_index}/{total_pieces})..."))

        lt.set_piece_hashes(t, str(parent_dir), hashing_progress_callback)

        torrent_entry = t.generate()
        torrent_data = lt.bencode(torrent_entry)

        output_file = os.path.join(tempfile.gettempdir(), "temp_upload.torrent")
        with open(output_file, "wb") as f:
            f.write(torrent_data)

        queue.put(('progress', int(t_range[1]), "Torrent creation complete."))

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
            print(f"Warning fetching session cookies from keyring: {e}")

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
            page_resp = session.get("https://www.gaytor.rent/doupload.php", timeout=30)
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
        except Exception as e:
            print(f"Warning fetching CSRF token: {e}")

        queue.put(('progress', int(p_range[0]), "Uploading pictures..."))
        pid_list = []
        file_tuples = []
        opened_files = []
        
        try:
            pic_sources = pictures if pictures else additional_assets
            for pic in pic_sources:
                if pic and os.path.exists(pic):
                    f = open(pic, "rb")
                    opened_files.append(f)
                    file_tuples.append(("ulpic[]", (os.path.basename(pic), f, "image/jpeg")))
            
            if file_tuples:
                resp = session.post("https://www.gaytor.rent/api/v1/uploads/pics", files=file_tuples, timeout=60)
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

        with open(output_file, "rb") as tf:
            files_payload["file"] = (os.path.basename(output_file), tf, "application/x-bittorrent")
            api_url = "https://www.gaytor.rent/api/v1/torrents"
            response = session.post(api_url, files=files_payload, timeout=60)
            
            resp_data = {}
            try:
                resp_data = response.json()
            except Exception:
                pass
            
            if response.status_code != 200 or (resp_data and not resp_data.get("ok", True) and "error" in resp_data):
                raise Exception(f"Upload failed with status {response.status_code}: {response.text}")
            
            torrent_info = resp_data.get("data", {})
            torrent_id = resp_data.get("id") or torrent_info.get("id")
            redirect_url = resp_data.get("redirect") or torrent_info.get("redirect", "")
            
            # Extract encrypted_id cleanly from redirect URL
            encrypted_id = None
            if "id=" in str(redirect_url):
                try:
                    encrypted_id = str(redirect_url).split("id=")[1].split("&")[0]
                except Exception:
                    pass

            print(f"Successfully uploaded! Torrent ID: {torrent_id}, Redirect: {redirect_url}")
            print(f"[Seeding Debug] Captured encrypted_id: {encrypted_id}")

        # --- AUTOMATIC SEEDING WORKFLOW ---
        if settings.get("save_seeding", False) and encrypted_id:
            queue.put(('progress', int(s_range[0]), "Waiting for torrent to register on server..."))
            time.sleep(2.0)  # Give the server a moment to index the upload
            
            queue.put(('progress', int(s_range[0]), "Downloading torrent file for seeding..."))
            try:
                download_url = f"https://www.gaytor.rent/download.php?id={encrypted_id}"
                print(f"[Seeding Debug] Downloading from: {download_url}")
                
                dl_resp = session.get(download_url, timeout=30)
                print(f"[Seeding Debug] Download HTTP Status: {dl_resp.status_code}")
                
                program_dir = os.path.dirname(os.path.abspath(__file__))
                torrents_dir = os.path.join(program_dir, "downloaded_torrents")
                os.makedirs(torrents_dir, exist_ok=True)
                
                if dl_resp.status_code == 200:
                    seeded_torrent_path = os.path.join(torrents_dir, f"{encrypted_id}.torrent")
                    with open(seeded_torrent_path, "wb") as f_dl:
                        f_dl.write(dl_resp.content)
                    print(f"[Seeding Debug] Successfully saved torrent to {seeded_torrent_path}")
                    
                    client_path = settings.get("torrent_client_path", "")
                    client_name = settings.get("torrent_client", "")
                    
                    if client_path and client_path != "WebUI" and os.path.exists(client_path):
                        # Determine save_path based on mode and structure
                        if mode == "folder":
                            if isinstance(file_input, (list, tuple)):
                                target_path = os.path.abspath(file_input[0])
                            else:
                                target_path = os.path.abspath(str(file_input))
                            
                            if os.path.isfile(target_path):
                                save_path = os.path.dirname(target_path)
                            else:
                                # Folder mode: save path must be one level above the target folder (parent directory)
                                save_path = os.path.dirname(target_path)
                        elif mode == "files":
                            input_paths = [os.path.abspath(p) for p in file_input if os.path.isfile(p)]
                            if len(input_paths) == 1:
                                save_path = os.path.dirname(input_paths[0])
                            else:
                                # Multiple files packaged into a root folder staging directory
                                try:
                                    common_base = os.path.commonpath(input_paths)
                                    save_path = os.path.dirname(common_base)
                                except ValueError:
                                    save_path = os.path.dirname(input_paths[0])
                        else:
                            save_path = os.path.abspath(str(file_input))
                            if os.path.isfile(save_path):
                                save_path = os.path.dirname(save_path)

                        cmd = [
                            client_path,
                            "--skip-dialog=true",
                            f"--save-path={save_path}",
                            "--seed-mode",
                            seeded_torrent_path
                        ]
                        
                        print(f"[Seeding Debug] Launching client with save_path: {save_path}")
                        queue.put(('progress', int(s_range[0]), f"Launching {client_name} for seeding..."))
                        
                        # Use subprocess.run with a non-blocking timeout or keep process alive a moment longer
                        subprocess.Popen(cmd)
                        time.sleep(1.0) # Give Windows window manager time to spawn the GUI process
                else:
                    print(f"Failed to download torrent file for seeding: HTTP {dl_resp.status_code}")
            except Exception as e_seed:
                print(f"Error starting automatic seeding: {e_seed}")
        else:
            print("[Seeding Debug] Automatic seeding skipped (save_seeding is disabled or encrypted_id is missing).")

        queue.put(('progress', int(s_range[0]), "Upload complete! Configuring cleanup..."))
        queue.put(('finished', True, {
            "output_file": output_file,
            "torrent_id": torrent_id,
            "encrypted_id": encrypted_id,
            "redirect": redirect_url
        }))

    except Exception as e:
        import traceback
        print(f"Pipeline error traceback:\n{traceback.format_exc()}")
        queue.put(('finished', False, str(e)))
    finally:
        if staging_dir and os.path.exists(staging_dir):
            shutil.rmtree(staging_dir, ignore_errors=True)

class TorrentPipelineWorker(QThread):
    progress_signal = pyqtSignal(int, str)
    finished_signal = pyqtSignal(bool, object)

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
        self.torrent_title = torrent_title
        self.torrent_descr = torrent_descr
        self.pictures = pictures or []
        self.queue = multiprocessing.Queue()
        self.process = None
        self.temp_torrent_path = None

    def run(self):
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
                    if msg[0] == 'progress':
                        self.progress_signal.emit(msg[1], msg[2])
                    elif msg[0] == 'finished':
                        success, data = msg[1], msg[2]
                        if success:
                            self.temp_torrent_path = data.get("output_file") if isinstance(data, dict) else data
                            self.torrent_result = data
                        self.finished_signal.emit(success, data)
            except Exception:
                pass
            time.sleep(0.05)

        try:
            while not self.queue.empty():
                msg = self.queue.get_nowait()
                if msg[0] == 'progress':
                    self.progress_signal.emit(msg[1], msg[2])
                elif msg[0] == 'finished':
                    success, data = msg[1], msg[2]
                    if success:
                        self.temp_torrent_path = data
                    self.finished_signal.emit(success)
        except Exception:
            pass

    def cancel(self):
        if self.process and self.process.is_alive():
            self.process.terminate()
            self.process.join()
        self.finished_signal.emit(False, None)