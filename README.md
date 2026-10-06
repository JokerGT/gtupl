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
On the first launch, it uses Selenium to start a Chrome instance where you will login to your gaytorrent account. Once the login is successful, the browser will automatically close, and the session cookies will be safely stored into Windows Credential Manager, fully encrypted.

### Pick Files
Unlike other similar tools, this mode allows the user to pick one or more files from a folder without including the entire directory.
It does so by relying on a staging folder containing hardlinks, created in the input's relative path and removed after the task is done or cancelled.

### Previous Runs
Every task is logged to the History panel, keeping date, time, torrent title, task status (failed, canceled, success), and a link to the download page when applicable.


