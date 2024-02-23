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
| project_name             | string | slug of your project name used as prefix for containers      |
| encryption               | dict   | encryption settings                                          |
| encryption.deterministic | bool   | if True, encryption hash is always the same for same value   |
| encryption.folder        | bool   | path to folder with your environment files                   |
| configs                  | dict   | configuration settings                                       |
| configs.folder           | string | path to folder with your configuration files                 |
| build                    | dict   | build settings                                               |
| build.tool               | string | "docker" or "compose"                                        |
| compose                  | dict   | docker compose settings                                      |
| compose.command          | string | standalone "docker-compose" or "docker compose" plugin       |
| compose.name             | string | docker compose suffix: "docker-compose.ENVIRONMENT.NAME.yml" |
| compose.folder           | string | path to folder with compose files                            |
| environment              | dict   | environment settings                                         |
| environment.folder       | string | path to folder with environment files                        |
| environment.file_prefix  | string | file prefix of environment files                             |
| zero_downtime            | array  | list of services to deploy with zero downtime                |
| project_path             | string | path to folder with project files on remote server           |
| connections              | dict   | definition of your connections for each environment          |

TODO:
- default values

See [template file](https://github.com/PragmaticMates/mantis-cli/blob/master/mantis/mantis.tpl) for exact JSON structure.

### Connections

Connection for each environment except localhost can be defined either as an SSH or Docker context:

For example:

```json
"connections": {
    "stage": "context://<context_name>",
    "production": "ssh://<user>@<host>:<port>"
}
```

### Encryption

If you plan to use encryption and decryption of your environment files, you need to create encryption key.

Generation of new key:

```bash
mantis --generate-key
```

Save key to **mantis.key** file:

```bash
echo <MANTIS_KEY> > /path/to/encryption/folder/mantis.key
```

Then you can encrypt your environment files using symmetric encryption. 
Every environment variable is encrypted separately instead of encrypting the whole file for better tracking of changes in VCS.

```bash
mantis <ENVIRONEMNT> --encrypt-env
```

Decryption is easy like this:

```bash
mantis <ENVIRONEMNT> --decrypt-env
```

When decrypting, mantis prompts user for confirmation. 
You can bypass that by forcing decryption which can be useful in CI/CD pipeline:

```bash
mantis <ENVIRONEMNT> --decrypt-env:force
```

## Usage

General usage of mantis-cli has this format:

```bash
mantis [--mode=remote|ssh|host] [environment] --command[:params]
```

### Modes

Mantis can operate in 3 different modes depending on a way it connects to remote machhine


#### Remote mode ```--mode=remote``` 

Runs commands remotely from local machine using DOCKER_HOST or DOCKER_CONTEXT (default)

#### SSH mode ```--mode=ssh```

Connects to host via ssh and run all mantis commands on remote machine directly (nantis-cli needs to be installed on server)


#### Host mode ```--mode=host```

Runs mantis on host machine directly without invoking connection (used as proxy for ssh mode)


### Environments

Environment can be either *local* or any custom environment like *stage*, *production* etc.
The environment is also used as an identifier for remote connection.

### Commands

| command / shortcut                         | environment required | description                                                                                                 | params         |
|--------------------------------------------|:--------------------:|-------------------------------------------------------------------------------------------------------------|----------------|
| *--version*                                |        false         | prints the mantis-cli version                                                                               |                |
| *--check-config*                           |        false         | validates config file according to template                                                                 |                |
| *--generate-key*                           |        false         | creates new encryption key                                                                                  |                |
| *--read-key*                               |        false         | returns value of mantis encryption key                                                                      |                |
| *--encrypt-env[:force]*                    |         TRUE         | encrypts all environment files (force param skips user confirmation)                                        |                |
| *--decrypt-env[:force]*                    |         TRUE         | decrypts all environment files (force param skips user confirmation)                                        |                |
| *--check-env*                              |         TRUE         | compares encrypted and decrypted env files                                                                  |                |
| *--contexts*                               |        false         | prints all docker contexts                                                                                  |                |
| *--create-context*                         |        false         | creates docker context using user inputs                                                                    |                |
| *--healthcheck:container-name / -hc*       |         TRUE         | checks health of given project container                                                                    | container name |
| *--build[:params] / -b*                    |         TRUE         | builds all services with Dockerfiles                                                                        | custom params  |
| *--services*                               |         TRUE         | prints all defined services                                                                                 |                |
| *--services-to-build*                      |         TRUE         | prints all services which will be build                                                                     |                |
| *--push*                                   |         TRUE         | push built images to repository                                                                             |                |
| *--pull / -p*                              |         TRUE         | pulls required images for services                                                                          |                |
| *--upload / -u*                            |         TRUE         | uploads mantis config, compose file <br/>and environment files to server                                    |                |
| *--restart*                                |         TRUE         | restarts all containers by calling compose down and up                                                      |                |
| *--deploy / -d*                            |         TRUE         | uploads files, pulls images, runs zero-downtime deployment, <br/>removes suffixes, reloads webserver, clean |                |
| *--zero-downtime[:service]*                |         TRUE         | runs zero-downtime deployment of services (or given service)                                                | service        |
| *--remove-suffixes[:prefix]*               |         TRUE         | removes numerical suffixes from container names (if scale == 1)                                             | prefix         |
| *--restart-service:service*                |         TRUE         | stops, removes and recreates container for given service                                                    | service        |
| *--stop[:container-name]*                  |         TRUE         | stops all or given project container                                                                        | container name |
| *--kill[:container-name]*                  |         TRUE         | kills all or given project container                                                                        | container name |
| *--start[:container-name]*                 |         TRUE         | starts all or given project container                                                                       | container name |
| *--run:params*                             |         TRUE         | calls compose run with params                                                                               | params         |
| *--up[:params]*                            |         TRUE         | calls compose up (with optional params)                                                                     | params         |
| *--down[:params]*                          |         TRUE         | calls compose down (with optional params)                                                                   | params         |
| *--remove[:params]*                        |         TRUE         | removes all or given project container                                                                      | container name |
| *--clean / -c*                             |         TRUE         | clean images, containers, networks                                                                          |                |
| *--clean:--volumes*                        |         TRUE         | same as --clean but also removes volumes                                                                    |                |
| *--status / -s*                            |         TRUE         | prints images and containers                                                                                |                |
| *--networks / -n*                          |         TRUE         | prints docker networks                                                                                      |                |
| *--logs[:container-name] / -l*             |         TRUE         | prints logs of all or given project container                                                               | container name |
| *--bash:container-name*                    |         TRUE         | runs bash in container                                                                                      | container name |
| *--sh:container-name*                      |         TRUE         | runs sh in container                                                                                        | container name |
| *--get-containers[:prefix]*                |         TRUE         | prints all project containers                                                                               | container name |
| *--get-container-project:container-name*   |         TRUE         | prints project name of given container                                                                      | container name |
| *--get-healthcheck-config:container-name*  |         TRUE         | prints health-check config (if any) of given container                                                      | container name |

Few examples:

```bash
mantis --version
mantis local --encrypt-env
mantis stage --build
mantis production --logs:container-name

# you can also run multiple commands at once
mantis stage --build --push --deploy -s -l
```

## Flow

### 1. Build

Once you define mantis config for your project and optionally create encryption key, you can build your docker images:

```bash
mantis <ENVIRONMENT> --build
```

Mantis either uses ```docker-compose --build``` or ```docker build``` command depending on build tool defined in your config.
Build image names use '_' as word separator.

### 2. Push

Built images needs to be pushed to your repository defined in compose file (you need to authenticate)

```bash
mantis <ENVIRONEMNT --push
```

### 3. Deployment

Deployment to your remote server is being executed by calling simple command:

```bash
mantis <ENVIRONMENT> --deploy
```

The deployment process consists of multiple steps:

- If using --mode=ssh, mantis uploads mantis config, environment files and compose file to server
- pulling docker images from repositories
- zero-downtime deployment of running containers (if any)
- calling docker compose up to start containers
- removing numeric suffixes from container names (if scale==1)
- reloading webserver (if found suitable extension)
- cleaning docker resources (without volumes)

Docker container names use '-' as word separator (docker compose v2 convention).

### 4. Inspect

Once deployed, you can verify the container status:

```bash
mantis <ENVIRONEMNT> --status
```

list all docker networks:

```bash
mantis <ENVIRONMENT> --networks
```

and also check all container logs:

```bash
mantis <ENVIRONEMNT> --logs
```

If you need to follow logs of a specific container, you can do it by passing container name to command:

```bash
mantis <ENVIRONMENT> --logs:<container-name>
```

### 5. Another useful commands

Sometimes, instead of calling whole deployment process, you just need to call compose commands directly:

```bash
mantis <ENVIRONEMNT> --up
mantis <ENVIRONEMNT> --down
mantis <ENVIRONEMNT> --restart
mantis <ENVIRONEMNT> --stop
mantis <ENVIRONEMNT> --kill
mantis <ENVIRONEMNT> --start
```

Commands over a single container:

```bash
mantis <ENVIRONMENT> --bash:container-name
mantis <ENVIRONMENT> --sh:container-name
mantis <ENVIRONMENT> --run:params
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