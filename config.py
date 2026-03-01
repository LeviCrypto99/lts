VERSION = "2.1.5"
UPDATE_INFO_URL = "https://raw.githubusercontent.com/LeviCrypto99/lts/main/version.json"
UPDATE_TIMEOUT_SEC = 5
UPDATE_AUTH_TOKEN_ENV = "LTS_UPDATE_TOKEN"
UPDATER_URL = ""
ALLOW_LAUNCH_ON_UPDATE_CHECK_FAILURE = True
UPDATE_CHECK_STRICT_MODE_ENV = "LTS_UPDATE_STRICT_MODE"
LOG_ROTATE_MAX_BYTES = 5 * 1024 * 1024
# Keep up to 10 files per log stream (1 active + 9 backups).
LOG_ROTATE_BACKUP_COUNT = 9

# Signal source defaults baked into the client build.
# Users should be able to run EXE without extra environment setup.
SIGNAL_SOURCE_MODE_DEFAULT = "relay"
SIGNAL_RELAY_BASE_URL_DEFAULT = "https://port-0-lts-signal-relay-mjtr1yoo788d348e.sel3.cloudtype.app"
SIGNAL_RELAY_TOKEN_DEFAULT = ""
