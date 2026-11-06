# 4. Containers

## What a container is

A container is a normal process that the operating system isolates: it sees its own files, network and limits. It is not a small virtual machine, and it shares the host's kernel. An **image** is the frozen set of files it starts from. The same image runs the same on a laptop and in the cloud, which is the main reason to use one.

An image is a stack of **layers**, one per step in the Dockerfile. Layers are cached and reused, so a step reruns only if it or an earlier step changed. That is why dependency files get copied before source code in many Dockerfiles.

## The choices in these Dockerfiles

**Two stages.** The first stage has `uv` and builds the environment. The second copies in only the result. Build tools then never reach the final image, which keeps it smaller and leaves less to attack.

**An allowlist of files.** `.dockerignore` starts with `*`, which excludes everything, then names what may enter. The usual approach lists what to exclude, so a new secret or data folder gets in by default. Here it stays out by default. With `.env`, 5 GB of photos and a `wandb/` folder in the project, that default matters.

**A locked install.** `uv sync --frozen` installs exactly what `uv.lock` says and fails if it does not match, so a rebuild next month gets the same versions. `--extra serving` means the API image holds only serving libraries, and `--no-editable` copies the code in rather than linking back to a folder that will not exist.

**A non-root user.** The process runs as uid 1000. If someone found a way to run code through an uploaded image, they would have far less to work with.

**A checksum check during the build.** A wrong model fails the build, long before it could answer a request.

**A health check.** Docker asks `/health` every 30 seconds. `compose.yaml` uses it so the demo page starts only once the API can answer.

**One process per container.** The API and the demo page are separate images, because they scale and fail separately, and the demo holds no model.

## Limits, and what they measure

`--cpus 0.5` does not give you half a core to yourself. It gives a time budget: use at most half a second of CPU time per second, and be paused when it runs out. `--memory 1g` is harder: go over it and the process is killed. Both come from a Linux feature called cgroups.

So measuring an image means running it under the limits it will really have. Measuring it unlimited on a fast desktop would flatter it. The sizes in `main.tf` come from running the API image at 0.25, 0.5 and 1 vCPU, and reading the real peak from `/sys/fs/cgroup/memory.peak`, which the container's own limit is enforced against.

## Compose

`compose.yaml` describes the two containers and how they connect, so one command starts the whole service with no cloud account. On their shared network, the demo page finds the API by its service name: `http://api:8000`. The address comes from the `FRUITY_API_ENDPOINT` variable, because where the API is depends on the deployment, not on the code.

## In this repo

- [docker/api.Dockerfile](../../docker/api.Dockerfile) and [docker/frontend.Dockerfile](../../docker/frontend.Dockerfile): the two images.
- [.dockerignore](../../.dockerignore): the allowlist.
- [compose.yaml](../../compose.yaml): both apps together. Try `docker compose up --build`, then open <http://localhost:8501>.
