import socket
import random
from pathlib import Path

IP_ADDRESS = "localhost"
PORT = 8000
BUFFER_SIZE = 1024

if __name__ == "__main__":
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.bind((IP_ADDRESS, random.randint(8001, 9000)))

    while True:
        command = input("Digite o tipo de request (ex: GET /file.txt, POST /file.txt, exit): ")

        if command.lower().startswith("post"):
            parts = command.split()
            if len(parts) != 2:
                print("Formato inválido. Use: POST /caminho/do/arquivo")
                continue

            archive = Path(parts[1].strip('/'))
            if not archive.exists():
                print(f"Erro: Arquivo '{archive}' não encontrado.")
                continue

            client.sendto(f"{command} /{archive}".encode(), (IP_ADDRESS, PORT))
            print(f"Enviando arquivo '{archive}'...")
            with open(archive, "rb") as f:
                while chunk := f.read(BUFFER_SIZE - 20):
                    client.sendto(chunk, (IP_ADDRESS, PORT))
            client.sendto(b"END", (IP_ADDRESS, PORT))
            print("Arquivo enviado com sucesso!")

        elif command.lower().startswith("get"):
            parts = command.split()
            if len(parts) != 2:
                print("Formato inválido. Use: GET /nome_do_arquivo")
                continue

            archive = parts[1].strip('/')
            client.sendto(f"{command} /{archive}".encode(), (IP_ADDRESS, PORT))
            print("Aguardando resposta do servidor...")
            archive, _ = client.recvfrom(BUFFER_SIZE)
            if archive.decode().lower().startswith("err"):
                print(f"Erro do servidor: {archive.decode()}")
            else:
                print(f"Recebendo arquivo: {archive.decode()}")
                with open(archive, "wb") as f:
                    while True:
                        data, _ = client.recvfrom(BUFFER_SIZE)
                        if data == b"END":
                            print("Arquivo recebido com sucesso!")
                            break
                        f.write(data)
                    
        elif command.startswith("exit"):
            print("Encerrando o cliente.")
            break

        else:
            print("Comando inválido!")

    client.close()