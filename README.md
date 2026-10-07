# Youtube Downloader

A Dockerized web application for downloading YouTube videos and audio. Paste a YouTube URL, choose a video resolution or audio format, and download the file to your browser. Temporary files are deleted after transmission.

## Quick Start

Install Docker with the Docker Compose plugin.

The external Docker network `web` must already exist. If it does not exist, create it once with `docker network create web`.

Start the application:

```bash
docker compose up --build
```

Connect your reverse proxy to the Docker network `web` and configure its upstream as `http://youtubedl:8000`. Open the application using the URL configured in your reverse proxy. Port `8000` is internal to the container and is not published on the host.

## Supported Architectures

The Docker image can be built on Linux x86_64 and Apple Silicon (arm64). Docker selects the appropriate architecture from the multi-platform `python:3.12-slim` base image.

To build and push an image for both architectures, replace the registry placeholder and run:

```bash
docker buildx build --platform linux/amd64,linux/arm64 -t your-registry/youtubedl:latest --push .
```

To build a local image, choose the command matching your machine's architecture:

```bash
docker buildx build --platform linux/arm64 -t youtubedl:local --load .
docker buildx build --platform linux/amd64 -t youtubedl:local --load .
```

## GitHub Actions: Deploy to Your Server

The workflow in `.github/workflows/deploy.yml` runs on pushes to `main`. To trigger it manually, select the deployment workflow in **Actions**, click **Run workflow**, and select `main`.

Install a self-hosted GitHub Actions runner on your Linux server. Set `jobs.deploy.runs-on` in `.github/workflows/deploy.yml` to match your runner's labels, for example:

```yaml
runs-on: [self-hosted, linux]
```

Install Bash and Docker on the server, and ensure the runner user can access the server's Docker daemon. If the runner itself runs in a container, it needs the Docker CLI and access to the host's Docker daemon. Keep the GitHub Actions runner up to date to meet the [requirements for `actions/checkout@v6`](https://github.com/actions/checkout#whats-new).

The pipeline builds `youtubedl:<commit SHA>` directly on the runner, replaces the `youtubedl` container using `docker run`, and checks that the application responds over HTTP inside the container. Deployment does not use Docker Compose and requires no container registry or secrets. Access the application through your reverse proxy; port `8000` is not published on the server.

The container joins the existing Docker network `web` at startup. Create this network on your server before the first deployment if needed: `docker network create web`. The workflow checks that the network exists before stopping the current container. Connect your reverse proxy to this network and configure its upstream as `http://youtubedl:8000`.

Downloads are temporarily stored in `/data/downloads` inside the container. Each download's temporary directory is deleted after transmission to the browser, including when transmission fails or the connection is interrupted. No persistent volume is used. Replacing the container also removes files left behind by a process crash.

The container uses `--restart unless-stopped`, and deployments run one at a time. Replacing the container causes brief downtime and may interrupt active downloads. If the startup check fails, the workflow prints container logs and exits with an error. There is no automatic rollback.

After a successful deployment check, the workflow removes older `youtubedl` images that are no longer used by any container. The deployed image and images used by running or stopped containers are kept. Images belonging to other applications are unaffected.

## GitLab CI

The GitLab pipeline publishes a multi-platform image to `balanial/yourubedl` on Docker Hub when a SemVer Git tag is pushed:

```bash
git tag v1.0.0
git push origin v1.0.0
```

Set these GitLab CI/CD variables:

- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN`

The runner tagged `docker` must support Docker-in-Docker in privileged mode because the build registers QEMU/binfmt handlers inside the job.

For the Git tag `v1.2.3`, the pipeline publishes these Docker tags:

- `balanial/yourubedl:1.2.3`
- `balanial/yourubedl:1.2`
- `balanial/yourubedl:1`
- `balanial/yourubedl:latest`

## How It Works

- **Backend:** FastAPI.
- **Video information and downloads:** `yt-dlp`.
- **Merging video and audio, and converting audio to MP3:** `ffmpeg`.
- **Temporary storage:** `/data/downloads` in Docker, or `app/downloads` when running outside Docker. Temporary directories are removed after transmission; download and transmission errors also trigger cleanup.
- **Updates:** `yt-dlp` is not pinned to a specific version so image rebuilds can pick up fixes for YouTube changes. If available formats stop appearing, rebuild the image with fresh dependencies. For Docker Compose:

  ```bash
  docker compose build --no-cache && docker compose up -d
  ```

## Notes

Only download content you own or have permission to download. Some YouTube videos require authentication or cookies; cookie configuration is not currently supported.
