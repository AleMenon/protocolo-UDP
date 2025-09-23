import socket
import struct
import zlib
from pathlib import Path

# --- [PROTOCOLO: Definição de Constantes] ---
IP_ADDRESS = "localhost"
PORT = 8000
BUFFER_SIZE = 8192
# [PROTOCOLO: Mensagens de Controle - Cabeçalho]
HEADER_FORMAT = '!iI'
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
PAYLOAD_SIZE = BUFFER_SIZE - HEADER_SIZE

def create_packet(seq_num, data):
    # [REQUISITO: Detecção de Erros]
    checksum = zlib.crc32(data)
    # [REQUISITO: Ordenação]
    header = struct.pack(HEADER_FORMAT, seq_num, checksum)
    return header + data

def get_file_chunks(archive):
    chunks = {}
    seq_num = 0
    with open(archive, "rb") as f:
        while True:
            data = f.read(PAYLOAD_SIZE)
            if not data:
                break
            chunks[seq_num] = data
            seq_num += 1
    return chunks

if __name__ == "__main__":
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind((IP_ADDRESS, PORT))
    print(f"Servidor ouvindo em {IP_ADDRESS}:{PORT}")

    while True:
        # [REQUISITO: Aguardar conexões/mensagens de clientes]
        message, address = server.recvfrom(BUFFER_SIZE)
        print(f"Recebida mensagem de {address}:{message.decode()}")

        if message.decode().startswith("GET"):
            archive = message.decode().split('/')[1]

            # [REQUISITO: Interpretar as requisições recebidas]
            if not Path(archive).exists():
                # [PROTOCOLO: Mensagens de Controle - Erro]
                print(f"Arquivo '{archive}' não encontrado. Enviando erro para {address}.")
                error_packet = create_packet(-1, b'ERR/FILE_NOT_FOUND')
                server.sendto(error_packet, address)
                continue

            # [REQUISITO: Segmentação]
            print(f"Segmentando o arquivo '{archive}'...")
            file_chunks = get_file_chunks(archive)
            total_chunks = len(file_chunks)
            print(f"Arquivo dividido em {total_chunks} segmentos.")

            # [REQUISITO: Transmissão do Arquivo]
            for seq_num, data in file_chunks.items():
                packet = create_packet(seq_num, data)
                server.sendto(packet, address)

            # [PROTOCOLO: Mensagens de Controle - Fim de Transmissão]
            end_packet = create_packet(total_chunks, b'END')
            server.sendto(end_packet, address)
            print(f"Todos os {total_chunks} segmentos iniciais foram enviados.")

            # [REQUISITO: Lógica para reenviar segmentos (Retransmissão)]
            while True:
                response, _ = server.recvfrom(BUFFER_SIZE)
                decoded = response.decode()

                if decoded == 'ACK_SUCCESS':
                    print(f"Cliente confirmou o recebimento completo de '{archive}'. Transação finalizada.")
                    break

                if decoded == 'NACK:END':
                    server.sendto(end_packet, address)
                    print("Reenviando pacote END a pedido do cliente.")
                    continue

                if decoded.startswith('NACK:'):
                    missing_seqs_str = decoded.split(':', 1)[1]
                    missing_seqs = [int(s) for s in missing_seqs_str.split(',') if s]
                    print(f"Cliente solicitou retransmissão de {len(missing_seqs)} segmentos: {missing_seqs}")

                    for seq_num in missing_seqs:
                        if seq_num in file_chunks:
                            packet = create_packet(seq_num, file_chunks[seq_num])
                            server.sendto(packet, address)
                    server.sendto(end_packet, address)
                    print("Segmentos de retransmissão enviados.")


