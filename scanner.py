import json
import subprocess
import requests
import time
import re
import os
import socket
from datetime import datetime, UTC


REDES = [
    {"rede": "10.0.10.0/24", "vlan": 10},
    {"rede": "10.0.20.0/24", "vlan": 20},
    {"rede": "10.0.30.0/24", "vlan": 30},
    {"rede": "10.0.40.0/24", "vlan": 40},
    {"rede": "10.0.50.0/24", "vlan": 50},
    {"rede": "10.0.60.0/24", "vlan": 60}
]

INTERFACE_SCAN = "ens4"

URL_INVENTORY = "http://10.0.20.10/api/v1/inventory/"
URL_EVENTS = "http://10.0.20.10/api/v1/events/"

ARQUIVO_INVENTARIO = "inventory.json"
ARQUIVO_ESTADO = "estado_rede.json"

TEMPO_ENTRE_SCANS = 60


def agora_iso():
    return datetime.now(UTC).isoformat()


def obter_ip_local():
    resultado = subprocess.run(
        ["ip", "-4", "addr", "show", INTERFACE_SCAN],
        capture_output=True,
        text=True
    )

    match = re.search(
        r"inet\s+(\d+\.\d+\.\d+\.\d+)",
        resultado.stdout
    )

    if match:
        return match.group(1)

    return None


def obter_mac_local():
    resultado = subprocess.run(
        ["ip", "link", "show", INTERFACE_SCAN],
        capture_output=True,
        text=True
    )

    match = re.search(
        r"link/ether\s+([0-9a-f:]+)",
        resultado.stdout,
        re.IGNORECASE
    )

    if match:
        return match.group(1)

    return "Desconhecido"


def descobrir_hosts_rede(rede):
    resultado = subprocess.run(
        ["nmap", "-sn", rede],
        capture_output=True,
        text=True
    )

    hosts = []

    for linha in resultado.stdout.splitlines():
        if "Nmap scan report for" in linha:
            ip = linha.split()[-1]
            ip = ip.replace("(", "").replace(")", "")
            hosts.append(ip)

    return sorted(list(set(hosts)))


def descobrir_hosts():
    hosts = []

    for item in REDES:
        rede = item["rede"]
        vlan = item["vlan"]

        print(f"Descobrindo hosts na rede {rede} VLAN {vlan}...")

        ips = descobrir_hosts_rede(rede)

        for ip in ips:
            hosts.append({
                "ip": ip,
                "vlan": vlan,
                "rede": rede
            })

    return hosts


def obter_hostname(ip):
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return ip


def obter_mac(ip):
    ip_local = obter_ip_local()

    if ip == ip_local:
        return obter_mac_local()

    subprocess.run(
        ["ping", "-c", "1", "-W", "1", ip],
        capture_output=True,
        text=True
    )

    resultado = subprocess.run(
        ["ip", "neigh", "show", ip],
        capture_output=True,
        text=True
    )

    match = re.search(
        r"lladdr\s+([0-9a-f:]+)",
        resultado.stdout,
        re.IGNORECASE
    )

    if match:
        return match.group(1)

    return "Desconhecido"


def descobrir_servicos(ip):
    portas = []
    servicos = []

    resultado = subprocess.run(
        ["nmap", "-Pn", "-T4", "--version-light", "-sV", ip],
        capture_output=True,
        text=True
    )

    for linha in resultado.stdout.splitlines():
        match = re.match(r"^(\d+)/tcp\s+open\s+(\S+)", linha)

        if match:
            porta = int(match.group(1))
            servico = match.group(2)

            portas.append(porta)
            servicos.append(servico)

    return portas, servicos


def descobrir_so(ip):
    resultado = subprocess.run(
        [
            "nmap",
            "-Pn",
            "-T4",
            "-O",
            "--osscan-guess",
            ip
        ],
        capture_output=True,
        text=True
    )

    for linha in resultado.stdout.splitlines():
        if "OS details:" in linha:
            return linha.replace("OS details:", "").strip()

        if "Running:" in linha:
            return linha.replace("Running:", "").strip()

        if "Aggressive OS guesses:" in linha:
            guess = linha.replace(
                "Aggressive OS guesses:",
                ""
            ).strip()

            return guess.split(",")[0].strip()

    return "Desconhecido"


def carregar_estado_anterior():
    if not os.path.exists(ARQUIVO_ESTADO):
        return {"hosts": {}}

    try:
        with open(ARQUIVO_ESTADO, "r") as arquivo:
            return json.load(arquivo)
    except Exception:
        return {"hosts": {}}


def salvar_estado_atual(inventario):
    estado = {
        "updated_at": agora_iso(),
        "hosts": {}
    }

    for host in inventario["hosts"]:
        ip = host["ip_address"]

        estado["hosts"][ip] = {
            "hostname": host["hostname"],
            "mac_address": host["mac_address"],
            "open_ports": host["open_ports"],
            "services": host["services"],
            "os_fingerprint": host["os_fingerprint"],
            "vlan": host["vlan"]
        }

    with open(ARQUIVO_ESTADO, "w") as arquivo:
        json.dump(estado, arquivo, indent=4)


def salvar_inventario(inventario):
    with open(ARQUIVO_INVENTARIO, "w") as arquivo:
        json.dump(inventario, arquivo, indent=4)


