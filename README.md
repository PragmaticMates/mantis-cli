# mantis-cli

Mantis is a CLI (command line interface) tool designed as a wrapper upon docker and docker compose commands for your project.

Using few commands you can:
- encrypt and decrypt your environment files
- build and push docker images
- create docker contexts
- zero-downtime deploy your application
- print logs of your containers
- connect to bash of your containers using SSH 
- clean docker resources
- use specific commands using Django, PostgreSQL and Nginx extensions
- and much more

## Installation

```bash
pip install mantis-cli
```

## Configuration

Create a **mantis.json** configuration file in JSON format.
You can use ``<MANTIS>`` variable in your paths if needed as a relative reference to your mantis file.

### Explanation of config arguments

| argument                 | type   | description                                                  |
|--------------------------|--------|--------------------------------------------------------------|
| manager_class            | string | class path to mantis manager class                           |
| extensions               | dict   | Django, Postgres, Nginx                                      |
| encryption               | dict   | encryption settings                                          |
| encryption.deterministic | bool   | if True, encryption hash is always the same for same value   |
| encryption.folder        | bool   | path to folder with your environment files                   |
| configs                  | dict   | configuration settings                                       |
| configs.folder           | string | path to folder with your configuration files                 |
| build                    | dict   | build settings                                               |
| build.tool               | string | "docker" or "compose"                                        |
| compose                  | dict   | docker compose settings                                      |
| compose.command          | string | standalone "docker-compose" or "docker compose" plugin       |
| compose.folder           | string | path to folder with compose files                            |
| environment              | dict   | environment settings                                         |
| environment.folder       | string | path to folder with environment files                        |
| environment.file_prefix  | string | file prefix of environment files                             |
| zero_downtime            | array  | list of services to deploy with zero downtime                |
| project_path             | string | path to folder with project files on remote server           |
| connection               | string | single connection string (use instead of connections)        |
| connections              | dict   | definition of your connections for each environment          |
| tunnel                   | dict   | SSH tunnel settings                                          |
| tunnel.enabled           | bool   | share a single SSH connection for the whole run (null = auto)|
| tunnel.remote_socket     | string | path to the docker socket on the server                      |
| tunnel.ssh_options       | array  | extra options passed to the ssh command                      |

TODO:
- default values

