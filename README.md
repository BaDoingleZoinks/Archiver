# The Archiver

A vibecoded, Python-based desktop application for backing up YouTube videos and Wikipedia reference URLs directly to the Internet Archive, along with Wayback Machine snapshots and bulk metadata editing tools.

## Features
- **YouTube Video Archiver**: Batch download and upload YouTube playlist or channel contents to Internet Archive with automatic metadata generation and batch metadata editing.
- **Wayback Page Archiver**: Collect Wikipedia reference URLs and easily archive them to the Wayback Machine.
- **Metadata Editor**: Batch view, edit, tag, and synchronize uploaded item metadata from your Archive.org account across multiple devices.
- **Custom & Shared Ledgers**: Ledger system prevents duplicate file processing. Choose existing ledgers or create new ones. Put ledger files in shared cloud or network folders for team/device collaboration without conflict.
- **Internet Archive Account Setup**: Automatic first-run setup to configure your personal `ia.ini` credentials (via S3 API keys or Archive.org login). Credentials remain strictly in your private local profile and are never tracked in Git.
- **In-App Version & Update Manager**: Check for updates, upgrade to latest builds, or roll back to previous versions directly within the application.

## Setup & Running

### Requirements
- Python 3.10+
- Install dependencies:
  ```bash
  pip install -r requirements.txt
  ```

### Launching
- Double-click `start_app.bat` to launch the app.
- On any synced machine, double-click `update_and_run.bat` to pull the latest changes from GitHub before launching.
  - Or start app and click `Check for Updates/Sync`
- On first launch, enter your Internet Archive S3 credentials when prompted to enable uploading.
   - Click the Keys button on the top right of the window to access your login at any time.

### Updating

- On the top right, click Check for Updates/Sync
- Enter your update repository (this one, or your fork)
- Click Fetch Versions to check for updates. Update to the latest version or roll back to a previous build saved locally.
- if not, run `update_and_run.bat` before launching.

## Use

### Youtube Video Archiver

The first tab of the app to be developed. A walkthrough of each field:

- Youtube Playlist URL:
  - Paste the URL of the playlist of channel whose contents you want to archive. Playlists must be Public or Unlisted; cannot be Private.
  - Allows for naming and renaming of URLs for ease of use.
  - Can save URLs as presets to quickly switch between them.

- Custom tags (comma-separated):
  - Type the Internet Archive subjects tags to mark your content with, separated by commas.
  - Allows saving presets to quickly switch between them.

- Max Resolution:
  - Can set the maximum download resolution, to avoid downloading large files.
 
- Metadata language:
  - Language tag that will be set on your videos.
 
- Browser cookies:
  - Type in the name of your browser and the tool will retrieve your account cookies in order to prevent download errors and IP timeouts/bans.
 
- Upload delay:
  - Delay (in minutes) between Internet Archive uploads to avoid being rate limited.
  - App automatically applies exponential delays in case of rate limits, and stops after three failed attempts to prevent IP bans.
  - Personal testing found 15 minutes to be the shortest usable delay when mass archiving files. Experiment at your own risk.

- Download Directory:
  - Local directory where the tool will keep the video files prior to uploading.
  - Though one can disable the permanent saving of the video files, the tool needs a temporary space to store the file you will upload. If the option to save videos locally is disabled, the file will be deleted after a confirmed successful upload.

- Active ledger:
  - .txt file that keeps track of videos archived with timestamps
  - The tool will not archive any video already found in the ledger. This is to prevent duplicate uploads.
  - Can choose an existing ledger or create a new one.
  - Tip: save the ledger to a network folder like Google Drive to be able to sync it across devices!
 
- Keep Video Files Locally After Upload
  - When enabled, saves downloaded videos to local directory

- Prevent PC from sleeping while archiving
  - Useful if you want to leave the PC on to archive content while you're away.

- Enable Dark Mode
  - To prevent you from flash banging yourself at night!  

- Download oldest first (reverse playlist)
  - Will archive content starting from the oldest, instead of the newest
 
- Open active ledger
  - Will open the selected ledger on your default text editor

- Open settings
  - Will open the Settings.json file on your default app
  - This is where your tag presets and other settings are saved. 

 Click on Start Archiving and you will see the activity log populate. The tool will scan the channel or playlist, download a video, parse its metadata, and upload it with your selected tags to your Internet Archive. It will then download the next video, wait for the configured delay, and upload it. The tool skips any video previously recorded on your selected ledger file to avoid duplicate uploads. 
 On the right you will see the Time Since Last Upload. The timer is synced to your account, so you can turn on the tool on another device and not get rate limited; the tool will wait the correct time. 

 The Archive History tab will display all items uploaded. If you use the tool on multiple devices, it will be missing the items uploaded from other devices. Click Sync and Refresh From Account to sync your uploads from your devices. The log will also show from which ledger the file was uploaded.  

 ### Wayback Page Archiver

