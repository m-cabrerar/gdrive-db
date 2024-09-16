from sqlalchemy import create_engine, text
from sqlalchemy_utils import database_exists, create_database
import google_lib

def process_files(file_iterator, db, privated_files, service_gdrive):
    """ Iterates over files. 
    If a file is public, makes it private. 
    Stores or updates all files in the database. """
    files = []
    while file_iterator.has_next():
        file = file_iterator.next_file()
        if file:
            file['permissions'] = file.get('permissions', [])
            is_public = google_lib.file_is_public(file)
            file['visibility'] = "PUBLIC" if is_public else "PRIVATE"
            if is_public:
                if google_lib.make_private(service_gdrive, file):
                    file['visibility'] = "PRIVATE"
                    privated_files[file["owners"][0]["emailAddress"]] = privated_files.get(file["owners"][0]["emailAddress"], []) + [file]
            
            db.insert_file(file)
            if is_public: db.insert_privacy_history(file["id"])
            files.append(file)
    return files

def notify_owners(service_gmail, privated_files):
    """ Notifies the owners of the files that were made private. """
    for owner, files in privated_files.items():
        google_lib.mail_notify(service_gmail, files, owner)

class DriveDB:
    """ Class to interact with the database. """
    def __init__(self, DB_URL, DB_NAME):
        self.engine = create_engine(DB_URL, isolation_level="AUTOCOMMIT")
        if not database_exists(self.engine.url):
            create_database(self.engine.url)
        self.DB_URL = DB_URL
        self.DB_NAME = DB_NAME
        self.files_table = ""
        self.privacy_history_table = ""

    def create_files_table(self, table_name):
        """ Creates the table to store the files. """
        with self.engine.connect() as connection:
            connection.execute(text("CREATE TABLE IF NOT EXISTS " + table_name
                                    + " (id VARCHAR(255) PRIMARY KEY NOT NULL, "
                                    + " name VARCHAR(255) NOT NULL, "
                                    + " extension VARCHAR(10), "
                                    + " owner VARCHAR(255), "
                                    + " visibility VARCHAR(10), "
                                    + " last_modified TIMESTAMP)"))
            
            self.files_table = table_name

    def insert_file(self, file):
        """ Inserts or updates a file in the database. """
        extension = file['name'].split('.')[-1] if '.' in file['name'] else None
        name = file['name'].replace("." + extension, '') if extension else file['name']
        owner = file['owners'][0]['emailAddress'] if file['owners'] else None

        with self.engine.connect() as connection:
            result = connection.execute(text(f"SELECT * FROM {self.files_table} WHERE id = '{file['id']}'"))
            if result.rowcount > 0:
                connection.execute(text(f"UPDATE {self.files_table} SET name = '{name}', "
                                        + f"extension = " + ('NULL' if not extension else "'"+extension+"'") + ", "
                                        + f"owner = " + ('NULL' if not owner else "'"+owner+"'") + ", "
                                        + f"visibility = '{file['visibility']}', "
                                        + f"last_modified = '{file['modifiedTime']}' "
                                        + f"WHERE id = '{file['id']}'"))
            else:
                connection.execute(text(f"INSERT INTO {self.files_table} (id, name, extension, owner, visibility, last_modified) "
                                        + f"VALUES ('{file['id']}', '{name}', "
                                        + ('NULL' if not extension else "'"+extension+"'") + ", "
                                        + ('NULL' if not owner else "'"+owner+"'") + ", "
                                        + f"'{file['visibility']}', '{file['modifiedTime']}')"))

    def create_privacy_history_table(self, table_name, files_table):
        """ Creates the table to store the privacy history of the files. """
        with self.engine.connect() as connection:
            connection.execute(text("CREATE TABLE IF NOT EXISTS " + table_name
                                    + " (file_id VARCHAR(255) PRIMARY KEY NOT NULL, "
                                    + " last_public TIMESTAMP, "
                                    + " FOREIGN KEY (file_id) REFERENCES " + files_table + "(id))"))
            
            self.privacy_history_table = table_name

    def insert_privacy_history(self, file_id):
        """ Inserts or updates the privacy history of a file in the database. """
        with self.engine.connect() as connection:
            result = connection.execute(text(f"SELECT * FROM {self.privacy_history_table} WHERE file_id = '{file_id}'"))
            if result.rowcount > 0:
                connection.execute(text(f"UPDATE {self.privacy_history_table} SET last_public = CURRENT_TIMESTAMP WHERE file_id = '{file_id}'"))
            else:
                connection.execute(text(f"INSERT INTO {self.privacy_history_table} (file_id, last_public) VALUES ('{file_id}', CURRENT_TIMESTAMP)"))
