import random
import socket
import struct
import zlib
import os
import sys
import platform
import subprocess
from pathlib import Path

IP_ADDRESS = "localhost"
PORT = 8000
BUFFER_SIZE = 1024
HEADER_FORMAT = '!iI' # Deve ser o mesmo do servidor
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
PAYLOAD_SIZE = BUFFER_SIZE - HEADER_SIZE

def hangle_get_request(client, address, archive, packets_to_drop):
    temp_archive = f"temp_{archive}.part"
    final_archive = f"client_download_{archive}"

    try:
        request = f"GET /{archive}"
        client.sendto(request.encode(), server_address)
        print(f"Solicitação '{request}' enviada para {server_address}. Aguardando pacotes...")

        total_chunks = -1
        received_seqs = set()
        primeiro_pacote_recebido = False

        with open(temp_archive, "wb") as f:
            while True:
                while True:
                    try:
                        packet, _ = client.recvfrom(BUFFER_SIZE)
                        primeiro_pacote_recebido = True
                        
                        header = packet[:HEADER_SIZE]
                        data = packet[HEADER_SIZE:]
                        seq_num, checksum = struct.unpack(HEADER_FORMAT, header)

                        if seq_num in packets_to_drop:
                            print(f"---! DESCARTANDO PACOTE {seq_num} (SIMULAÇÃO DE PERDA) !---")
                            packets_to_drop.remove(seq_num)
                            continue
                        
                        if zlib.crc32(data) != checksum:
                            print(f"Checksum inválido para o segmento {seq_num}. Descartando.")
                            continue

                        if seq_num == -1 and data.decode().startswith('ERR'):
                            print(f"Erro recebido do servidor: {data.decode()}")
                            f.close()
                            os.remove(temp_archive)
                            return

                        if data == b'END':
                            total_chunks = seq_num
                            print(f"Pacote de Fim de Transmissão (END) recebido. Total de segmentos: {total_chunks}")
                            if total_chunks == 0:
                                print("Arquivo vazio recebido com sucesso.")
                                break
                            continue
                        
                        if seq_num not in received_seqs:
                            f.seek(seq_num * PAYLOAD_SIZE)
                            f.write(data)
                            received_seqs.add(seq_num)

                            if total_chunks > 0:
                                progress = len(received_seqs) / total_chunks * 100
                                sys.stdout.write(f"\rProgresso: {progress:.2f}% ({len(received_seqs)}/{total_chunks})")
                                sys.stdout.flush()

                    except socket.timeout:
                        break
                
                if not primeiro_pacote_recebido:
                    print("\nNenhuma resposta recebida do servidor. Verifique o endereço ou o status do servidor.")
                    return

                if total_chunks != -1 and len(received_seqs) == total_chunks:
                    print("\nTodos os segmentos foram recebidos com sucesso!")
                    client.sendto(b'ACK_SUCCESS', server_address)
                    break
                
                if total_chunks == -1:
                    print("\nPacote final (END) ainda não recebido. Aguardando mais dados...")
                    continue

                expected_seqs = set(range(total_chunks))
                missing_seqs = sorted(list(expected_seqs - received_seqs))

                if missing_seqs:
                    print(f"\nFaltando {len(missing_seqs)} segmentos. Solicitando retransmissão.")
                    nack_message = f"NACK:{','.join(map(str, missing_seqs))}"
                    client.sendto(nack_message.encode(), server_address)
        
        os.rename(temp_archive, final_archive)
        print(f"Arquivo montado e salvo como: '{final_archive}'")

        open_file = input("Deseja abrir o arquivo agora? (s/n): ").lower()
        if open_file == 's':
            try:
                if platform.system() == 'Darwin':
                    subprocess.call(('open', final_archive))
                elif platform.system() == 'Windows':    
                    os.startfile(final_archive)
                else:                                
                    subprocess.call(('xdg-open', final_archive))
            except Exception as e:
                print(f"Não foi possível abrir o arquivo automaticamente: {e}")

    except Exception as e:
        print(f"Ocorreu um erro durante a transferência: {e}")
        if os.path.exists(temp_archive):
            os.remove(temp_archive)

if __name__ == "__main__":
    local_ip = "localhost"
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.bind((IP_ADDRESS, random.randint(8001, 9000)))
    client.settimeout(2.0)

    while True:
        command = input("Digite o comando (@IP:Porta/arquivo ou 'exit'): ")

        if command.startswith("exit"):
            print("Encerrando o cliente.")
            break

        if not command.startswith('@') or '/' not in command or ':' not in command:
            print("Formato inválido. Use: @IP_Servidor:Porta_Servidor/nome_do_arquivo.ext")
            continue
        try:
            address, archive = command.split('/')
            ip_addr, port_str = address.lstrip('@').split(':')
            port = int(port_str)
            server_address = (ip_addr, port)

            loss_input = input("Digite os números dos pacotes a descartar (separados por vírgula, ou deixe em branco): ")
            packets_to_drop = set()
            if loss_input:
                try:
                    packets_to_drop = set(int(s.strip()) for s in loss_input.split(','))
                    print(f"Simulação ativada. Pacotes a serem descartados: {sorted(list(packets_to_drop))}")
                except ValueError:
                    print("Entrada inválida para descarte de pacotes. Ignorando.")

            hangle_get_request(client, server_address, archive, packets_to_drop)

        except ValueError:
            print("Porta inválida. Deve ser um número.")

    client.close()