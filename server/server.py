import socket
from pathlib import Path

IP_ADDRESS = "localhost"
PORT = 8000
BUFFER_SIZE = 1024

if __name__ == "__main__":
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind((IP_ADDRESS, PORT))
    print(f"Servidor ouvindo em {IP_ADDRESS}:{PORT}")
    while True:
        message, address = server.recvfrom(BUFFER_SIZE)
        print(f"Recebida mensagem de {address}:{message.decode()}")
        if message.decode().startswith("POST"):
            archive = message.decode().split('/')[1]
            print(f"Recebendo arquivo '{archive}' de {address}...")
            with open(archive, "wb") as f:
                while True:
                    data, _ = server.recvfrom(BUFFER_SIZE)
                    if data == b"END":
                        break
                    f.write(data)

        elif message.decode().startswith("GET"):
            archive = message.decode().split('/')[1]
            if Path(archive).exists():
                print(f"Enviando arquivo '{archive}' para {address}...")
                server.sendto(archive.encode(), address)
                with open(archive, "rb") as f:
                    while chunk := f.read(BUFFER_SIZE):
                        server.sendto(chunk, address)
                server.sendto(b"END", address)
                print(f"Arquivo '{archive}' enviado com sucesso.")
            else:
                print(f"Arquivo '{archive}' não encontrado. Enviando erro para {address}.")
                server.sendto("ERR/NAO_ENCONTRADO".encode(), address)
