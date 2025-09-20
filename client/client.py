import socket
import random
from pathlib import Path

IP_ADDRESS = "localhost"
PORT = 8000

if __name__ == "__main__":
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.bind((IP_ADDRESS, random.randint(8001, 9000)))

    while True:
        type = input("Tipo de request: ")

        if type.startswith("POST"):
            archive = input("Arquivo que deseja enviar: ")
            client.sendto(f"{type} /{archive}".encode(), (IP_ADDRESS, PORT))
            with open(archive, "rb") as f:
                while chunk := f.read(1024):
                    client.sendto(chunk, (IP_ADDRESS, PORT))
            client.sendto(b"END", (IP_ADDRESS, PORT))
            print("Arquivo enviado com sucesso!")

        elif type.startswith("GET"):
            archive = input("Arquivo que deseja receber: ")
            client.sendto(f"{type} /{archive}".encode(), (IP_ADDRESS, PORT))
            archive, _ = client.recvfrom(1024)
            with open(archive, "wb") as f:
                while True:
                    data, _ = client.recvfrom(1024)
                    if data == b"END":
                        print("Arquivo recebido com sucesso!")
                        break
                    f.write(data)
                    
        elif type.startswith("exit"):
            exit()

        else:
            print("Entrada inválida!")
            exit()

