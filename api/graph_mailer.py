import os
import requests


def _get_graph_token() -> str:
    tenant_id = os.environ["M365_TENANT_ID"]
    client_id = os.environ["M365_CLIENT_ID"]
    client_secret = os.environ["M365_CLIENT_SECRET"]

    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"

    r = requests.post(
        token_url,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials",
            "scope": "https://graph.microsoft.com/.default",
        },
        timeout=15,
    )
    if r.status_code != 200:
       raise Exception(f"Token request failed: {r.status_code} {r.text}")
    return r.json()["access_token"]



def send_booking_confirmed_email(
    *,
    from_user: str,  # e.g. "info@diveinsteam.org"
    to_emails: list[str],
    subject: str,
    body_text: str,
) -> None:
    token = _get_graph_token()

    url = f"https://graph.microsoft.com/v1.0/users/{from_user}/sendMail"
    payload = {
        "message": {
            "subject": subject,
            "body": {
                "contentType": "Text",
                "content": body_text,
            },
            "toRecipients": [{"emailAddress": {"address": e}} for e in to_emails],
        },
        "saveToSentItems": True,
    }

    r = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=15,
    )
    r.raise_for_status()
