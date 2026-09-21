import socket
import base64
import os

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
try:
    s.connect(('8.8.8.8', 80))
    ip = s.getsockname()[0]
except Exception:
    ip = '127.0.0.1'
finally:
    try:
        s.close()
    except Exception:
        pass

key = base64.urlsafe_b64encode(os.urandom(32)).decode()
print(ip)
print(key)