def enviar_inventario_para_vm1(host):
    try:
        resposta = requests.post(
            URL_INVENTORY,
            json=host,
            timeout=5
        )

        print(
            f"Inventário {host['ip_address']} "
            f"VLAN {host['vlan']} -> HTTP {resposta.status_code}"
        )

    except Exception as erro:
        print(
            f"Erro ao enviar inventário "
            f"{host['ip_address']}: {erro}"
        )


def enviar_evento(evento):
    try:
        resposta = requests.post(
            URL_EVENTS,
            json=evento,
            timeout=5
        )

        print(
            f"Evento {evento['event_type']} -> "
            f"HTTP {resposta.status_code}"
        )

    except Exception as erro:
        print(f"Erro ao enviar evento: {erro}")


def evento_novo_host(ip, vlan):
    return {
        "description": f"Novo host detectado na VLAN {vlan}: {ip}",
        "event_type": "host_discovered",
        "extra_data": {
            "ip": ip,
            "vlan": vlan,
            "detected_at": agora_iso()
        },
        "severity": "info",
        "source": "vm3-descoberta"
    }


def evento_host_down(ip, vlan):
    return {
        "description": f"Host {ip} não está mais respondendo na VLAN {vlan}",
        "event_type": "host_down",
        "extra_data": {
            "ip": ip,
            "vlan": vlan,
            "detected_at": agora_iso()
        },
        "severity": "critical",
        "source": "vm3-descoberta"
    }


def evento_nova_porta(ip, vlan, porta, servico):
    return {
        "description": f"Nova porta aberta detectada em {ip}: {porta}/{servico}",
        "event_type": "new_open_port",
        "extra_data": {
            "ip": ip,
            "port": porta,
            "service": servico,
            "vlan": vlan,
            "detected_at": agora_iso()
        },
        "severity": "warning",
        "source": "vm3-descoberta"
    }


def gerar_inventario():
    hosts_descobertos = descobrir_hosts()

    inventario = {
        "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "hosts": []
    }

    for item in hosts_descobertos:
        ip = item["ip"]
        vlan = item["vlan"]

        print(f"Escaneando {ip} VLAN {vlan}...")

        portas, servicos = descobrir_servicos(ip)
        so = descobrir_so(ip)
        mac = obter_mac(ip)
        hostname = obter_hostname(ip)

        host = {
            "hostname": hostname,
            "ip_address": ip,
            "mac_address": mac,
            "open_ports": portas,
            "os_fingerprint": so,
            "services": servicos,
            "vlan": vlan
        }

        inventario["hosts"].append(host)

    return inventario


def analisar_mudancas(estado_anterior, inventario_atual):
    hosts_anteriores = set(
        estado_anterior.get("hosts", {}).keys()
    )

    hosts_atuais = set(
        host["ip_address"]
        for host in inventario_atual["hosts"]
    )

    novos_hosts = sorted(list(hosts_atuais - hosts_anteriores))
    hosts_down = sorted(list(hosts_anteriores - hosts_atuais))

    mapa_hosts_atuais = {
        host["ip_address"]: host
        for host in inventario_atual["hosts"]
    }

    for ip in novos_hosts:
        vlan = mapa_hosts_atuais[ip]["vlan"]

        print(f"Novo host detectado: {ip} VLAN {vlan}")

        enviar_evento(
            evento_novo_host(ip, vlan)
        )

    for ip in hosts_down:
        host_antigo = estado_anterior["hosts"].get(ip, {})
        vlan = host_antigo.get("vlan", "desconhecida")

        print(f"Host down detectado: {ip} VLAN {vlan}")

        enviar_evento(
            evento_host_down(ip, vlan)
        )

    for host in inventario_atual["hosts"]:
        ip = host["ip_address"]
        vlan = host["vlan"]

        if ip not in estado_anterior.get("hosts", {}):
            continue

        portas_anteriores = set(
            estado_anterior["hosts"][ip].get("open_ports", [])
        )

        portas_atuais = set(
            host.get("open_ports", [])
        )

        novas_portas = sorted(
            list(portas_atuais - portas_anteriores)
        )

        for porta in novas_portas:
            servico = "desconhecido"

            if porta in host["open_ports"]:
                indice = host["open_ports"].index(porta)

                if indice < len(host["services"]):
                    servico = host["services"][indice]

            print(f"Nova porta detectada em {ip}: {porta}/{servico}")

            enviar_evento(
                evento_nova_porta(ip, vlan, porta, servico)
            )


def executar_scan():
    print("\n======================")
    print(f"[{agora_iso()}] Novo scan iniciado")
    print("======================\n")

    estado_anterior = carregar_estado_anterior()

    inventario = gerar_inventario()

    analisar_mudancas(
        estado_anterior,
        inventario
    )

    print(json.dumps(inventario, indent=4))

    salvar_inventario(inventario)

    for host in inventario["hosts"]:
        enviar_inventario_para_vm1(host)

    salvar_estado_atual(inventario)

    print(f"Hosts encontrados: {len(inventario['hosts'])}")


if __name__ == "__main__":
    try:
        while True:
            executar_scan()

            print(f"\nAguardando {TEMPO_ENTRE_SCANS} segundos...")
            print("Pressione CTRL+C para encerrar o scanner.\n")

            time.sleep(TEMPO_ENTRE_SCANS)

    except KeyboardInterrupt:
        print("\n\nScanner interrompido pelo usuário.")
        print("Encerrando VM3 Discovery de forma segura.\n")
