from os import system
import socket
import hashlib
import random
import time

CHUNK_SIZE = 512  # Tamanho de cada chunk em bytes
# Escolher um tamanho de chunk próximo, mas abaixo do MTU, como 512 bytes.
# Ele evita fragmentação, melhora a confiabilidade da transmissão e mantém a eficiência.
# Esse valor pode ser ajustado dependendo da rede específica, mas sempre considerar o MTU para evitar fragmentação.

RECONNECT_INTERVAL = 5  # Tempo em segundos entre tentativas de reconexão


def checksum(data):
    """Calcula o checksum dos dados."""
    return hashlib.md5(data).hexdigest()


def start_udp_client(server_ip, server_port):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client_socket.settimeout(2)  # Define timeout para lidar com pacotes perdidos
    # O cliente utiliza timeout para identificar pacotes ausentes.
    # Após o timeout, ele solicita retransmissão dos chunks faltantes ao servidor

    def wait_for_server():
        """Aguarda até que o servidor esteja disponível."""
        print("Aguardando o servidor estar disponível...")
        while True:
            try:
                # Tentar enviar um pacote vazio para checar se o servidor está online
                client_socket.sendto(b"PING", (server_ip, server_port))
                client_socket.recvfrom(1024)  # Tentar receber uma resposta
                print("Servidor disponível! Continuando...")
                break
            except socket.timeout:
                print(
                    f"Servidor não respondeu, tentando novamente em {RECONNECT_INTERVAL} segundos..."
                )
                time.sleep(RECONNECT_INTERVAL)
            except socket.error:
                print(
                    f"Erro de conexão. Tentando novamente em {RECONNECT_INTERVAL} segundos..."
                )
                time.sleep(RECONNECT_INTERVAL)

    wait_for_server()  # Verifica se o servidor está online antes de continuar

    while True:
        filename = input("Digite o nome do arquivo a ser requisitado: ")

        request = f"GET {filename}"
        client_socket.sendto(request.encode(), (server_ip, server_port))

        received_chunks = {}
        missing_chunks = []
        complete = False

        received_nums = []

        while not complete:
            try:
                data, _ = client_socket.recvfrom(1024)
                if data == b"END":
                    print("Transferência do arquivo concluída.\n")
                    complete = True
                    break
                elif data.startswith(b"ERRO"):
                    print(data.decode())
                    break
                elif data.startswith(b"OK"):
                    print(
                        f"Arquivo '{filename}' encontrado, iniciando transferência...\n"
                    )
                else:
                    # Extraindo número do chunk e checksum do cabeçalho
                    header, chunk = data.split(b"&&&")
                    chunk_num, chunk_checksum = header.decode().split(r"%%%")
                    chunk_num = int(chunk_num)
                    print(f"Recebendo chunk {chunk_num}\n")

                    # Verifica integridade do chunk recebido
                    if checksum(chunk) == chunk_checksum:
                        received_chunks[chunk_num] = chunk
                        # O checksum é utilizado para verificar se os dados de cada pedaço chegaram intactos,
                        # sem erros ou corrupção. Ele permite que o cliente detecte e solicite retransmissão
                        # de pedaços com problemas, garantindo a integridade do arquivo final.
                        received_nums.append(chunk_num)

            except socket.timeout:
                # Quando ocorre timeout, tenta se reconectar
                print("Timeout: servidor não respondeu. Tentando reconectar...")
                while True:
                    try:
                        client_socket.sendto(request.encode(), (server_ip, server_port))
                        break
                    except socket.error:
                        print(
                            f"Reconexão falhou, tentando novamente em {RECONNECT_INTERVAL} segundos..."
                        )
                        time.sleep(RECONNECT_INTERVAL)
                continue

        # Verifica se há chunks faltantes
        if received_chunks:
            for i in range(received_nums[-1]):
                if i not in received_nums:
                    missing_chunks.append(i)
        else:
            print(f"ERRO: Não foi possível receber o arquivo '{filename}'.\n")
            continue

        # Pedindo retransmissão para os chunks faltantes
        while missing_chunks:
            print(
                f"Chunks faltantes: {missing_chunks}.\nSolicitando retransmissão...\n"
            )
            retry_request = f"GET2 {filename}"
            client_socket.sendto(retry_request.encode(), (server_ip, server_port))

            complete = False
            while not complete:
                try:
                    data, _ = client_socket.recvfrom(2048)
                    if data == b"END":
                        print("Transferência do arquivo concluída.\n")
                        complete = True
                    elif data.startswith(b"ERRO"):
                        print(data.decode())
                        break
                    elif data.startswith(b"OK"):
                        continue
                    else:
                        header, chunk = data.split(b"&&&", 2)
                        received_chunk_num, chunk_checksum = header.decode().split(
                            r"%%%"
                        )
                        received_chunk_num = int(received_chunk_num)

                        # Verifica se o chunk é o esperado e se passou no checksum
                        if (
                            received_chunk_num in missing_chunks
                            and checksum(chunk) == chunk_checksum
                        ):
                            print(f"Recebendo chunk {received_chunk_num}\n")
                            received_chunks[received_chunk_num] = chunk
                            received_nums.append(received_chunk_num)
                            missing_chunks.remove(received_chunk_num)
                except socket.timeout:
                    # Quando ocorre timeout, tenta se reconectar
                    print("Timeout: servidor não respondeu. Tentando reconectar...")
                    while True:
                        try:
                            client_socket.sendto(
                                request.encode(), (server_ip, server_port)
                            )
                            break
                        except socket.error:
                            print(
                                f"Reconexão falhou, tentando novamente em {RECONNECT_INTERVAL} segundos..."
                            )
                            time.sleep(RECONNECT_INTERVAL)
                    continue

        # Reconstituindo o arquivo se todos os chunks foram recebidos corretamente
        if not missing_chunks:
            with open(f"received_files/recebido_{filename}", "wb") as f:
                for chunk_num in sorted(received_chunks):
                    f.write(received_chunks[chunk_num])
            print(f"Arquivo '{filename}' recebido e montado com sucesso.\n")
        else:
            print(
                f"Erro: Não foi possível receber todos os chunks do arquivo '{filename}'.\n"
            )


start_udp_client("127.0.0.1", 5000)
# Cliente UDP pode executar antes do servidor?
# Sim, mas o cliente ficará esperando sem resposta até que o servidor esteja ativo para atender as requisições.
