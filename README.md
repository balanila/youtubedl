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

The GitHub Actions workflow publishes both `linux/amd64` and `linux/arm64` variants under each version tag and `latest`. Docker automatically selects the matching architecture. On macOS Apple Silicon, install Docker Desktop and use the ARM64 Linux image through its Linux virtual machine; no architecture flag is needed.

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

Install Bash and Docker on the server, and ensure the runner user can access the server's Docker daemon. The workflow sets up Buildx and QEMU for cross-architecture builds; the daemon must allow privileged containers to register QEMU/binfmt handlers. If the runner itself runs in a container, it needs the Docker CLI and access to the host's Docker daemon. Keep the GitHub Actions runner up to date to meet the [requirements for `actions/checkout@v6`](https://github.com/actions/checkout#whats-new). Emulated builds can take longer, so the deployment job has a 60-minute timeout.

Set these repository secrets in **Settings → Secrets and variables → Actions**:

- `DOCKERHUB_USERNAME`: your Docker Hub username.
- `DOCKERHUB_TOKEN`: a Docker Hub personal access token with `read/write/delete` scope for publishing images and updating the repository description. For an organization's repository, the user must have Admin permissions for that repository.

The default image repository is `balanial/youtubedl`. To publish to another repository, set the repository variable `DOCKERHUB_IMAGE` to `your-username/youtubedl`. Create the repository on Docker Hub before the first publication and ensure the token can push to it.

After publishing the image and recording its version, the workflow updates the Docker Hub repository description from `README.dockerhub.md`. This separate README contains startup and usage instructions for image users. If you change the image repository, update the image names in that file as well. A failed description update fails the workflow before deployment.

Versions follow SemVer and are calculated from the latest reachable `vMAJOR.MINOR.PATCH` Git tag. After merging a pull request into `main`, its source branch determines the increment:

- `bugfix/…` or `hotfix/…`: increment patch, for example `1.2.3` → `1.2.4`.
- `feature/…`: increment minor and reset patch, for example `1.2.3` → `1.3.0`.
- Direct pushes to `main` or other branch prefixes: increment patch.

If several pull requests have merged since the previous version, the workflow increments once, with a feature taking precedence over fixes. Branch names are read from the GitHub pull request API, so merge, squash, and rebase merges are supported. Before the first version tag exists, `INITIAL_VERSION` in the workflow (default `1.0.0`) is the base, and the current commit determines the increment. For a major release, create a new `vMAJOR.0.0` tag on `main` and run the workflow for that commit.

The workflow publishes both `<image repository>:MAJOR.MINOR.PATCH` and `<image repository>:latest`, then records the published version as a Git tag on the built commit. Rerunning a tagged commit reuses its version. The workflow needs `contents: write` to create tags and `pull-requests: read` to read source branches; repository rules must allow its token to create `v*` tags. The image also includes OCI version and commit revision labels. Published versions appear in the workflow run summary.

The pipeline builds both architectures with Buildx on the runner and publishes their shared image manifest to Docker Hub. It then pulls the exact versioned image for the server's architecture, replaces the `youtubedl` container with `docker run`, and checks that the application responds over HTTP inside the container. If publication or pulling the image fails, deployment does not start. Deployment does not use Docker Compose. Access the application through your reverse proxy; port `8000` is not published on the server.

The container joins the existing Docker network `web` at startup. Create this network on your server before the first deployment if needed: `docker network create web`. The workflow checks that the network exists before stopping the current container. Connect your reverse proxy to this network and configure its upstream as `http://youtubedl:8000`.

Downloads are temporarily stored in `/data/downloads` inside the container. Each download's temporary directory is deleted after transmission to the browser, including when transmission fails or the connection is interrupted. No persistent volume is used. Replacing the container also removes files left behind by a process crash.

The container uses `--restart unless-stopped`, and deployments run one at a time. Replacing the container causes brief downtime and may interrupt active downloads. If the startup check fails, the workflow prints container logs and exits with an error. There is no automatic rollback.

After a successful deployment check, the workflow removes older local images from the configured image repository that are no longer used by any container. The deployed version, `latest`, and images used by running or stopped containers are kept. Published versions on Docker Hub are retained. Images belonging to other applications are unaffected.

## GitLab CI

The GitLab pipeline publishes a multi-platform image to `balanial/youtubedl` on Docker Hub when a SemVer Git tag is pushed:

```bash
git tag v1.0.0
git push origin v1.0.0
```

Set these GitLab CI/CD variables:

- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN`

The runner tagged `docker` must support Docker-in-Docker in privileged mode because the build registers QEMU/binfmt handlers inside the job.

For the Git tag `v1.2.3`, the pipeline publishes these Docker tags:

- `balanial/youtubedl:1.2.3`
- `balanial/youtubedl:1.2`
- `balanial/youtubedl:1`
- `balanial/youtubedl:latest`

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
