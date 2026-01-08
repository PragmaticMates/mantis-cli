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

TODO:
- default values

See [template file](https://github.com/PragmaticMates/mantis-cli/blob/master/mantis/mantis.tpl) for exact JSON structure.

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

Run `mantis commands` to see all available commands with their descriptions.

| Command / Shortcut            | Description                                                       |
|-------------------------------|-------------------------------------------------------------------|
| status / s                    | Prints images and containers                                      |
| deploy [--dirty] / d          | Runs deployment process                                           |
| build [services...] / b       | Builds all services with Dockerfiles                              |
| pull [services...] / p        | Pulls required images for services                                |
| push [services...] / u        | Push built images to repository                                   |
| upload                        | Uploads config, compose and env files to server                   |
| clean / c                     | Clean images, containers, networks                                |
| logs [container] / l          | Prints logs of containers                                         |
| networks / n                  | Prints docker networks                                            |
| healthcheck [container] / hc  | Execute health-check of container                                 |
| up [params...]                | Calls compose up                                                  |
| down [params...]              | Calls compose down                                                |
| restart [service]             | Restarts all containers                                           |
| stop [containers...]          | Stops containers                                                  |
| start [containers...]         | Starts containers                                                 |
| kill [containers...]          | Kills containers                                                  |
| remove [containers...]        | Removes containers                                                |
| bash <container>              | Runs bash in container                                            |
| sh <container>                | Runs sh in container                                              |
| exec <container> <command>    | Executes command in container                                     |
| ssh                           | Connects to remote host via SSH                                   |
| scale <service> <num>         | Scales service to given number                                    |
| zero-downtime [service]       | Runs zero-downtime deployment                                     |
| encrypt-env [--force]         | Encrypts environment files                                        |
| decrypt-env [--force]         | Decrypts environment files                                        |
| check-env                     | Compares encrypted and decrypted env files                        |
| generate-key                  | Creates new encryption key                                        |
| read-key                      | Returns encryption key value                                      |
| check-config                  | Validates config file                                             |
| contexts                      | Prints all docker contexts                                        |
| create-context                | Creates docker context                                            |
| services                      | Lists all defined services                                        |
| commands                      | Lists all available commands                                      |

**Django extension:**

| Command                       | Description                                                       |
|-------------------------------|-------------------------------------------------------------------|
| shell                         | Runs Django shell                                                 |
| manage <command> [args...]    | Runs Django manage command                                        |
| send-test-email               | Sends test email to admins                                        |

**PostgreSQL extension:**

| Command                       | Description                                                       |
|-------------------------------|-------------------------------------------------------------------|
| psql                          | Starts psql console                                               |
| pg-dump [--data-only] [--table TABLE] | Backups database                                          |
| pg-restore <filename> [--table TABLE] | Restores database from backup                             |

**Nginx extension:**

| Command                       | Description                                                       |
|-------------------------------|-------------------------------------------------------------------|
| reload-webserver              | Reloads nginx                                                     |

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