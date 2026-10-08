# Youtube Downloader

A web application for downloading YouTube videos and audio through your browser. Paste a video URL, choose an available resolution or audio quality, and save the file to your computer. Audio downloads are converted to MP3.

The image includes the application, `yt-dlp`, and `ffmpeg`.

Source code: [balanila/youtubedl on GitHub](https://github.com/balanila/youtubedl).

## Supported Platforms

Images are available for Linux x86_64 (`linux/amd64`) and ARM64 (`linux/arm64`), including Macs with Apple Silicon. On macOS, install and start Docker Desktop before running the commands below. Docker automatically selects the correct image architecture; both platforms use the same version tags and `latest`.

## Start with Docker

Install Docker and run:

```bash
docker run --detach \
  --name youtubedl \
  --publish 127.0.0.1:8000:8000 \
  --restart unless-stopped \
  balanial/youtubedl:latest
```

Open **http://localhost:8000** in a browser on the machine running Docker.

## Start with Docker Compose

Save this as `compose.yml`:

```yaml
services:
  youtubedl:
    image: balanial/youtubedl:latest
    ports:
      - "127.0.0.1:8000:8000"
    restart: unless-stopped
```

Start the application:

```bash
docker compose up -d
```

Open **http://localhost:8000**. To use a specific release, replace `latest` with its version tag.

## Run Behind a Reverse Proxy

For a server with a reverse proxy connected to the Docker network `web`, create the network if it does not already exist:

```bash
docker network create web
```

Start the container on that network:

```bash
docker run --detach \
  --name youtubedl \
  --network web \
  --restart unless-stopped \
  balanial/youtubedl:latest
```

Configure the proxy's upstream as **http://youtubedl:8000** and open the URL configured in your proxy. This setup does not publish a port on the host. Use one of these startup methods at a time; the Docker commands use the same container name.

## Download a Video or Audio

1. Paste a YouTube video URL into the URL field.
2. Click **Show formats**.
3. Select **Video** or **Audio**.
4. Click **Download** next to the desired quality.
5. Wait for the application to prepare the file, then save it using your browser.

Available formats depend on the video. Large videos and audio conversion can take some time. Temporary files are removed after transfer to the browser; no persistent volume is required. Allow enough free disk space for downloads and conversion.

## Update and Stop

For the Docker Compose setup, update to the latest image with:

```bash
docker compose pull
docker compose up -d
```

Stop and remove the Compose containers with `docker compose down`.

For a container started with `docker run`, stop it with `docker stop youtubedl`. To update it, run `docker pull balanial/youtubedl:latest`, remove the stopped container with `docker rm youtubedl`, and repeat your chosen startup command. Updates interrupt active downloads.

Some YouTube videos require authentication or cookies; cookie configuration is not currently supported. Only download content you own or have permission to download.
