import socket
import hashlib
import random
import time

CHUNK_SIZE = 32768  # Tamanho de cada chunk em bytes
# Escolher um tamanho de chunk próximo, mas abaixo do MTU, como 1024 bytes.
# Ele evita fragmentação, melhora a confiabilidade da transmissão e mantém a eficiência.
# Esse valor pode ser ajustado dependendo da rede específica, mas sempre considerar o MTU para evitar fragmentação.


def checksum(data):
    """Calcula o checksum dos dados."""
    return hashlib.md5(data).hexdigest()


def start_udp_client(server_ip, server_port):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client_socket.settimeout(2)  # Define timeout para lidar com pacotes perdidos
    # O cliente utiliza timeout para identificar pacotes ausentes.
    # Após o timeout, ele solicita retransmissão dos chunks faltantes ao servidor

    while True:
        filename = input("Digite o nome do arquivo a ser requisitado: ")

        request = f"GET {filename}"
        client_socket.sendto(request.encode(), (server_ip, server_port))

        received_chunks = {}
        missing_chunks = set()
        complete = False

        while not complete:
            try:
                print(f"Aguardando resposta do servidor {server_ip}:{server_port}...\n")
                data, _ = client_socket.recvfrom(2048)
                print(f"Recebido: {data[:30]}\n")
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
                    print(f"Recebendo chunk {chunk_num}\nContendo o texto: {chunk}\n")

                    # Verifica integridade do chunk recebido
                    if checksum(chunk) == chunk_checksum:
                        received_chunks[chunk_num] = chunk
                        # O checksum é utilizado para verificar se os dados de cada pedaço chegaram intactos, sem erros ou corrupção.
                        # Ele permite que o cliente detecte e solicite retransmissão de pedaços com problemas, garantindo a integridade do arquivo final.

                    else:
                        print(f"Erro de checksum no chunk {chunk_num}\n")
                        missing_chunks.add(chunk_num)

            except socket.timeout:
                print("Timeout: aguardando pacotes restantes...")
                complete = True

            # Verifica se há chunks faltantes
            if not complete and received_chunks:
                expected_chunks = max(received_chunks.keys()) + 1
                missing_chunks.update(
                    set(range(expected_chunks)) - set(received_chunks.keys())
                )

            elif not received_chunks:
                print(f"Erro: Não foi possível receber o arquivo '{filename}'.\n")
                continue

        # Pedindo retransmissão para os chunks faltantes
        while missing_chunks:
            print(
                f"Chunks faltantes: {sorted(missing_chunks)}. Solicitando retransmissão...\n"
            )

            retry_request = f"GET {filename}"
            client_socket.sendto(retry_request.encode(), (server_ip, server_port))

            complete = False
            while not complete:
                try:
                    data, _ = client_socket.recvfrom(2048)
                    if data == b"END":
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
                            received_chunks[received_chunk_num] = chunk
                            missing_chunks.remove(received_chunk_num)
                except socket.timeout:
                    print(f"Timeout na retransmissão do chunk {chunk_num}\n")

        # Reconstituindo o arquivo se todos os chunks foram recebidos corretamente
        if not missing_chunks:
            with open(f"recebido_{filename}", "wb") as f:
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
