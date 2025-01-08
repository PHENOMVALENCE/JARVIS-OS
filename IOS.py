from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import base64 
import os 
from googleapiclient import errors
from datetime import datetime

def recieve_message():


    ############## - Credentials - ##############

    SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file(
        'token.json', scopes=SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("client.json", SCOPES)
            creds = flow.run_local_server(port = 0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    ############# - API CALL - ###################

    try:
        service = build('gmail', 'v1', credentials=creds)
        result = service.users().messages().list(userId = 'me').execute()
        messages = result.get('messages')
        for i in messages:
            txt = service.users().messages().get(userId = 'me', id = i['id'], format = 'full').execute()
            payload = txt['payload']
            headers =payload['headers']
            for j in headers:
                #print(j)
                if j['name'] == 'Subject':
                    subject = j['name']
                if j['name'] == 'From' or j['name'] == 'from':
                    sender = j['value']
                if j['name'] == 'Date':
                    email_date = j['value']

            #Make sure that the email is from my phone before scanning
            if sender == '4632099000@vzwpix.com':
                parts = payload.get('parts')[0]
                attachment_id = parts['body']['attachmentId']
                attachment = service.users().messages().attachments().get(userId = 'me', messageId = i['id'], id=attachment_id).execute()
                data = base64.urlsafe_b64decode(attachment['data'].encode('UTF-8')).decode('UTF-8')

            #after getting the email, delete  it immediatly.
                service.users().messages().modify( userId='me', id=i['id'], body={ 'addLabelIds': ['TRASH'] }).execute()


    ############## - JARVIS LOGIC ##################

                # print(f"Email date: {date_obj}")
                # print(f"Email seconds: {date_obj_sec}")
                print(data)
                return data
            #print("ran but unsuccessful")
            return None
    except HttpError as error:
        print(f"An error has occured: {error}")

recieve_message()