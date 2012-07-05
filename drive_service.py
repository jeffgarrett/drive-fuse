#!/usr/bin/env python

import datetime
import httplib2
import os
import time

from apiclient.discovery import build
from oauth2client.file import Storage
from oauth2client.client import flow_from_clientsecrets
from oauth2client.tools import run

CLIENT_SECRETS = 'client_secrets.json'
MISSING_CLIENT_SECRETS_MESSAGE = """
WARNING: Please configure OAuth 2.0

To make this sample run you will need to populate the client_secrets.json file
found at:

%s

with information from the APIs Console <https://code.google.com/apis/console>.

""" % os.path.join(os.path.dirname(__file__), CLIENT_SECRETS)

FLOW = flow_from_clientsecrets(CLIENT_SECRETS,
        scope='https://www.googleapis.com/auth/drive',
        message=MISSING_CLIENT_SECRETS_MESSAGE)

class DriveFileProxy:
    all_files = {}

    def __init__(self, attrs):
        self.attrs = attrs
        if "title" in self.attrs:
            self.escaped_name = self.title.replace("/", "%2F")
        DriveFileProxy.all_files[self.id] = self

    def __getattr__(self, name):
        # Handle parents and children specially
        if name == "parents":
            if "parents" not in self.attrs:
                return []
            return [DriveFileProxy.all_files[p["id"]] for p in self.attrs["parents"]]
        if name == "children":
            return [x for x in DriveFileProxy.all_files.values() if self in x.parents]
        if name in self.attrs:
            return self.attrs[name]
        raise AttributeError

    def is_folder(self):
        return self.mimeType == "application/vnd.google-apps.folder"

    def get_file_size(self):
        if self.is_folder():
            return 4096
        if "fileSize" in self.attrs:
            return long(self.attrs["fileSize"])
        return 0

    def get_access_date(self):
        if "lastViewedByMeDate" not in self.attrs:
            return time.time()

        dt = self.lastViewedByMeDate
        secs = datetime.datetime.strptime(dt.split(".")[0], "%Y-%m-%dT%H:%M:%S")
        ms = int(dt.split(".")[1][:-1])
        secs.replace(microsecond=1000*ms)

        return time.mktime(secs.timetuple())

    def get_create_date(self):
        if "createdDate" not in self.attrs:
            return time.time()

        dt = self.createdDate
        secs = datetime.datetime.strptime(dt.split(".")[0], "%Y-%m-%dT%H:%M:%S")
        ms = int(dt.split(".")[1][:-1])
        secs.replace(microsecond=1000*ms)

        return time.mktime(secs.timetuple())

    def get_modify_date(self):
        if "modifiedDate" not in self.attrs:
            return time.time()

        dt = self.modifiedDate
        secs = datetime.datetime.strptime(dt.split(".")[0], "%Y-%m-%dT%H:%M:%S")
        ms = int(dt.split(".")[1][:-1])
        secs.replace(microsecond=1000*ms)

        return time.mktime(secs.timetuple())

class DriveService:
    def __init__(self, email):
        storage = Storage("drive-fuse.dat")
        credentials = storage.get()
        if credentials is None or credentials.invalid:
            credentials = run(FLOW, storage)
        http = httplib2.Http()
        http = credentials.authorize(http)
        self.service = build("drive", "v2", http=http)

        about = self.service.about().get().execute()
        self.largestChangeId = about.get("largestChangeId")
        self.rootFolder = DriveFileProxy({"id": about.get("rootFolderId"),
            "mimeType": "application/vnd.google-apps.folder"})

        self.refresh()

    def refresh(self):
        # Grab the list of files
        req = self.service.files().list(maxResults=10000)
        while True:
            files = req.execute()
            for f in files.get("items"):
                fp = DriveFileProxy(f) 
            nextPageToken = files.get("nextPageToken")
            if nextPageToken is None:
                break
            req = self.service.files().list(pageToken=nextPageToken)

        # Cache by filename to speed lookup
        self.filename_cache = {}
        stack = [self.rootFolder]
        self.rootFolder.full_name = "/"
        while stack:
            d = stack.pop(0)
            for f in d.children:
                f.full_name = os.path.join(d.full_name, f.escaped_name)
                self.filename_cache[f.full_name] = f
                if f.is_folder():
                    stack.append(f)

    def lookup(self, path):
        path = os.path.normpath(path)
        while path[-1:] == "/":
            path = path[:-1]
        if path in self.filename_cache:
            return self.filename_cache[path]

        # This shouldn't really come up
        f = self.rootFolder
        for component in path.split("/"):
            if component == "." or component == "":
                continue
            for x in f.children:
                if x.escaped_name == component:
                    f = x
                    break
            else:
                return None
        self.filename_cache[path] = f
        return f

    def readdir(self, folder):
        """
        Return a list of direct children
        """
        return folder.children
