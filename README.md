# VM3 Discovery
## Relatório Técnico

O relatório técnico individual do projeto está disponível no arquivo:

https://github.com/DanielPMarchesi/vm3-discovery/blob/b09f97c035a45ef0cd09e4bcd280676b1ddf081a/Relat%C3%B3rio%20T%C3%A9cnico.pdf

Agente de descoberta e monitoramento de rede desenvolvido para a disciplina de Laboratório de Redes.

O projeto tem como objetivo criar uma VM responsável por escanear redes/VLANs, identificar hosts ativos, portas abertas, serviços, fingerprint de sistema operacional e enviar os dados coletados para um servidor central, chamado VM1.

---

## Visão Geral

A **VM3 Discovery** atua como um agente de coleta dentro da rede. Ela executa varreduras periódicas utilizando Python e Nmap, gera um inventário em formato JSON e envia os resultados para uma API REST hospedada na VM1.

O sistema também compara o estado atual da rede com o estado anterior, permitindo detectar alterações como:

* novos hosts descobertos;
* hosts que deixaram de responder;
* novas portas abertas;
* serviços identificados;
* fingerprint aproximado do sistema operacional.

---

## Arquitetura do Projeto

A arquitetura do projeto é composta por duas funções principais:

### VM1 — Servidor Central

A VM1 é responsável por receber e armazenar os dados enviados pela VM3.

Endpoints utilizados:

```text
http://10.0.20.10/api/v1/inventory/
http://10.0.20.10/api/v1/events/
```

O endpoint de inventário recebe os dados dos hosts encontrados.
O endpoint de eventos recebe alterações detectadas entre uma varredura e outra.

### VM3 — Agente de Descoberta

A VM3 executa o scanner da rede.

Tecnologias utilizadas:

* Ubuntu Server;
* Python 3;
* Nmap;
* Requests;
* Docker;
* Docker Compose.

---

## Configuração de Rede da VM3

A VM3 foi configurada com duas interfaces de rede:

```text
ens3 -> rede externa / SSH / acesso administrativo
ens4 -> rede interna / VLAN 40 / rede monitorada
```

Exemplo de configuração utilizada:

```text
ens3 -> 192.168.10.187/24
ens4 -> 10.0.40.40/24
gateway interno -> 10.0.40.1
```

A rota padrão foi configurada pela interface `ens4`, permitindo que a VM3 acesse as VLANs internas por meio do gateway `10.0.40.1`.

Para manter o acesso SSH funcionando pela interface externa, foi adicionada uma rota específica:

```bash
sudo ip route replace 10.10.0.0/16 via 192.168.10.1 dev ens3
```

---

## Redes Monitoradas

O scanner foi preparado para percorrer múltiplas VLANs.

Configuração atual:

```python
REDES = [
    {"rede": "10.0.10.0/24", "vlan": 10},
    {"rede": "10.0.20.0/24", "vlan": 20},
    {"rede": "10.0.30.0/24", "vlan": 30},
    {"rede": "10.0.40.0/24", "vlan": 40},
    {"rede": "10.0.50.0/24", "vlan": 50},
    {"rede": "10.0.60.0/24", "vlan": 60}
]
```

Para adicionar uma nova VLAN, basta inserir uma nova entrada na lista `REDES`.

---

## Funcionamento do Scanner

O scanner executa continuamente. A cada ciclo, ele:

1. percorre todas as redes configuradas;
2. descobre hosts ativos;
3. identifica portas abertas;
4. identifica serviços;
5. tenta identificar o sistema operacional;
6. coleta hostname e MAC quando possível;
7. gera inventário em JSON;
8. compara com o estado anterior;
9. gera eventos de mudança;
10. envia inventário e eventos para a VM1;
11. aguarda 60 segundos;
12. inicia uma nova varredura.

O loop principal segue a lógica:

```python
while True:
    executar_scan()
    time.sleep(60)
```

---

## Descoberta de Hosts

A descoberta de hosts ativos é feita com o Nmap:

```bash
nmap -sn REDE
```

Exemplo:

