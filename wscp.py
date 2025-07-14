import os
import socket
from http.server import HTTPServer, BaseHTTPRequestHandler
from zipfile import ZipFile
from io import BytesIO

UPLOAD_FOLDER = "shared_files"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Ask permission once at server start
ALLOW_UPLOADS = input("Give uploading permissions (Y/N): ").strip().lower() == 'y'

def get_lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class CustomHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()

            files = os.listdir(UPLOAD_FOLDER)
            file_links = "".join(
                f'<li><a href="/download/{file}" download>{file}</a></li>' for file in files
            )

            html = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <title>🎉 Personal Server</title>
                <link href="https://fonts.googleapis.com/css2?family=Inter:wght@500;700&display=swap" rel="stylesheet">
                <style>
                    body {{
                        font-family: 'Inter', sans-serif;
                        background-color: #1e1e2f;
                        color: #ffcc00;
                        text-align: center;
                        padding: 30px;
                    }}
                    h1 {{
                        font-size: 2.5em;
                        color: cyan;
                        margin-bottom: 0;
                    }}
                    h2 {{
                        color: orange;
                        margin-top: 2em;
                    }}
                    form {{
                        margin: 10px auto;
                        padding: 20px;
                        background-color: #2b2b3c;
                        border-radius: 12px;
                        max-width: 800px;
                        box-shadow: 0 0 10px rgba(0,0,0,0.3);
                    }}
                    input[type="file"] {{
                        margin: 10px;
                        padding: 6px;
                        color: #fff;
                    }}
                    button {{
                        background-color: #00ffaa;
                        color: #000;
                        padding: 10px 16px;
                        border: none;
                        border-radius: 6px;
                        cursor: pointer;
                        font-weight: bold;
                        transition: background 0.3s ease;
                    }}
                    button:hover {{
                        background-color: #00cc88;
                    }}
                    ul {{
                        list-style: none;
                        padding: 0;
                    }}
                    a {{
                        color: #00ffff;
                        text-decoration: none;
                        font-family: monospace;
                    }}
                    a:hover {{
                        text-decoration: underline;
                    }}
                </style>
            </head>
            <body>
                <h1>🎉 File Sharing Server</h1>
                <p style="color: #ffff88;">🎊 Welcome to your Server! 🎊</p>
        """

            if ALLOW_UPLOADS:
                html += """
                <h2>📤 Upload Files</h2>
                <form method="POST" action="/upload" enctype="multipart/form-data">
                    <input type="file" name="files" multiple required>
                    <button type="submit">Upload Files</button>
                </form>

                <h2>📁 Upload Directory</h2>
                <form method="POST" action="/upload_directory" enctype="multipart/form-data">
                    <input type="file" name="directory" webkitdirectory directory required>
                    <button type="submit">Upload Folder</button>
                </form>
                """

            html += f"""
                <h2>📥 Download (Click to Download)</h2>
                <ul>{file_links or "<li><i>No files yet.</i></li>"}</ul>
            </body>
            </html>
            """

            self.wfile.write(html.encode("utf-8"))

        elif self.path.startswith("/download/"):
            file_name = self.path[len("/download/"):]
            file_path = os.path.join(UPLOAD_FOLDER, file_name)
            if os.path.isfile(file_path):
                try:
                    with open(file_path, "rb") as file:
                        self.send_response(200)
                        self.send_header("Content-Disposition", f"attachment; filename={file_name}")
                        self.send_header("Content-type", "application/octet-stream")
                        self.send_header("Content-Length", str(os.path.getsize(file_path)))
                        self.end_headers()
                        self.wfile.write(file.read())
                except Exception as e:
                    self.send_error(500, f"Error: {e}")
            else:
                self.send_error(404, "File not found")
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        if not ALLOW_UPLOADS:
            self.send_error(403, "Uploading not allowed")
            return

        if self.path == "/upload":
            self.handle_multiple_files_upload()
        elif self.path == "/upload_directory":
            self.handle_directory_upload()

    def handle_multiple_files_upload(self):
        content_length = int(self.headers['Content-Length'])
        boundary = self.headers['Content-Type'].split("boundary=")[1].encode()
        data = self.rfile.read(content_length)
        parts = data.split(b"--" + boundary)

        for part in parts:
            if b"filename=" in part:
                header = part.split(b"\r\n\r\n")[0]
                file_data = part.split(b"\r\n\r\n")[1][:-2]
                file_name = header.split(b'filename="')[1].split(b'"')[0].decode()

                with open(os.path.join(UPLOAD_FOLDER, file_name), "wb") as f:
                    f.write(file_data)

        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        response = """
        <html><body><h1>Files Uploaded Successfully</h1><a href="/">Back</a></body></html>
        """
        self.wfile.write(response.encode("utf-8"))

    def handle_directory_upload(self):
        content_length = int(self.headers['Content-Length'])
        boundary = self.headers['Content-Type'].split("boundary=")[1].encode()
        data = self.rfile.read(content_length)
        parts = data.split(b"--" + boundary)

        for part in parts:
            if b"filename=" in part:
                header = part.split(b"\r\n\r\n")[0]
                file_data = part.split(b"\r\n\r\n")[1][:-2]
                file_name = header.split(b'filename="')[1].split(b'"')[0].decode()

                if file_name.endswith(".zip"):
                    zip_path = os.path.join(UPLOAD_FOLDER, file_name)
                    with open(zip_path, "wb") as f:
                        f.write(file_data)

                    with ZipFile(zip_path, "r") as zip_ref:
                        zip_ref.extractall(UPLOAD_FOLDER)

                    os.remove(zip_path)

        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        response = """
        <html><body><h1>Directory Uploaded Successfully</h1><a href="/">Back</a></body></html>
        """
        self.wfile.write(response.encode("utf-8"))


def main():
    print("=== 🎉 HTTP File Sharing Server ===")
    server_ip = get_lan_ip()
    port = 8000

    httpd = HTTPServer(("0.0.0.0", port), CustomHandler)
    print(f"[+] Server running at http://{server_ip}:{port}")
    print("[+] Share this link with others in your LAN.")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[-] Server stopped.")


if __name__ == "__main__":
    main()
