import random
import socket
import struct
import zlib
from pathlib import Path

IP_ADDRESS = "localhost"
PORT = 8000
BUFFER_SIZE = 1024
HEADER_FORMAT = '!iI' # Deve ser o mesmo do servidor
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
PAYLOAD_SIZE = BUFFER_SIZE - HEADER_SIZE

def hangle_get_request(client, command, archive, address):
    client.sendto(f"{command} /{archive}".encode(), address)
    print(f"Solicitação '{command}' enviada. Aguardando pacotes...")
    
    received_chunks = {}
    total_chunks = -1

    while True:
        while True:
            try:
                packet, _ = client.recvfrom(BUFFER_SIZE)

                header = packet[:HEADER_SIZE]
                data = packet[HEADER_SIZE:]
                seq_num, checksum = struct.unpack(HEADER_FORMAT, header)

                if zlib.crc32(data) != checksum:
                    print(f"Checksum inválido para o segmento {seq_num}. Descartando.")
                    continue

                if seq_num == -1 and data.decode().startswith('ERR'):
                    print(f"Erro recebido do servidor: {data.decode()}")
                    return
                
                if data == b'END':
                    total_chunks = seq_num
                    print(f"Pacote de Fim de Transmissão (END) recebido. Total de segmentos: {total_chunks}")
                    continue

                if seq_num not in received_chunks:
                    received_chunks[seq_num] = data
            except socket.timeout:
                break

        if total_chunks == -1:
            print("Pacote final (END) ainda não recebido. Aguardando mais dados...")
            continue

        if len(received_chunks) == total_chunks:
            print("Todos os segmentos foram recebidos com sucesso!")
            client.sendto(b'ACK_SUCCESS', address)
            break

        expected_seqs = set(range(total_chunks))
        received_seqs = set(received_chunks.keys())
        missing_seqs = sorted(list(expected_seqs - received_seqs))

        if missing_seqs:
            print(f"Faltando {len(missing_seqs)} segmentos. Solicitando retransmissão...")
            nack_message = f"NACK:{','.join(map(str, missing_seqs))}"
            client.sendto(nack_message.encode(), address)

    output_archive = f"client_download_{archive}"
    print(f"Montando o arquivo final: '{output_archive}'")
    with open(output_archive, "wb") as f:
        for i in range(total_chunks):
            f.write(received_chunks[i])


if __name__ == "__main__":
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.bind((IP_ADDRESS, random.randint(8001, 9000)))
    client.settimeout(2.0)

    while True:
        command = input("Digite o tipo de request (ex: GET /file.txt, exit): ")

        if command.lower().startswith("get"):
            parts = command.split()
            if len(parts) != 2:
                print("Formato inválido. Use: GET /nome_do_arquivo")
                continue

            archive = parts[1].strip('/')
            hangle_get_request(client, command, archive, (IP_ADDRESS, PORT))
                    
        elif command.startswith("exit"):
            print("Encerrando o cliente.")
            break

        else:
            print("Comando inválido!")

    client.close()