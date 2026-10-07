<img width="1538" height="967" alt="image" src="https://github.com/user-attachments/assets/5541a5cc-5f93-4208-b228-eb869f5c0418" />

# GayTorrent Uploader

### Key Features

* Emulates the look and feel of the online upload page.
* Image files added to the torrent content automatically populate the torrent presentation pictures.
* Allows uploading to categories that the user has blocked for convenience.
* Added a history panel with previous runs, their status & download link.
* Has a built-in highly customizable Contact Sheet creator (can create contact sheets and individual thumbnail frames).
* Option to automatically start seeding the uploaded torrent using qBittorrent (currently this is the only client supported)

### Security
On the first launch, the uploader asks for a personal API key. You can create one on gaytor.rent under Settings → Account → API keys; the key only allows uploads and can be revoked there at any time. It is stored securely in Windows Credential Manager via keyring. No browser is opened and no cookies are stored any more.

The Logout button removes the key from Credential Manager. To disable the key itself, revoke it on the site.

### Pick Files
Unlike other similar tools, this mode allows the user to pick one or more files from a folder without including the entire directory.
It does so by relying on a staging folder containing hardlinks, created in the input's relative path and removed after the task is done or cancelled.

### Previous Runs
Every task is logged to the History panel, keeping date, time, torrent title, task status (failed, canceled, success), and a link to the download page when applicable.


