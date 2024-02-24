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
mantis <ENVIRONMENT> --encrypt-env
```

Decryption is easy like this:

```bash
mantis <ENVIRONMENT> --decrypt-env
```

When decrypting, mantis prompts user for confirmation. 
You can bypass that by forcing decryption which can be useful in CI/CD pipeline:

```bash
mantis <ENVIRONMENT> --decrypt-env:force
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

| Command / Shortcut                           | Description                                                                                                                     |
|----------------------------------------------|:--------------------------------------------------------------------------------------------------------------------------------|
| --bash:params                                | Runs bash in container                                                                                                          |
| --build[:params] / -b                        | Builds all services with Dockerfiles                                                                                            |
| --check-config                               | Validates config file according to template                                                                                     |
| --check-env                                  | Compares encrypted and decrypted env files                                                                                      |
| --check-health:container                     | Checks current health of given container                                                                                        |
| --clean[:params] / -c                        | Clean images, containers, networks                                                                                              |
| --contexts                                   | Prints all docker contexts                                                                                                      |
| --create-context                             | Creates docker context using user inputs                                                                                        |
| --decrypt-env[:params,env_file,return_value] | Decrypts all environment files (force param skips user confirmation)                                                            |
| --deploy / -d                                | Runs deployment process: uploads files, pulls images, runs zero-downtime deployment, removes suffixes, reloads webserver, clean |
| --down[:params]                              | Calls compose down (with optional params)                                                                                       |
| --encrypt-env[:params,env_file,return_value] | Encrypts all environment files (force param skips user confirmation)                                                            |
| --exec:params                                | Executes command in container                                                                                                   |
| --generate-key                               | Creates new encryption key                                                                                                      |
| --get-container-name:service                 | Constructs container name with project prefix for given service                                                                 |
| --get-container-suffix:service               | Returns the suffix used for containers for given service                                                                        |
| --get-deploy-replicas:service                | Returns default number of deploy replicas of given services                                                                     |
| --get-healthcheck-config:container           | Prints health-check config (if any) of given container                                                                          |
| --get-healthcheck-start-period:container     | Returns healthcheck start period for given container (if any)                                                                   |
| --get-image-name:service                     | Constructs image name for given service                                                                                         |
| --get-image-suffix:service                   | Returns the suffix used for image for given service                                                                             |
| --get-number-of-containers:service           | Prints number of containers for given service                                                                                   |
| --get-service-containers:service             | Prints container names of given service                                                                                         |
| --has-healthcheck:container                  | Checks if given container has defined healthcheck                                                                               |
| --healthcheck[:container] / -hc              | Execute health-check of given project container                                                                                 |
| --kill[:params]                              | Kills all or given project container                                                                                            |
| --logs[:params] / -l                         | Prints logs of all or given project container                                                                                   |
| --manage:params                              | Runs Django manage command                                                                                                      |
| --networks / -n                              | Prints docker networks                                                                                                          |
| --pg-dump[:data_only,table]                  | Backups PostgreSQL database [data and structure]                                                                                |
| --pg-dump-data[:table]                       | Backups PostgreSQL database [data only]                                                                                         |
| --pg-restore[:filename,table]                | Restores database from backup [data and structure]                                                                              |
| --pg-restore-data:params                     | Restores database from backup [data only]                                                                                       |
| --psql                                       | Starts psql console                                                                                                             |
| --pull[:params] / -p                         | Pulls required images for services                                                                                              |
| --push[:params]                              | Push built images to repository                                                                                                 |
| --read-key                                   | Returns value of mantis encryption key                                                                                          |
| --remove[:params]                            | Removes all or given project container                                                                                          |
| --remove-suffixes[:prefix]                   | Removes numerical suffixes from container names (if scale == 1)                                                                 |
| --restart[:service]                          | Restarts all containers by calling compose down and up                                                                          |
| --restart-service:service                    | Stops, removes and recreates container for given service                                                                        |
| --run:params                                 | Calls compose run with params                                                                                                   |
| --scale:service,scale                        | Scales service to given scale                                                                                                   |
| --send-test-email                            | Sends test email to admins using Django 'sendtestemail' command                                                                 |
| --services                                   | Prints all defined services                                                                                                     |
| --services-to-build                          | Prints all services which will be build                                                                                         |
| --sh:params                                  | Runs sh in container                                                                                                            |
| --shell                                      | Runs and connects to Django shell                                                                                               |
| --start[:params]                             | Starts all or given project container                                                                                           |
| --status / -s                                | Prints images and containers                                                                                                    |
| --stop[:params]                              | Stops all or given project container                                                                                            |
| --try-to-reload-webserver                    | Tries to reload webserver (if suitable extension is available)                                                                  |
| --up[:params]                                | Calls compose up (with optional params)                                                                                         |
| --upload / -u                                | Uploads mantis config, compose file <br/>and environment files to server                                                        |
| --zero-downtime[:service]                    | Runs zero-downtime deployment of services (or given service)                                                                    |

Few examples:

```bash
mantis --version
mantis local --encrypt-env
mantis stage --build
mantis production --logs:container-name

# you can also run multiple commands at once
mantis stage --build --push --deploy -s -l
```

Check ``mantis --help`` for more details.

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
mantis <ENVIRONMENT> --push
```

### 3. Deployment

Deployment to your remote server is being executed by calling simple command:

```bash
mantis <ENVIRONMENT> --deploy
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
mantis <ENVIRONMENT> --status
```

list all docker networks:

```bash
mantis <ENVIRONMENT> --networks
```

and also check all container logs:

```bash
mantis <ENVIRONMENT> --logs
```

If you need to follow logs of a specific container, you can do it by passing container name to command:

```bash
mantis <ENVIRONMENT> --logs:<container-name>
```

### 5. Another useful commands

Sometimes, instead of calling whole deployment process, you just need to call compose commands directly:

```bash
mantis <ENVIRONMENT> --up
mantis <ENVIRONMENT> --down
mantis <ENVIRONMENT> --restart
mantis <ENVIRONMENT> --stop
mantis <ENVIRONMENT> --kill
mantis <ENVIRONMENT> --start
mantis <ENVIRONMENT> --clean
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