```bash
nmap -sn 10.0.40.0/24
```

A opção `-sn` permite identificar quais hosts estão ativos sem executar varredura de portas nesse momento.

---

## Descoberta de Portas e Serviços

Após identificar os hosts ativos, o scanner executa uma nova varredura para descobrir portas abertas e serviços:

```bash
nmap -Pn -T4 -sV IP
```

Exemplo:

```bash
nmap -Pn -T4 -sV 10.0.40.1
```

Significado das opções:

```text
-Pn -> considera o host ativo e evita nova descoberta ICMP
-T4 -> aumenta a velocidade do scan
-sV -> identifica serviços e versões
```

---

## Fingerprint de Sistema Operacional

A tentativa de identificação do sistema operacional é feita com:

```bash
nmap -O --osscan-guess IP
```

O Nmap analisa características das respostas TCP/IP do host, como TTL, flags TCP, janela TCP e respostas ICMP.

Exemplo de resultado:

```json
"os_fingerprint": "Linux 4.15 (96%)"
```

Quando o sistema operacional não pode ser identificado, o campo é preenchido como:

```json
"os_fingerprint": "Desconhecido"
```

---

## Hostname e MAC Address

O scanner tenta identificar o hostname por DNS reverso usando Python:

```python
socket.gethostbyaddr(ip)
```

Quando não existe registro DNS reverso, o próprio IP é usado como hostname.

Exemplo:

```json
"hostname": "10.0.60.10"
```

A descoberta de MAC é feita usando informações locais e a tabela de vizinhança do Linux:

```bash
ip neigh show IP
```

Entretanto, o MAC address só pode ser obtido diretamente para hosts da mesma VLAN da VM3. Isso ocorre porque ARP não atravessa roteadores.

Por isso, em hosts de outras VLANs, o inventário pode apresentar:

```json
"mac_address": "Desconhecido"
```

Esse comportamento é esperado em redes roteadas.

---

## Exemplo de Inventário Gerado

```json
{
  "timestamp": "2026-06-25T21:01:55Z",
  "hosts": [
    {
      "hostname": "vm3-descoberta",
      "ip_address": "10.0.40.40",
      "mac_address": "fa:16:3e:9d:43:e2",
      "open_ports": [22],
      "os_fingerprint": "Linux 2.6.X|5.X",
      "services": ["ssh"],
      "vlan": 40
    }
  ]
}
```

---

## Eventos Implementados

O scanner detecta alterações entre o scan atual e o estado anterior.

Eventos implementados:

```json
{
  "event_type": "host_discovered"
}
```

```json
{
  "event_type": "host_down"
}
```

```json
{
  "event_type": "new_open_port"
}
```

O estado anterior da rede é armazenado em:

```text
estado_rede.json
```

---

## Estrutura do Projeto

```text
vm3-discovery/
├── scanner.py
├── events.py
├── Dockerfile
├── docker-compose.yml
├── COMANDOS.md
├── estado_rede.json
├── hosts_anteriores.json
├── inventory.json
└── README.md
```

Descrição dos principais arquivos:

```text
scanner.py            Código principal do scanner
events.py             Funções relacionadas a eventos
Dockerfile            Arquivo de construção da imagem Docker
docker-compose.yml    Arquivo para execução com Docker Compose
COMANDOS.md           Comandos úteis para execução
estado_rede.json      Estado anterior da rede
inventory.json        Inventário gerado
```

---

## Executando o Projeto

### 1. Clonar o repositório

```bash
gh repo clone DanielPMarchesi/vm3-discovery
cd vm3-discovery
```

Ou usando Git:

```bash
git clone https://github.com/DanielPMarchesi/vm3-discovery.git
cd vm3-discovery
```

---

### 2. Baixar a imagem Docker

```bash
docker pull danielpmarchesi/vm3labredes:v1
```

---

### 3. Executar com Docker Compose

```bash
docker compose up -d
```

Se estiver usando usuário comum, utilize:

```bash
sudo docker compose up -d
```

---

### 4. Verificar se o container está rodando

```bash
docker ps
```

