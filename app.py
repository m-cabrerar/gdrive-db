# app.py
import os
from flask import Flask, redirect, url_for, session, request


import google_lib
import gdrive_db
import tests

# Create Flask app
app = Flask(__name__)

FILES_TABLE = "files"
PRIVACY_HISTORY_TABLE = "privacy_history"

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
DB_NAME = os.getenv('DATABASE_NAME')
DB_URL = f"postgresql://user:password@db:5432/{DB_NAME}"

db = gdrive_db.DriveDB(DB_URL, DB_NAME)
db.create_files_table(FILES_TABLE)
db.create_privacy_history_table(PRIVACY_HISTORY_TABLE, FILES_TABLE)

@app.route('/logout')
def logout():
    session.pop('credentials', None)
    session.pop('state', None)
    session.clear()
    session.permanent = False
    return redirect(url_for('authorize'))

@app.route('/')
def index():
    if 'credentials' not in session:
        return redirect(url_for('authorize'))
    
    services = google_lib.build_services(session['credentials'])
    return main(services['drive'], services['gmail'])

@app.route('/authorize')
def authorize():
    authorization_url, state = google_lib.authorize()
    session['state'] = state
    return redirect(authorization_url)

@app.route('/oauth2callback')
def oauth2callback():
    session['credentials'] = google_lib.oauth2callback(session['state'], request.url)
    return redirect(url_for('index'))

def main(service_gdrive, service_gmail):
    result = ""
    privated_files = {}
    file_iterator = google_lib.FileIterator(service_gdrive)
    files = gdrive_db.process_files(file_iterator, db, privated_files, service_gdrive)
    gdrive_db.notify_owners(service_gmail, privated_files)
    for file in files:
        result += f'{file["id"]}, {file["name"]}, {file["owners"][0]["emailAddress"]}, {file["visibility"]}, {file["modifiedTime"]}<br>'
    return "Total files: " + str(len(files)) + "<br><br>" + result


if __name__ == '__main__':
    run_tests = os.getenv('RUN_TESTS')
    if run_tests:
        tests.run_all()
    
    app.run(host='0.0.0.0', port=5000, debug=True)

