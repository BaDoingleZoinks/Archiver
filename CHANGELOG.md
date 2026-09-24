# Changelog

All notable changes to **The Archiver**, extracted directly from the official GitHub repository (`BaDoingleZoinks/Archiver`) commit history.

## [1.6.2] - Latest
### Added
- **Data Export**: Added the ability to export a table (CSV, TXT, JSON) with all archived videos and their tags for external analysis.

## [1.6.1]
### Fixed
- **Wayback Machine**: Fixed availability check and URL fragments.

## [1.6.0]
### Added
- **Browser & Cookies Support**: Added support for `cookies.txt` imports to bypass login walls and age-restrictions.
- **Diagnostic Tools**: Added locked browser diagnostics to help troubleshoot connection issues.
- **Resilience**: Added exponential backoff to handle Internet Archive (IA) rate limits smoothly without crashing.

## [1.5.1]
### Fixed
- **History Sync**: Resolved a critical `KeyError: 1` bug that occurred in `sync_history_from_account` during data fetch.

## [1.5.0]
### Added
- **Archive History Sync**: Users can now synchronize their entire upload history directly from their Archive.org account.
- **Ledger Tagging**: Added support for tagging ledgers.
- **Safety Locks**: Ledger controls are now correctly locked during an active archiving run to prevent mid-run file corruption.

## [1.4.0]
### Added
- **Cloud Cooldown Sync**: The upload cooldown timer now synchronizes across multiple devices via the user's Archive.org account, preventing rate-limit bans when using the app on multiple PCs.

## [1.3.1]
### Added
- **Ledger Deletion**: Added a "Remove Ledger" button, featuring a safe disk file deletion prompt to prevent accidental data loss.

## [1.3.0]
### Added
- **Account Onboarding**: Added a first-launch prompt and a dedicated IA (Internet Archive) Account Setup dialog for easier credential management.
- **Dynamic Queries**: The app now dynamically queries the uploader's account rather than relying on hardcoded paths.

## [1.2.0]
### Added
- **Friendly Ledger Names**: Added support for mapping local ledger file paths to friendly, readable names in the UI.
- **Updater Improvements**: The integrated updater now filters out raw commit hashes for a cleaner user experience.

## [1.1.0]
### Added
- **Ledger Management**: Added "Choose Ledger" and "New Ledger" options to easily manage multiple archives.
- **Repo Cleanliness**: Removed personal `archive.txt` files from git tracking.

## [1.0.0]
### Added
- **Initial Major Release**: Launched The Archiver v1.0.0.
- **Built-in Updater**: Added the In-App Version & Update Manager.
- **GitHub Sync**: Added GitHub synchronization and the `push_to_github` helper script.
