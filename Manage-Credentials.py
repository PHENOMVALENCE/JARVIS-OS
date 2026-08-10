"""Interactive Windows Credential Manager helper for optional integrations."""

from getpass import getpass

from jarvis_os.credentials import CredentialStore


SUPPORTED = (
    "github_token", "notion_token", "notion_database_id", "home_assistant_token",
    "home_assistant_url", "email_username", "email_password", "email_imap_server",
    "calendar_ics_url",
)


def main():
    store = CredentialStore()
    print("Supported credentials:", ", ".join(SUPPORTED))
    name = input("Credential name: ").strip()
    if name not in SUPPORTED:
        raise SystemExit("Unsupported credential name.")
    secret = getpass("Value (input is hidden): ")
    if not secret:
        store.delete(name)
        print("Credential removed.")
    else:
        store.set(name, secret)
        print("Credential saved in Windows Credential Manager.")


if __name__ == "__main__":
    main()
