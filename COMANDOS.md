# Comandos para executar a VM3 Discovery

## Imagem Docker

Imagem no Docker Hub:

```text
https://hub.docker.com/r/danielpmarchesi/vm3labredes
```

Baixar a imagem:

```bash
docker pull danielpmarchesi/vm3labredes:v1
```

---

## Rodar com Docker Compose

Entrar na pasta do projeto:

```bash
cd ~/vm3-discovery
```

Subir o container:

```bash
docker compose up -d
```

Verificar se está rodando:

```bash
docker ps
```

Ver logs do scanner:

```bash
docker logs -f vm3-discovery
```

Ou:

```bash
docker compose logs -f
```

Parar o scanner:

```bash
docker compose down
```

Subir novamente:

```bash
docker compose up -d
```

Reiniciar o container:

```bash
docker restart vm3-discovery
```

---

## Comandos úteis

Ver imagens Docker:

```bash
docker images
```

Ver todos os containers, inclusive parados:

```bash
docker ps -a
```

Ver últimas 100 linhas de log:

```bash
docker logs --tail 100 vm3-discovery
```

Ver últimas 100 linhas e continuar acompanhando:

```bash
docker logs -f --tail 100 vm3-discovery
```

Parar apenas o container:

```bash
docker stop vm3-discovery
```

Iniciar novamente o container parado:

```bash
docker start vm3-discovery
```

Remover o container parado:

```bash
docker rm vm3-discovery
```

---


