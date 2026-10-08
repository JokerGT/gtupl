<img width="1538" height="967" alt="image" src="https://github.com/user-attachments/assets/5541a5cc-5f93-4208-b228-eb869f5c0418" />

# GayTorrent Uploader

### Key Features

* Emulates the look and feel of the online upload page.
* Image files added to the torrent content automatically populate the torrent presentation pictures.
* Option to automatically generate pictures for torrent presentation based on the torrent files.
* Allows uploading to categories that the user has blocked for convenience.
* History panel with previous runs, their status & download link.
* Has a built-in highly customizable Contact Sheet creator (can create contact sheets and individual thumbnail frames).
* Option to automatically start seeding the uploaded torrent using qBittorrent or uTorrent.

### Security
On the first launch, the program asks for a personal API key. You can create one on gaytor.rent under Settings → Account → API keys.
The key only allows uploads and can be revoked there at any time. It is stored securely in Windows Credential Manager via keyring.

The Logout button removes the key from Credential Manager without revoking the API key. Revoke is possible through the Account settings on the site.

### Pick Files
Unlike other similar tools, this mode allows the user to pick one or more files from a folder without including the entire directory.
It does so by relying on a staging folder containing hardlinks, created in the input's relative path and removed after the task is done or cancelled.

### Previous Runs
Every task is logged to the History panel, keeping date, time, torrent title, task status (failed, canceled, success), and a link to the download page when applicable.

### Generate presentation previews from content files
Once one or more videos are added to the file list, a button appears that allows creating previews for torrent presentation.
It allows to add still frames or contact sheets, those are added to the torrent page only, not to the torrent content.

The amount of still frames for each file depends on total of videos included in the torrent content:<br/>
1 video = 5 still frames<br/>
2 to 5 videos = 3 still frames<br/>
6 or more = 1 still frame

Individual frames can be included as part of the torrent content with no limitation using the sidebar settings.
