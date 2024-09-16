from google_auth_oauthlib.flow import Flow
from flask import url_for
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from email.mime.text import MIMEText
import base64

# Load client secrets from JSON
CLIENT_SECRETS_FILE = "credentials.json"
SCOPES = ['https://www.googleapis.com/auth/drive', 
          'https://www.googleapis.com/auth/drive.metadata.readonly',
          'https://www.googleapis.com/auth/gmail.send',
          'https://www.googleapis.com/auth/gmail.readonly']

API_SERVICES = {
    'drive': 'v3',
    'gmail': 'v1'
}

def credentials_to_dict(credentials):
    return {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }

def authorize():
    flow = Flow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes=SCOPES)
    flow.redirect_uri = url_for('oauth2callback', _external=True)

    return flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )

def oauth2callback(state, authorization_response):
    flow = Flow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes=SCOPES, state=state)
    flow.redirect_uri = url_for('oauth2callback', _external=True)

    flow.fetch_token(authorization_response=authorization_response)

    return credentials_to_dict(flow.credentials)

def build_services(credentials):
    credentials = Credentials(**credentials)
    services = {}
    for service_name, version in API_SERVICES.items():
        services[service_name] = build(service_name, version, credentials=credentials)
    return services

class FileIterator:
    def __init__(self, service):
        """ Initialize with the Google Drive service object and setup pagination. """
        self.service = service
        self.files = []
        self.page_token = None
        self.current_index = 0
        self._fetch_next_page()

    def _fetch_next_page(self):
        """ Fetch the next page of files from My Drive. """
        response = self.service.files().list(
            q="trashed = false",
            spaces='drive',
            fields="nextPageToken, files(id, name, permissions, modifiedTime, owners)",
            pageToken=self.page_token
        ).execute()

        # Get the list of files from the response
        self.files = response.get('files', [])
        self.page_token = response.get('nextPageToken', None)
        self.current_index = 0  # Reset index for the new page

    def has_next(self):
        """ Return whether there are more files to iterate over. """
        return self.current_index < len(self.files) or self.page_token is not None

    def next_file(self):
        """ Return the next file, fetching new pages if needed. """
        if self.current_index >= len(self.files):
            if self.page_token:
                self._fetch_next_page()
            else:
                return None  # No more files available

        if self.files:
            file = self.files[self.current_index]
            self.current_index += 1
            return file
        return None
    
def file_is_public(file):
    """ Check if a file is public. """
    return not file["permissions"] or any(permission["type"] == "anyone" for permission in file["permissions"])

def make_private(service, file):
    """ Make a file private if the user has the permission. """
    if not file["permissions"]: 
        return False

    try:
        service.permissions().delete(
            fileId=file['id'],
            permissionId='anyoneWithLink'
        ).execute()
        return True
    except HttpError as error:
        return False
    
def mail_notify(service, files, owner):
    """ Send an email notification to the file owner listing the files that were made private. """
    files_str = "<br>".join([f'{file["name"]} ({file["id"]})' for file in files])
    user_mail = service.users().getProfile(userId='me').execute()['emailAddress']
    message_body = f"""Hello, 
    <br><br> The file database app has found the following files to be public: 
    <br><br> {files_str} 
    <br><br> For your security, these files have been made private."""
    message = MIMEText(message_body, 'html')
    message['to'] = owner
    message['from'] = user_mail
    message['subject'] = "Google Drive Files Update"
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    try:
        service.users().messages().send(userId='me', body={'raw': raw}).execute()
        return True
    except HttpError as error:
        return False