The second feature to be developed. Intended for archiving Wikipedia references. Admittedly the least polished functionality, currently, as it's overall not as problematic to do it without the app, unlike mass archiving and tagging videos. 

Paste the URL of the Wikipedia article you are editing and click Fetch References on the right. It will populate the page with all links present in the article. It will then check the Wayback Machine to see if each URL has already been archived, and when. It will also tell you if a link is dead (note: sometimes the reference is alive but shows up as dead. This happens when the dead link is the http version, but if you look up the referece online, the article will sometimes be available under a new https URL. It is suggested that you change the reference in the article to the https version and then archive it). 

There are checkboxes for saving a screenshot of the archived page, as well as its outlinks, and saving it to your Web Archive, as you would be able to do on the Wayback Machine normally. 

Click on Archive Now to save a page to the Wayback Machine. It will output the archived URL. Don't forget to insert it to the references list in the article!


### Metadata Editor

Third main tab. Allows you to bulk edit the metadata of the videos you upload to Internet Archive.

- In the main table you will see all the content you've uploaded with the Youtube Video Archiver tab.
  - As well as all manually archived content ("legacy" content).
- You can search for title or tag terms with the search bar on the top.

Bulk metadata editing:

- Select the videos you want to edit with the checkboxes on the left. Type your tags (comma-separated) on the bottom field or select from your tag presets. You can create and remove presets from here as well. 
  - Tip: if you double click the tags of an existing row on the list, it will populate those tags into the tags field!
- Click on Update Metadata for Selected Items on the bottom to bulk apply the tags to the selected items.
  - Note: though the tags refresh immediately in the app, sometimes it takes some time for the tags to apply on Archive.org. If you immediately refresh the tab with the Sync With Account button, or immediately check your Archive, you might not see the changes take effect until a while has passed.
- WARNING: the tool does not deselect items automatically! Make sure you click on Deselect All to avoid giving all your items the same tag!
  - Likewise, mind the difference between Select Filtered and Select All.
- Click Sync With Account to sync the list across devices.
- You can also change the language of the files you've uploaded as a batch.


A powerful tool in this tab is the ability to export and import your table of archived content to bulk update metadata even easier!

- Click Export Table to export a snapshot of the videos archived in your account into CSV, text, or JSON format. This will let you analyze your content elsewhere in a better interface than from within the app.
  - Note: What is saved is a static snapshot. If you update the tags of your content in the app after exporting, your exported file will naturally not update automatically.
- What is really powerful is that you can now feed this table to your LLM of choice. For instance, you can ask an AI to identify all items with a placeholder tag (like the name of the channel or playlist being archived) and replace it with a set of highly specific, appropriate tags for each video—without you having to check all entries one by one.
- You do this by telling the AI to output the new data to a CSV or JSON file. This new table only strictly requires an Identifier (or ID) column so the app knows which video it is, and then the columns for the metadata you want to modify (Title, Language, Tags, etc). Any extra columns the AI generates are safely ignored.
  - Example prompt: "Read this file. For all rows with placeholder tag ABC, replace the tags with an appropriate set (comma-separated) to match the video title and topic. Do not output rows that do not match the criteria. Output as a downloadable CSV UTF-8 file with table headers ID, Video ID, Language, Title, and Tags."
  - Sometimes (inconsistent issue) AI's have a hard time parsing the file because of the BOM character encoding that ensures some symbols like accent marks don't come out all mangled when imported to Excel. Try specifying something like "Technical Note: This CSV contains a UTF-8 BOM. When reading or analyzing this dataset with Python, you must load it using pandas.read_csv with encoding='utf-8-sig' to avoid \ufeff header parsing errors." when prompting. Sometimes it helps. 
  - It would not be a bad idea to engineer the prompt so that it tries to reuse your tag presets, but I'll leave that implementation up to you.	
	
- Then, click on Import Table (Batch) and select your edits file. The tool will find the differences between your live account and the edits in the uploaded table. Before it applies anything to the Internet Archive, it will pop up a window allowing you to carefully preview every single change.
  - *And please, do carefully review the changes in the preview window, as a bulk mistake can be hard to fix!*



