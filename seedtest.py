import os
import subprocess
import tempfile

def run_dry_run_test():
    print("=== STARTING AUTOMATIC SEEDING DRY RUN ===")
    
    # Mock settings and parameters (modify these to match your actual test cases)
    settings = {
        "save_seeding": True,
        "torrent_client_path": r"D:\root\qBittorrent\qbittorrent.exe",
        "torrent_client": "qBittorrent"
    }
    
    encrypted_id = "YBJ2dD9zbyNnZUIc36Q5GQ"  # A known working ID from your earlier test
    
    # Test cases to simulate your modes
    test_cases = [
        {
            "name": "Single File Mode",
            "mode": "files",
            "file_input": [r"Untitled-1.png"] # Change to a real or dummy path if needed
        },
        {
            "name": "Folder Mode",
            "mode": "folder",
            "file_input": r"F:\qtm\refactored_project\tele"
        }
    ]
    
    for tc in test_cases:
        print(f"\n--- Testing Scenario: {tc['name']} ---")
        mode = tc["mode"]
        file_input = tc["file_input"]
        
        print(f"[Log] Mode: {mode}")
        print(f"[Log] File Input: {file_input}")
        
        # 1. Check local downloaded_torrents path
        program_dir = os.path.dirname(os.path.abspath(__file__))
        torrents_dir = os.path.join(program_dir, "downloaded_torrents")
        os.makedirs(torrents_dir, exist_ok=True)
        seeded_torrent_path = os.path.normpath(os.path.join(torrents_dir, f"{encrypted_id}.torrent"))
        
        print(f"[Log] Torrents Dir: {torrents_dir}")
        print(f"[Log] Seeded Torrent Path: {seeded_torrent_path}")
        print(f"[Log] Torrent file exists locally?: {os.path.exists(seeded_torrent_path)}")
        
        # 2. Path calculation logic
        client_path = settings.get("torrent_client_path", "")
        if client_path and client_path != "WebUI" and os.path.exists(client_path):
            if mode == "folder":
                if isinstance(file_input, (list, tuple)):
                    target_path = os.path.abspath(file_input[0])
                else:
                    target_path = os.path.abspath(str(file_input))
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

            save_path = os.path.normpath(save_path)
            print(f"[Log] Calculated save_path: {save_path}")
            
            # 3. Construct Command
            cmd = [
                client_path,
                "--skip-dialog=true",
                f"--save-path={save_path}",
                "--seed-mode",
                seeded_torrent_path
            ]
            
            print(f"[Log] Final Command Array:")
            for i, arg in enumerate(cmd):
                print(f"      [{i}] {arg}")
            
            # 4. Execute Dry Run check using subprocess.run to catch output/errors
            if os.path.exists(seeded_torrent_path):
                print(f"[Log] Executing subprocess test...")
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                    print(f"[Log] Subprocess Return Code: {result.returncode}")
                    print(f"[Log] Subprocess Stdout: {result.stdout.strip()}")
                    print(f"[Log] Subprocess Stderr: {result.stderr.strip()}")
                except Exception as e:
                    print(f"[Log] Subprocess execution exception: {e}")
            else:
                print(f"[Log] Skipping process execution because the .torrent file does not exist locally yet.")

if __name__ == "__main__":
    run_dry_run_test()