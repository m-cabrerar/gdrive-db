import datetime
import gdrive_db
import google_lib
import unittest
from unittest.mock import patch
from sqlalchemy import text

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_test_result(expected, result, message):
    print(message, end=" - ")
    if expected == result:
        print(bcolors.OKGREEN + "OK" + bcolors.ENDC)
    else:
        print(bcolors.FAIL + "FAIL" + bcolors.ENDC)


def test01_list_files():
    print(bcolors.HEADER + "Test 01: List files" + bcolors.ENDC)
    print("Expected: 3 files listed")
    # Setup
    mock_files = {
        "files": [
            { "id": "1", "name": "file1", "permissions": [], "modifiedTime": "2021-01-01T00:00:00Z", "owners": [{"emailAddress": "owner@test.test"}] },
            { "id": "2", "name": "file2", "permissions": [{"type": "anyone"}], "modifiedTime": "2021-01-02T00:00:00Z", "owners": [{"emailAddress": "test@test.test"}] },
            { "id": "3", "name": "file3", "permissions": [{"type": "user"}], "modifiedTime": "2021-01-03T00:00:00Z", "owners": [{"emailAddress": "test@test.test"}] }
        ]
    }
    mocked_service = unittest.mock.MagicMock()
    mocked_service.files().list().execute.return_value = mock_files
    mocked_iterator = google_lib.FileIterator(mocked_service)

    mocked_db = unittest.mock.MagicMock()
    mocked_db.insert_file.return_value = None
    mocked_db.insert_privacy_history.return_value = None
    
    # Execute
    files = gdrive_db.process_files(mocked_iterator, mocked_db, {}, mocked_service)

    # Assert
    print_test_result(3, len(files), "3 files listed")
    for file in files:
        if file["id"] == "1":
            print_test_result("file1", file["name"], "file1 listed")
            print_test_result("PUBLIC", file["visibility"], "file1 is public since user has no specific permissions")
        elif file["id"] == "2":
            print_test_result("file2", file["name"], "file2 listed")
            print_test_result("PRIVATE", file["visibility"], "file2 was public and now is private")
        elif file["id"] == "3":
            print_test_result("file3", file["name"], "file3 listed")
            print_test_result("PRIVATE", file["visibility"], "file3 is private")

def test02_store_files():
    print(bcolors.HEADER + "Test 02: Store files" + bcolors.ENDC)
    print("Expected: 3 files stored")
    # Setup
    mock_files = {
        "files": [
            { "id": "1", "name": "file1.py", "permissions": [], "modifiedTime": "2021-01-01T00:00:00Z", "owners": [{"emailAddress": "owner@test.test"}] },
            { "id": "2", "name": "file2.exe", "permissions": [{"type": "anyone"}], "modifiedTime": "2021-01-02T00:00:00Z", "owners": [{"emailAddress": "test@test.test"}] },
            { "id": "3", "name": "file3.pdf", "permissions": [{"type": "user"}], "modifiedTime": "2021-01-03T00:00:00Z", "owners": [{"emailAddress": "test@test.test"}] }
        ]
    }
    mocked_service = unittest.mock.MagicMock()
    mocked_service.files().list().execute.return_value = mock_files
    mocked_iterator = google_lib.FileIterator(mocked_service)

    db = gdrive_db.DriveDB("postgresql://user:password@db:5432/test", "test")
    borrar_tabla(db, "privacy_history")
    borrar_tabla(db, "files")
    db.create_files_table("files")
    db.create_privacy_history_table("privacy_history", "files")

    # Execute
    files = gdrive_db.process_files(mocked_iterator, db, {}, mocked_service)

    # Assert
    with db.engine.connect() as connection:
        result = connection.execute(text("SELECT COUNT(*) FROM files")).fetchone()[0]
        print_test_result(3, result, "3 files stored")

        result = connection.execute(text("SELECT COUNT(*) FROM privacy_history")).fetchone()[0]
        print_test_result(2, result, "2 privacy history entries stored")

        # assert file1
        result = connection.execute(text("SELECT * FROM files WHERE id = '1'")).fetchone()
        print_test_result("file1", result[1], "file1 stored")
        print_test_result("py", result[2], "file1 extension stored")
        print_test_result("owner@test.test", result[3], "file1 owner stored")
        print_test_result("PUBLIC", result[4], "file1 visibility stored")
        print_test_result(datetime.datetime(2021, 1, 1, 0, 0), result[5], "file1 last modified stored")

        # assert file2
        result = connection.execute(text("SELECT * FROM files WHERE id = '2'")).fetchone()
        print_test_result("file2", result[1], "file2 stored")
        print_test_result("exe", result[2], "file2 extension stored")
        print_test_result("test@test.test", result[3], "file2 owner stored")
        print_test_result("PRIVATE", result[4], "file2 visibility stored")
        print_test_result(datetime.datetime(2021, 1, 2, 0, 0), result[5], "file2 last modified stored")

        # assert file3
        result = connection.execute(text("SELECT * FROM files WHERE id = '3'")).fetchone()
        print_test_result("file3", result[1], "file3 stored")
        print_test_result("pdf", result[2], "file3 extension stored")
        print_test_result("test@test.test", result[3], "file3 owner stored")
        print_test_result("PRIVATE", result[4], "file3 visibility stored")
        print_test_result(datetime.datetime(2021, 1, 3, 0, 0), result[5], "file3 last modified stored")
    
    # Cleanup
    borrar_tabla(db, "privacy_history")
    borrar_tabla(db, "files")

def test03_make_private():
    print(bcolors.HEADER + "Test 03: Make file private" + bcolors.ENDC)
    print("Expected: File made private")
    # Setup
    file = { "id": "1", "permissions": [{"type": "anyone"}] }
    mocked_service = unittest.mock.MagicMock()
    mocked_service.permissions().delete().execute.return_value = None

    # Execute
    result = google_lib.make_private(mocked_service, file)

    # Assert
    print_test_result(True, result, "File made private")

def test04_mail_notify():
    print(bcolors.HEADER + "Test 04: Mail notify" + bcolors.ENDC)
    print("Expected: Mail sent")
    # Setup
    files = [
        { "id": "1", "name": "file1", "owners": [{"emailAddress": "test@test.test"}] },
        { "id": "2", "name": "file2", "owners": [{"emailAddress": "test@test.test"}] }
    ]
    mocked_service = unittest.mock.MagicMock()
    mocked_service.users().getProfile().execute.return_value = { "emailAddress": "test@test.test" }

    # Execute
    google_lib.mail_notify(mocked_service, files, "test@test.test")

    # Assert
    mocked_service.users().messages().send.assert_called_once()
    print_test_result(True, mocked_service.users().messages().send.called, "Mail sent")
                                                                
def borrar_tabla(db, table):
    with db.engine.connect() as connection:
        connection.execute(text(f"DROP TABLE IF EXISTS {table}"))


def run_all():
    test01_list_files()
    test02_store_files()
    test03_make_private()
    test04_mail_notify()

