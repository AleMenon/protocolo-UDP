import random
import socket
import struct
import zlib
import os
import sys
import platform
import subprocess

# --- [PROTOCOLO: Definição de Constantes] ---
# As constantes devem ser idênticas às do servidor para compatibilidade.
IP_ADDRESS = "localhost"
PORT = 8000
BUFFER_SIZE = 8192
HEADER_FORMAT = '!iI' # Deve ser o mesmo do servidor
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
PAYLOAD_SIZE = BUFFER_SIZE - HEADER_SIZE

def handle_get_request(client, server_address, archive, packets_to_drop):
    temp_archive = f"temp_{archive}.part"
    final_archive = f"client_download_{archive}"

    try:
        # [REQUISITO: Enviar uma requisição ao servidor]
        request = f"GET /{archive}"
        client.sendto(request.encode(), server_address)
        print(f"Solicitação '{request}' enviada para {server_address}. Aguardando pacotes...")

        total_chunks = -1
        received_seqs = set()
        primeiro_pacote_recebido = False

        # [REQUISITO: Recepção e Montagem]
        # Abre um arquivo temporário para escrever os dados diretamente no disco.
        # Isso evita consumir memória RAM para arquivos grandes (streaming).
        with open(temp_archive, "wb") as f:
            while True: # Loop externo que controla a lógica de retransmissão.
                while True: # Loop interno que recebe uma rajada de pacotes.
                    try:
                        packet, _ = client.recvfrom(BUFFER_SIZE)
                        primeiro_pacote_recebido = True
                        
                        # Desempacota o cabeçalho para obter o seq_num e o checksum.
                        header = packet[:HEADER_SIZE]
                        data = packet[HEADER_SIZE:]
                        seq_num, checksum = struct.unpack(HEADER_FORMAT, header)

                        # [REQUISITO: Simulação de Perda]
                        # Ponto crucial para testes: descarta intencionalmente pacotes
                        # para forçar e validar a lógica de retransmissão.
                        if seq_num in packets_to_drop:
                            print(f"---! DESCARTANDO PACOTE {seq_num} (SIMULAÇÃO DE PERDA) !---")
                            packets_to_drop.remove(seq_num)
                            continue
                        
                        # [REQUISITO: Verificar a integridade de cada segmento]
                        if zlib.crc32(data) != checksum:
                            print(f"Checksum inválido para o segmento {seq_num}. Descartando.")
                            continue
                        
                        # [REQUISITO: Interpretar e exibir mensagens de erro]
                        if seq_num == -1 and data.decode().startswith('ERR'):
                            print(f"Erro recebido do servidor: {data.decode()}")
                            f.close()
                            os.remove(temp_archive)
                            return

                        # [REQUISITO: Detecção de Perda] - Recebe o pacote 'END'.
                        if data == b'END':
                            total_chunks = seq_num
                            print(f"Pacote de Fim de Transmissão (END) recebido. Total de segmentos: {total_chunks}")
                            if total_chunks == 0:
                                print("Arquivo vazio recebido com sucesso.")
                                break
                            continue
                        
                        # [REQUISITO: Armazenar e ordenar os segmentos]
                        if seq_num not in received_seqs:
                            # Usa f.seek() para pular para a posição correta no arquivo e
                            # escrever o payload. Isso garante a ordem correta.
                            f.seek(seq_num * PAYLOAD_SIZE)
                            f.write(data)
                            received_seqs.add(seq_num)

                            # Barra de progresso para UX.
                            if total_chunks > 0:
                                progress = len(received_seqs) / total_chunks * 100
                                sys.stdout.write(f"\rProgresso: {progress:.2f}% ({len(received_seqs)}/{total_chunks})")
                                sys.stdout.flush()

                    except socket.timeout:
                        break # O timeout indica o fim de uma rajada de pacotes.
                
                # [REQUISITO: Verificação e Finalização] - Lógica pós-timeout.
                if not primeiro_pacote_recebido:
                    print("\nNenhuma resposta recebida do servidor. Verifique o endereço ou o status do servidor.")
                    return

                # Se o arquivo estiver completo, envia o ACK final e encerra.
                if total_chunks != -1 and len(received_seqs) == total_chunks:
                    print("\nTodos os segmentos foram recebidos com sucesso!")
                    client.sendto(b'ACK_SUCCESS', server_address)
                    break
                
                if total_chunks == -1:
                    print("\nPacote final (END) ainda não recebido. Solicitando retransmissão do END...")
                    nack_message = "NACK:END"
                    client.sendto(nack_message.encode(), server_address)
                    continue
                
                # [REQUISITO: Identificar quais segmentos estão faltando]
                expected_seqs = set(range(total_chunks))
                missing_seqs = sorted(list(expected_seqs - received_seqs))

                # Se o pacote END não foi recebido, peça também!
                if total_chunks == -1 or (total_chunks != -1 and len(received_seqs) < total_chunks):
                    # Não sabemos o número do END se total_chunks == -1, então só pedimos retransmissão dos segmentos conhecidos.
                    pass
                elif total_chunks not in received_seqs:
                    # Adiciona o pacote END à lista de faltantes
                    missing_seqs.append(total_chunks)

                # [REQUISITO: Solicitar a retransmissão]
                if missing_seqs:
                    print(f"\nFaltando {len(missing_seqs)} segmentos. Solicitando retransmissão.")
                    nack_message = f"NACK:{','.join(map(str, missing_seqs))}"
                    client.sendto(nack_message.encode(), server_address)
        
        # [REQUISITO: Salvar o arquivo reconstruído localmente]
        os.rename(temp_archive, final_archive)
        print(f"Arquivo montado e salvo como: '{final_archive}'")
        # ... (lógica para abrir o arquivo) ...

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
        # ... (tratamento de exceção) ...
        print(f"Ocorreu um erro durante a transferência: {e}")
        if os.path.exists(temp_archive):
            os.remove(temp_archive)

# --- Lógica Principal do Cliente ---
if __name__ == "__main__":
    local_ip = "localhost"
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.bind((IP_ADDRESS, random.randint(8001, 9000)))
    client.settimeout(2.0)

    while True:
        # [REQUISITO: Permitir que o usuário especifique o endereço IP e a porta]
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

            # [REQUISITO: Implementar uma opção que permita ao cliente descartar]
            loss_input = input("Digite os números dos pacotes a descartar (separados por vírgula, ou deixe em branco): ")
            packets_to_drop = set()
            if loss_input:
                try:
                    packets_to_drop = set(int(s.strip()) for s in loss_input.split(','))
                    print(f"Simulação ativada. Pacotes a serem descartados: {sorted(list(packets_to_drop))}")
                except ValueError:
                    print("Entrada inválida para descarte de pacotes. Ignorando.")

            # Chama a função principal que executa o protocolo.
            handle_get_request(client, server_address, archive, packets_to_drop)

        except ValueError:
            print("Porta inválida. Deve ser um número.")

    client.close()