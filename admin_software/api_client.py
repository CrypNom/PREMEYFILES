"""
api_client.py - Talks to the PREMEYFILES website through its secure API.

The desktop app keeps NO website data of its own. Every action
(list, upload, edit, delete ...) is a request to the website.
Only the server address and the login token (in memory) are used.
"""
import json
import mimetypes
import os
import uuid
from pathlib import Path

import requests

SETTINGS_FILE = Path(__file__).resolve().parent / "admin_settings.json"
DEFAULT_URL = "http://127.0.0.1:5000"


class ApiError(Exception):
    """An error with a message that is safe to show to the admin."""

    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


# ------------------------------------------------------------------ saved server address
def load_server_url():
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8")).get("server_url", DEFAULT_URL)
    except (OSError, ValueError):
        return DEFAULT_URL


def save_server_url(url):
    try:
        SETTINGS_FILE.write_text(json.dumps({"server_url": url}), encoding="utf-8")
    except OSError:
        pass  # not important


def normalize_url(url):
    url = (url or "").strip().rstrip("/")
    if not url:
        raise ApiError("Please enter the website address.")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url if "." in url and not url.startswith(("127.", "localhost")) else "http://" + url
    return url


# ------------------------------------------------------------------ upload body with progress
class MultipartBody:
    """Builds a multipart/form-data body piece by piece so we can report upload progress
    (and so large files are never loaded into memory all at once)."""

    def __init__(self, fields, files, progress=None):
        self.boundary = uuid.uuid4().hex
        self.progress = progress
        self._segments = []          # bytes or open file objects
        self._lengths = []
        for name, value in fields.items():
            head = ('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n' % (self.boundary, name)).encode()
            self._add(head + str(value).encode("utf-8") + b"\r\n")
        for name, path in files.items():
            filename = os.path.basename(path)
            ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            safe_name = filename.replace('"', "_").replace("\r", "").replace("\n", "")
            head = ('--%s\r\nContent-Disposition: form-data; name="%s"; filename="%s"\r\n'
                    "Content-Type: %s\r\n\r\n" % (self.boundary, name, safe_name, ctype)).encode("utf-8")
            self._add(head)
            handle = open(path, "rb")
            self._add(handle, os.path.getsize(path))
            self._add(b"\r\n")
        self._add(("--%s--\r\n" % self.boundary).encode())
        self.total = sum(self._lengths)
        self.sent = 0
        self._index = 0

    def _add(self, segment, length=None):
        self._segments.append(segment)
        self._lengths.append(len(segment) if length is None else length)

    @property
    def content_type(self):
        return "multipart/form-data; boundary=%s" % self.boundary

    def __len__(self):
        return self.total

    def read(self, size=65536):
        if size is None or size < 0:
            size = 65536
        out = b""
        while len(out) < size and self._index < len(self._segments):
            segment = self._segments[self._index]
            want = size - len(out)
            chunk = segment.read(want) if hasattr(segment, "read") else segment[:want]
            if hasattr(segment, "read"):
                if not chunk:
                    self._index += 1
                    continue
            else:
                rest = segment[len(chunk):]
                if rest:
                    self._segments[self._index] = rest
                else:
                    self._index += 1
            out += chunk
        self.sent += len(out)
        if self.progress and out:
            self.progress(min(self.sent, self.total), self.total)
        return out

    def __iter__(self):
        while True:
            chunk = self.read()
            if not chunk:
                return
            yield chunk

    def close(self):
        for segment in self._segments:
            if hasattr(segment, "close"):
                segment.close()


# ------------------------------------------------------------------ the client
class ApiClient:
    def __init__(self):
        self.base_url = ""
        self.token = None
        self.username = ""
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "PREMEYFILES-Admin/1.0"

    # ---- low level
    def _request(self, method, path, **kwargs):
        headers = kwargs.pop("headers", {})
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        try:
            response = self.session.request(method, self.base_url + path, headers=headers,
                                            timeout=kwargs.pop("timeout", 30), **kwargs)
        except requests.exceptions.SSLError:
            raise ApiError("Secure connection failed. Check the website address (https://...).")
        except requests.exceptions.ConnectionError:
            raise ApiError("Cannot reach the website at %s. Is it running and is the address correct?" % self.base_url)
        except requests.exceptions.Timeout:
            raise ApiError("The website took too long to answer. Try again.")
        except requests.exceptions.RequestException as exc:
            raise ApiError("Network error: %s" % exc)

        try:
            data = response.json()
        except ValueError:
            raise ApiError("The server sent an unexpected answer (HTTP %d). Is the address the PREMEYFILES website?"
                           % response.status_code, response.status_code)
        if response.status_code >= 400 or not data.get("ok", False):
            raise ApiError(data.get("error", "Request failed (HTTP %d)." % response.status_code), response.status_code)
        return data

    def get(self, path, **params):
        return self._request("GET", path, params=params)

    def post_json(self, path, body=None):
        return self._request("POST", path, json=body or {})

    def put_json(self, path, body):
        return self._request("PUT", path, json=body)

    def delete(self, path):
        return self._request("DELETE", path)

    # ---- authentication
    def login(self, url, username, password):
        self.base_url = normalize_url(url)
        self.token = None
        data = self._request("POST", "/api/login", json={"username": username, "password": password})
        self.token = data["token"]
        self.username = data["username"]
        save_server_url(self.base_url)
        return data

    def logout(self):
        try:
            if self.token:
                self._request("POST", "/api/logout", timeout=5)
        except ApiError:
            pass
        self.token = None

    # ---- projects
    def dashboard(self):
        return self.get("/api/dashboard")

    def projects(self, q="", category=None):
        params = {"q": q}
        if category:
            params["category"] = category
        return self.get("/api/projects", **params)["projects"]

    def project(self, project_id):
        return self.get("/api/projects/%d" % project_id)["project"]

    def _send_project(self, method, path, fields, files, progress):
        body = MultipartBody(fields, files, progress)
        try:
            return self._request(method, path, data=body, headers={"Content-Type": body.content_type},
                                 timeout=(15, 3600))["project"]
        finally:
            body.close()

    def create_project(self, fields, file_path, thumb_path=None, progress=None):
        files = {"file": file_path}
        if thumb_path:
            files["thumbnail"] = thumb_path
        return self._send_project("POST", "/api/projects", fields, files, progress)

    def update_project(self, project_id, fields, file_path=None, thumb_path=None, progress=None):
        files = {}
        if file_path:
            files["file"] = file_path
        if thumb_path:
            files["thumbnail"] = thumb_path
        return self._send_project("PUT", "/api/projects/%d" % project_id, fields, files, progress)

    def delete_project(self, project_id):
        return self.delete("/api/projects/%d" % project_id)

    # ---- categories / languages
    def categories(self):
        return self.get("/api/categories")["categories"]

    def languages(self):
        return self.get("/api/languages")["languages"]

    # ---- settings
    def settings(self):
        return self.get("/api/settings")

    def save_settings(self, values):
        return self.put_json("/api/settings", values)

    def change_password(self, current, new):
        return self.post_json("/api/change-password", {"current": current, "new": new})

    # ---- messages
    def messages(self):
        return self.get("/api/messages")["messages"]
