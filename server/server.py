import socket
from pathlib import Path

IP_ADDRESS = "localhost"
PORT = 8000

if __name__ == "__main__":
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind((IP_ADDRESS, PORT))
    while True:
        message, address = server.recvfrom(1024)
        if message.decode().startswith("POST"):
            archive = message.decode().split('/')[1]
            with open(archive, "wb") as f:
                while True:
                    data, _ = server.recvfrom(1024)
                    if data == b"END":
                        break
                    f.write(data)

        elif message.decode().startswith("GET"):
            archive = message.decode().split('/')[1]
            if Path(archive).exists():
                server.sendto(archive.encode(), address)
                with open(archive, "rb") as f:
                    while chunk := f.read(1024):
                        server.sendto(chunk, address)
                server.sendto(b"END", address)