O container esperado é:

```text
vm3-discovery
```

---

### 5. Visualizar os logs

```bash
docker logs -f vm3-discovery
```

Nos logs, deve aparecer algo semelhante a:

```text
Novo scan iniciado
Descobrindo hosts na rede 10.0.10.0/24 VLAN 10...
Descobrindo hosts na rede 10.0.20.0/24 VLAN 20...
Descobrindo hosts na rede 10.0.30.0/24 VLAN 30...
Descobrindo hosts na rede 10.0.40.0/24 VLAN 40...
Descobrindo hosts na rede 10.0.50.0/24 VLAN 50...
Descobrindo hosts na rede 10.0.60.0/24 VLAN 60...
Hosts encontrados: 15
Aguardando 60 segundos...
```

Para sair dos logs sem parar o container:

```text
CTRL + C
```

---

## Docker Compose

Exemplo de `docker-compose.yml`:

```yaml
services:
  vm3-discovery:
    image: danielpmarchesi/vm3labredes:v1
    container_name: vm3-discovery
    network_mode: host
    privileged: true
    restart: unless-stopped
    environment:
      - PYTHONUNBUFFERED=1
```

A opção `network_mode: host` é importante porque o scanner precisa acessar diretamente a rede da VM.

A opção `privileged: true` é utilizada para permitir que o Nmap execute operações de rede com permissões adequadas.

---

## Comandos Úteis

Ver interfaces de rede:

```bash
ip a
```

Ver tabela de rotas:

```bash
ip route
```

Ver rota até a internet:

```bash
ip route get 8.8.8.8
```

Ver rota até outra VLAN:

```bash
ip route get 10.0.60.10
```

Testar conectividade com gateway interno:

```bash
ping -c 4 10.0.40.1
```

Testar conectividade com a VM1:

```bash
ping -c 4 10.10.1.2
```

Ver imagens Docker:

```bash
docker images
```

Ver containers em execução:

```bash
docker ps
```

Parar o container:

```bash
docker compose down
```

---

## Limitações Conhecidas

Algumas limitações são esperadas no funcionamento do scanner:

* O MAC address pode aparecer como `Desconhecido` em hosts fora da VLAN da VM3;
* ARP não atravessa roteadores;
* O hostname pode aparecer como IP quando não existe DNS reverso configurado;
* O fingerprint do sistema operacional pode falhar em hosts com firewall ou poucas portas abertas;
* A identificação de serviços depende das respostas obtidas pelo Nmap;
* Rotas adicionadas manualmente com `ip route replace` podem ser perdidas após reinicialização, se não forem persistidas no Netplan.

---

## Possíveis Melhorias Futuras

* Criar tabela auxiliar de hostname para IPs conhecidos;
* Criar tabela auxiliar de IP para MAC usando dados do OpenStack;
* Consultar o gateway ou OpenStack para obter MACs de outras VLANs;
* Persistir rotas diretamente no Netplan;
* Melhorar tratamento de erros nas requisições HTTP;
* Criar arquivo `.env` para configuração dos endpoints;
* Adicionar autenticação nas requisições para VM1;
* Criar dashboard com quantidade de hosts, serviços e eventos;
* Automatizar build e push da imagem Docker.

---

## Uso de IA

Durante o desenvolvimento do projeto, foi utilizada IA generativa como ferramenta de apoio para:

* esclarecimento de conceitos de redes;
* interpretação de comandos Linux;
* explicação do funcionamento do Nmap;
* auxílio na estruturação do código Python;
* apoio na configuração com Docker;
* apoio na documentação do projeto.

Todas as configurações, testes e validações foram executados no ambiente real da VM3.

---

## Autor

**Daniel Prezotti Marchesi**
Curso de Engenharia Elétrica
Instituto Federal do Espírito Santo — IFES

---

## Referências

* Nmap — The Network Mapper: https://nmap.org
* Docker Documentation: https://docs.docker.com
* Docker Compose Documentation: https://docs.docker.com/compose
* Ubuntu Netplan Documentation: https://netplan.io