See [template file](https://github.com/PragmaticMates/mantis-cli/blob/master/mantis/mantis.tpl) for exact JSON structure.

### Build settings

With `build.tool` set to `"docker"`, mantis builds each service that declares a `build:` section
in your compose files, reading `context`, `dockerfile`, `args`, `platform`, `cache_from` and
`cache_to` from it. Nothing else needs configuring — the compose file stays the single source of
truth:

```yaml
services:
  backend:
    image: acme/app:production
    build:
      context: ../../../
      dockerfile: ./configs/docker/production/backend/Dockerfile
      cache_from:
        - type=registry,ref=acme/app:production
      cache_to:
        - type=inline
```

`cache_from` and `cache_to` become `--cache-from` / `--cache-to` on `docker build`, which is how
you keep a layer cache across machines that share no local docker state — CI runners, for
instance. Inline cache stores the metadata in the image being pushed and reads it back from the
previous one, so no separate cache tag is needed; note that it records only the final image's
layers, which is enough whenever earlier build stages copy their output forward.

With `build.tool` set to `"compose"`, `docker compose build` handles all of this itself.

### Connections

Mantis supports two connection modes: **multi-environment** and **single connection**.

#### Multi-environment mode

Use `connections` (dict) when you have multiple environments like stage, production, etc.:

```json
"connections": {
    "stage": "context://<context_name>",
    "production": "ssh://<user>@<host>:<port>"
}
```

In this mode, you must specify the environment in every command:

```bash
mantis -e production status
mantis -e stage deploy
```

#### Single connection mode

Use `connection` (string) when you only have one environment. This simplifies the CLI usage by making the environment parameter optional:

```json
"connection": "ssh://<user>@<host>:<port>"
```

In this mode, you can run commands without specifying an environment:

```bash
mantis status
mantis deploy
```

Environment files are looked up directly in the `environment.folder` instead of environment-specific subfolders.

**Note:** You cannot define both `connection` and `connections` in the same config file.

#### SSH tunnel

With a plain `ssh://` connection, Docker opens a **separate SSH connection for every
command** mantis runs. A single deployment issues dozens of them, and `compose pull` fans
out over all services at once. That burst runs into sshd's `MaxStartups`, which drops
connections beyond its threshold:

```
kex_exchange_identification: read: Connection reset by peer
```

It is also slow when the connection goes through a `ProxyCommand` (Cloudflare Access,
bastion hosts, ...), because each connection spawns its own proxy process.

The tunnel makes mantis open **one** SSH connection per run, forwarding the remote docker
socket to a local one and pointing every docker command at it.

Docker itself offers no way to pass `ssh` options (`ControlMaster` and friends), so this
is handled entirely by mantis — no `~/.ssh/config` changes are needed, and connection
details keep coming from your `ssh://` connection string. Unlike `ControlMaster`
multiplexing, forwarded channels are not counted against sshd's `MaxSessions`, so no
server-side configuration is required either.

`tunnel.enabled` decides how much mantis verifies before trusting it:

| value | behaviour |
|-------|-----------|
| unset (default) | detect per run: tunnel, and keep it only if the docker daemon answers through it |
| `true` | tunnel without detecting, for a server already known to support it |
| `false` | never tunnel |

```json
"tunnel": {
    "enabled": true
}
```

Detection costs one extra round-trip per run and cannot be skipped by opening the forward
alone: `ssh -L` to a unix socket succeeds even when nothing listens on the far end, so a
tunnel only proves itself once the daemon has replied. Set `enabled` explicitly once
`check-tunnel` (below) confirms a server, and that round-trip goes away.

Requirements on the server: the connecting user must be able to read the docker socket
(typically membership in the `docker` group), and `AllowStreamLocalForwarding` must not
be disabled — it defaults to `yes`. Whenever the tunnel cannot be used, mantis warns and
falls back to a connection per docker command, so deployments keep working either way.

The check ignores `tunnel.enabled`, so it answers "would this work" rather than "is this
on" — use it before setting `enabled` to `true`:

```bash
mantis -e production check-tunnel
```

It opens the tunnel, asks the remote docker daemon for its version and closes it again,
exiting non-zero on failure. A refused forward and an unreachable socket are reported
separately, since they need different fixes (`sshd_config` versus group membership).

Pass `--no-tunnel` to disable it for a single run:

```bash
mantis -e production --no-tunnel deploy
```

### Encryption

If you plan to use encryption and decryption of your environment files, you need to create encryption key.

Generation of new key:

```bash
mantis generate-key
```

Save key to **mantis.key** file:

```bash
echo <MANTIS_KEY> > /path/to/encryption/folder/mantis.key
```

Then you can encrypt your environment files using symmetric encryption.
Every environment variable is encrypted separately instead of encrypting the whole file for better tracking of changes in VCS.

```bash
mantis -e <ENVIRONMENT> encrypt-env
```

Decryption is easy like this:

```bash
mantis -e <ENVIRONMENT> decrypt-env
```

When decrypting, mantis prompts user for confirmation.
You can bypass that by forcing decryption which can be useful in CI/CD pipeline:

```bash
mantis -e <ENVIRONMENT> decrypt-env --force
```

## Usage

General usage of mantis-cli has this format:

```bash
mantis [OPTIONS] COMMAND [ARGS]... [+ COMMAND [ARGS]...]
```

Use `+` to chain multiple commands:

```bash
mantis -e production build + push + deploy
```

### Options

| Option          | Description                                       |
|-----------------|---------------------------------------------------|
| --env, -e       | Environment ID (e.g., stage, production)          |
| --mode, -m      | Execution mode: remote (default), ssh, host       |
| --dry-run, -n   | Show commands without executing                   |
| --version, -v   | Show version and exit                             |
| --help, -h      | Show help message                                 |

### Modes

Mantis can operate in 3 different modes depending on how it connects to remote machine:

#### Remote mode `--mode=remote`

Runs commands remotely from local machine using DOCKER_HOST or DOCKER_CONTEXT (default)

#### SSH mode `--mode=ssh`

Connects to host via SSH and runs all mantis commands on remote machine directly (mantis-cli needs to be installed on server)

#### Host mode `--mode=host`

Runs mantis on host machine directly without invoking connection (used as proxy for ssh mode)

### Environments

Environment can be either *local* or any custom environment like *stage*, *production* etc.
The environment is also used as an identifier for remote connection.

### Commands

Run `mantis --help` to see all available commands with their descriptions.

**Core commands:**

| Command / Shortcut                    | Description                                               |
|---------------------------------------|-----------------------------------------------------------|
| status / s                            | Prints images and containers                              |
| deploy [--dirty] [--strategy] / d     | Runs deployment process                                   |
| rolling-update [service] / ru         | Performs rolling update of containers one-by-one          |
| clean [params...] / c                 | Clean images, containers, networks                        |

**Files:**

| Command / Shortcut                    | Description                                               |
|---------------------------------------|-----------------------------------------------------------|
| upload / u                            | Uploads config, compose and env files to server           |

**Images:**

| Command / Shortcut                    | Description                                               |
|---------------------------------------|-----------------------------------------------------------|
| build [SERVICES...] / b               | Builds all services with Dockerfiles                      |
| pull [SERVICES...] / pl               | Pulls required images for services                        |
| push [SERVICES...] / p                | Push built images to repository                           |
| get-image-name SERVICE                | Gets image name for service                               |

**Containers:**

| Command / Shortcut                    | Description                                               |
|---------------------------------------|-----------------------------------------------------------|
| logs [CONTAINER\|SERVICE] / l          | Prints logs of containers                                 |
| networks / n                          | Prints docker networks                                    |
| healthcheck [CONTAINER\|SERVICE] / hc  | Execute health-check of container                         |
| stop [CONTAINERS...]                  | Stops containers                                          |
| start [CONTAINERS...]                 | Starts containers                                         |
| kill [CONTAINERS...]                  | Kills containers                                          |
| remove [CONTAINERS...] [--force]      | Removes containers                                        |
| rename CONTAINER NEW_NAME             | Rename container                                          |
| bash CONTAINER\|SERVICE               | Runs bash in container                                    |
| sh CONTAINER\|SERVICE                 | Runs sh in container                                      |
| exec CONTAINER\|SERVICE COMMAND...    | Executes command in container                             |
| exec-it CONTAINER\|SERVICE COMMAND... | Executes command in container (interactive)               |
| get-container-name SERVICE            | Gets container name for service                           |
| remove-suffixes [PREFIX]              | Removes numerical suffixes from container names           |

**Compose:**

| Command                               | Description                                               |
|---------------------------------------|-----------------------------------------------------------|
| up [PARAMS...]                        | Calls compose up                                          |
| down [PARAMS...]                      | Calls compose down                                        |
| run PARAMS...                         | Calls compose run with params                             |

**Services:**

| Command                               | Description                                               |
|---------------------------------------|-----------------------------------------------------------|
| restart [SERVICE]                     | Restarts containers                                       |
| scale SERVICE NUM                     | Scales service to given number                            |
| zero-downtime [SERVICE]               | Runs zero-downtime deployment                             |
| restart-service SERVICE               | Restarts a specific service                               |
| services                              | Lists all defined services                                |
| services-to-build                     | Lists services that will be built                         |

**Volumes:**

| Command                               | Description                                               |
|---------------------------------------|-----------------------------------------------------------|
| backup-volume VOLUME                  | Backups volume to a file                                  |
| restore-volume VOLUME FILE            | Restores volume from a file                               |

**Secrets:**

| Command                               | Description                                               |
|---------------------------------------|-----------------------------------------------------------|
| show-env [KEYWORD]                    | Shows environment variables from .env files               |
| encrypt-env [--force]                 | Encrypts environment files                                |
| decrypt-env [--force]                 | Decrypts environment files                                |
| check-env                             | Compares encrypted and decrypted env files                |
| generate-key                          | Creates new encryption key                                |
| read-key                              | Returns encryption key value                              |

**Configuration:**

| Command                               | Description                                               |
|---------------------------------------|-----------------------------------------------------------|
| show-config                           | Shows the JSON mantis config                              |
| check-config                          | Validates config file                                     |

**Connections:**

| Command                               | Description                                               |
|---------------------------------------|-----------------------------------------------------------|
| contexts                              | Prints all docker contexts                                |
| create-context                        | Creates docker context                                    |
| ssh                                   | Connects to remote host via SSH                           |
| check-tunnel                          | Checks if the docker socket can be tunnelled over SSH     |

**Django extension:**

| Command                               | Description                                               |
|---------------------------------------|-----------------------------------------------------------|
| shell                                 | Runs Django shell                                         |
| manage [OPTIONS] CMD [ARGS...]        | Runs Django manage command                                |
| send-test-email                       | Sends test email to admins                                |
| reset-migrations                      | Clears migration history and fakes all migrations         |

The `manage` command supports health-check options:
- `--if-healthy`: Only execute if the container is currently healthy. Skips with a warning if not healthy.
- `--healthy-timeout N`: Wait up to N seconds for the container to become healthy before executing. Polls every second and skips the command if the timeout is reached.

**PostgreSQL extension:**

| Command                               | Description                                               |
|---------------------------------------|-----------------------------------------------------------|
| psql                                  | Starts psql console                                       |
| pg-dump [--data-only] [--table]       | Backups PostgreSQL database                               |
| pg-dump-data [--table]                | Backups PostgreSQL database (data only)                   |
| pg-restore FILENAME [--table]         | Restores database from backup                             |
| pg-restore-data FILENAME TABLE        | Restores database data from backup                        |

**Nginx extension:**

| Command                               | Description                                               |
|---------------------------------------|-----------------------------------------------------------|
| reload-webserver                      | Reloads nginx webserver                                   |

### Examples

```bash
mantis --version
mantis -e local encrypt-env
mantis -e stage build
mantis -e production logs web

# Run multiple commands using + separator
mantis -e stage build + push + deploy
mantis -e stage build web api + push + deploy + status

# Commands with arguments
mantis -e production deploy --dirty
mantis -e production manage migrate
mantis -e production manage --healthy-timeout 60 migrate
mantis -e production pg-dump --data-only --table users

# Single connection mode (no environment needed)
mantis status
mantis deploy
```

Check `mantis --help` for more details, or `mantis COMMAND --help` for command-specific help.

## Flow

### 1. Build

Once you define mantis config for your project and optionally create encryption key, you can build your docker images:

```bash
mantis -e <ENVIRONMENT> build
```

Mantis either uses `docker-compose --build` or `docker build` command depending on build tool defined in your config.
Build image names use '_' as word separator.

### 2. Push

Built images needs to be pushed to your repository defined in compose file (you need to authenticate)

```bash
mantis -e <ENVIRONMENT> push
```

### 3. Deployment

Deployment to your remote server is being executed by calling simple command:

```bash
mantis -e <ENVIRONMENT> deploy
```

Or chain all steps together:

```bash
mantis -e <ENVIRONMENT> build + push + deploy
```

The deployment process consists of multiple steps:

- If using --mode=ssh, mantis uploads mantis config, environment files and compose file to server
- pulling docker images from repositories
- [zero-downtime deployment](https://github.com/PragmaticMates/mantis-cli?tab=readme-ov-file#zero-downtime-deployment) of running containers (if any)
- calling docker compose up to start containers
- removing numeric suffixes from container names (if scale==1)
- reloading webserver (if found suitable extension)
- cleaning docker resources (without volumes)

Docker container names use '-' as word separator (docker compose v2 convention).

### 4. Inspect

Once deployed, you can verify the container status:

```bash
mantis -e <ENVIRONMENT> status
```

list all docker networks:

```bash
mantis -e <ENVIRONMENT> networks
```

and also check all container logs:

```bash
mantis -e <ENVIRONMENT> logs
```

If you need to follow logs of a specific container, you can do it by passing container name to command:

```bash
mantis -e <ENVIRONMENT> logs <container-name>
```

#### Container or service name

Commands taking a container (`logs`, `healthcheck`, `bash`, `sh`, `exec`, `exec-it`) also accept a
plain service name and mantis finds its container(s) for you, including scaled ones with numerical
suffixes and services declaring their own `container_name`:

```bash
mantis -e production logs app   # reads logs of <project>-app container
mantis -e production bash app   # same container, no need to type the project prefix
```

A name which is not a service is still matched against container names without their project
prefix, which covers services numbered in the compose file:

```bash
mantis -e production logs htmltopdf  # reads <project>-htmltopdf-1 and <project>-htmltopdf-2
```

An exact container name always takes precedence: if a container literally named `app` exists,
`logs app` reads that one instead of `<project>-app`. Names matching no container at all are
passed to docker as they are.

`logs` follows all matching containers at once, prefixing every line with a container name:

```
itfitness-htmltopdf-1 | POST /generate-pdf 200 3355.969 ms - 837045
itfitness-htmltopdf-2 | POST /generate-pdf 200 889.662 ms - 747746
```

Commands which can only operate on one container (`bash`, `sh`, `exec`, `exec-it`, `healthcheck`)
use the first match and warn about the rest.

### 5. Another useful commands

Sometimes, instead of calling whole deployment process, you just need to call compose commands directly:

```bash
mantis -e <ENVIRONMENT> up
mantis -e <ENVIRONMENT> down
mantis -e <ENVIRONMENT> restart
mantis -e <ENVIRONMENT> stop
mantis -e <ENVIRONMENT> kill
mantis -e <ENVIRONMENT> start
mantis -e <ENVIRONMENT> clean
```

Commands over a single container:

```bash
mantis -e <ENVIRONMENT> bash <container-name>
mantis -e <ENVIRONMENT> sh <container-name>
mantis -e <ENVIRONMENT> run <params>
```

## Zero-downtime deployment

Mantis has own zero-downtime deployment implementation without any third-party dependencies. 
It uses docker compose service scaling and docker health-checks.

Works as follows:

- a new service container starts using scaling
- mantis waits until the new container is healthy by checking its health status. If not health-check is defined, it waits X seconds defined by start period 
- reloads webserver (to proxy requests to new container)
- once container is healthy or start period ends the old container is stopped and removed
- new container is renamed to previous container's name
- webserver is reloaded again

## Release notes

Mantis uses semantic versioning. See more in [changelog](https://github.com/PragmaticMates/mantis-cli/blob/master/CHANGES.md).