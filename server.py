import random
import socket
import os
import hashlib

CHUNK_SIZE = 1024  # Tamanho de cada chunk em bytes
DISCARD_PROBABILITY = 0.1  # 10% de chance de descartar um chunk (ajustável)


def checksum(data):
    """Calcula o checksum dos dados para verificação de integridade."""
    return hashlib.md5(data).hexdigest()


def read_file_in_chunks(filename, chunk_size=CHUNK_SIZE):
    """Lê o arquivo em chunks de tamanho especificado."""
    with open(filename, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            yield chunk


def start_udp_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind(("0.0.0.0", 5000))
    print("Servidor UDP pronto na porta 5000\n")

    while True:
        message, client_address = server_socket.recvfrom(1024)
        request = message.decode()

        if request.startswith("GET"):
            filename = request.split(" ")[1].strip()
            if os.path.isfile(filename):
                server_socket.sendto("OK".encode(), client_address)
                print(f"Transmitindo o arquivo '{filename}' para {client_address}\n")

                chunk_num = 0
                for chunk in read_file_in_chunks(filename):
                    chunk_checksum = checksum(chunk)

                    packet = f"{chunk_num}%%%{chunk_checksum}&&&".encode() + chunk
                    # Numerar os pedaços é essencial para que o cliente consiga remontá-los na ordem correta e detectar pacotes perdidos.

                    # Adicionando lógica de descarte aleatório para simular perda de pacotes
                    if random.random() < DISCARD_PROBABILITY:
                        print(
                            f"[DESCARTANDO] Chunk {chunk_num} descartado aleatoriamente.\n"
                        )
                        chunk_num += 1
                        continue

                    server_socket.sendto(packet, client_address)
                    chunk_num += 1

                # Indica o fim da transmissão
                server_socket.sendto("END".encode(), client_address)
            else:
                server_socket.sendto(
                    # Se o arquivo não existir, como avisa o cliente?
                    "ERRO: Arquivo não encontrado".encode(),
                    client_address,
                )
                print(
                    f"Arquivo '{filename}' solicitado por {client_address} não encontrado.\n"
                )
        else:
            server_socket.sendto("ERRO: Comando inválido".encode(), client_address)


start_udp_server()
# O que acontece se desligar o servidor durante a transmissão do arquivo e liga-lo depois?
# O cliente ficará em espera até o timeout, e então solicitará retransmissão dos chunks ausentes.
# Porém, se o servidor for reiniciado, ele não terá o estado anterior da transmissão,
# e o cliente precisará reiniciar o pedido do arquivo.
