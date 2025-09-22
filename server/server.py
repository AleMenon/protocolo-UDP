import socket
import struct
import zlib
from pathlib import Path

# --- [PROTOCOLO: Definição de Constantes] ---
# Define as constantes do protocolo que devem ser idênticas às do cliente.
IP_ADDRESS = "localhost"
PORT = 8000
BUFFER_SIZE = 8192 # Tamanho total do datagrama UDP.
# [PROTOCOLO: Mensagens de Controle - Cabeçalho]
# Formato do cabeçalho: '!iI' -> '!' para ordem de rede, 'i' para um inteiro COM sinal
# (necessário para o seq_num -1 de erro), e 'I' para um inteiro SEM sinal para o checksum.
HEADER_FORMAT = '!iI'
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
PAYLOAD_SIZE = BUFFER_SIZE - HEADER_SIZE

#Cria um pacote com cabeçalho e dados.
def create_packet(seq_num, data):
    """
    [PROTOCOLO: Mensagens de Controle - Segmento de Dados e Detecção de Erros]
    Esta função monta um segmento de dados completo. Ela encapsula a lógica de:
    1. Calcular o checksum (CRC32) do payload para garantir a integridade.
    2. Empacotar o número de sequência e o checksum em um cabeçalho binário.
    3. Concatenar o cabeçalho e o payload para formar o datagrama final.
    """
    # [REQUISITO: Detecção de Erros] - Calcula o checksum usando CRC32.
    checksum = zlib.crc32(data)
    # [REQUISITO: Ordenação] - Empacota o número de sequência junto com o checksum.
    header = struct.pack(HEADER_FORMAT, seq_num, checksum)
    return header + data

# Lê o arquivo e o divide em segmentos para envio.
def get_file_chunks(archive):
    """
    [REQUISITO: Segmentação e Tamanho do Buffer]
    Esta função implementa a estratégia de segmentação do arquivo.
    Ela lê o arquivo do disco em pedaços de tamanho fixo (PAYLOAD_SIZE)
    e os armazena em um dicionário, usando o número de sequência como chave.
    """
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

# --- Lógica Principal do Servidor ---
if __name__ == "__main__":
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind((IP_ADDRESS, PORT))
    print(f"Servidor ouvindo em {IP_ADDRESS}:{PORT}")

    while True: # Loop principal para aguardar novas conexões.
        # [REQUISITO: Aguardar conexões/mensagens de clientes]
        message, address = server.recvfrom(BUFFER_SIZE)
        print(f"Recebida mensagem de {address}:{message.decode()}")

        if message.decode().startswith("GET"):
            archive = message.decode().split('/')[1]

            # [REQUISITO: Interpretar as requisições recebidas]
            if not Path(archive).exists():
                # [PROTOCOLO: Mensagens de Controle - Erro]
                # Se o arquivo não existe, envia um pacote especial de erro.
                # O número de sequência -1 foi o escolhido para sinalizar erro.
                print(f"Arquivo '{archive}' não encontrado. Enviando erro para {address}.")
                error_packet = create_packet(-1, b'ERR/FILE_NOT_FOUND')
                server.sendto(error_packet, address)
                continue # Volta a esperar por novas requisições.

            # [REQUISITO: Segmentação] - Inicia a divisão do arquivo.
            print(f"Segmentando o arquivo '{archive}'...")
            file_chunks = get_file_chunks(archive)
            total_chunks = len(file_chunks)
            print(f"Arquivo dividido em {total_chunks} segmentos.")

            # [REQUISITO: Transmissão do Arquivo] - Envia todos os segmentos em uma rajada.
            for seq_num, data in file_chunks.items():
                packet = create_packet(seq_num, data)
                server.sendto(packet, address)

            # [PROTOCOLO: Mensagens de Controle - Fim de Transmissão]
            # Envia um pacote 'END' cujo número de sequência informa ao cliente o total de
            # pacotes. Isso é CRUCIAL para o cliente saber quando parar de esperar.
            end_packet = create_packet(total_chunks, b'END')
            server.sendto(end_packet, address)
            print(f"Todos os {total_chunks} segmentos iniciais foram enviados.")

            # [REQUISITO: Lógica para reenviar segmentos (Retransmissão)]
            # Entra em um loop para aguardar respostas do cliente (ACK ou NACK).
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


