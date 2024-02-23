# Release notes

## v14.6.0 (2024-02-18)
- django container checks for suffix as well

## v14.5.5 (2024-02-15)
- fixed local mantis image during build using docker tool

## v14.5.4 (2024-02-15) 
- fixed environment in postgres extension 

## v14.5.3 (2024-02-11)
- added Nginx extension to template and link to template file in error message 

## v14.5.2 (2024-02-08) 
- stripped encryption key 

## v14.5.1 (2024-02-01) 
- missing mantis.tpl in manifest 

## v14.5.0 (2024-01-30) 
- config file validation 

## v14.4.0 (2024-01-22) 
- using pretty table during mantis config selection 
- updated Makefile 

## v14.3.1 (2024-01-22) 
- fixed paths for docker build command 

## v14.3.0 (2024-01-20) 
- colorful selection of mantis files depending on environment/connection name 
- fixed makefile 

## v14.2.0 (2024-01-20) 
- cleaning all objects, not just dangling 
- fixed Makefile 

## v14.1.0 (2024-01-20) 
- do not remove volumes during cleaning, do not remove container suffixes for services with number suffix 
- makefile 

## v14.0.1 (2024-01-20) 
- fixed missing import to random_string 

## v14.0.0 (2024-01-20) 
- deterministic encryption by default, option to set path to mantis.key file, default paths for compose, configs, environment and mantis key are relative to mantis config file 

## v13.3.1 (2024-01-20) 
- User input to choose mantis.json file if found more than 1 
- check if connection for given environment ID exists 

## v13.2.1 (2024-01-17) 
- added cffi to requirements 

## v13.2.0 (2024-01-17) 
- added install dependencies into setup.py 

## v13.1.0 (2024-01-15) 
- refactoring upload method 

## v13.0.0 (2024-01-15) 
- improved fail checking of encryption 
- zero-downtime deployment using sleep for time period for services without healthcheck command defined 

## v12.4.1 (2024-01-09) 
- fixed version info (print replaced exit) 

## v12.4.0 (2024-01-09) 
- option to build using docker instead of docker compose 

## v12.3.0 (2024-01-06) 
- reading mantis encryption key from  if mantis.key file does not exist 

## v12.2.0 (2024-01-05) 
- custom docker compose command 

## v12.1.0 (2024-01-04)
- automatic config path discover

## v12.0.0 (2024-01-03) 
- improved deployment 

## v11.1.0 (2024-01-02) 
- counting how long it takes to start container during healthcheck 
- proper health-checking 
- healthcheck helper methods 
- refactoring 
- fixed path to environments on remote machine 

## v11.0.0 (2024-01-02) 
- zero downtime deployment 
- fixed restart service command 
- build and push don't use docker connection 
- refactoring 

## v10.0.0 (2023-12-31) 
- build uses compose file 
- refactoring environment and configs folders 
- cryptography and environment refactoring 

## v9.0.4 (2023-12-21) 
- refactoring containers 
- git status 

## v9.0.3 (2023-12-20) 
- version info and --version command 

## v9.0.2 (2023-12-20) 
- refactoring restart command 
- refactoring, some fixes 

## v9.0.1 (2023-12-19) 
- removed build platform 
- fixed postgres extension 
- removed swarm related functionality 
- refactoring logic and compose-file 

## v9.0.0 (2023-12-18) 
- updated extensions, massive refactoring 
- os.system calling is wrapped into cmd() method to catch error states and exit with error 

## v8.0.2 (2023-12-12) 
- CONTAINER_APP > CONTAINER_BACKEND 

## v8.0.1 (2023-12-12) 
- hyphen in container names replaced by dash 

## v8.0.0 (2023-12-11) 
- docker-compose > docker compose 

## v7.2.1 (2023-10-26) 
- stripping mantis key from file 

## v7.2.0 (2023-10-26)  
- raising exception when decrypting fails 

## v7.1.2 (2023-10-26) 
- decrypting .encrypted files 
- remove time if docker buildkit enabled 
- fixed force encryption and decryption 

## v7.1.0 (2023-10-10) 
- dev > local 

## v7.0.0 (2023-10-09) 
- encryption of multiple environment files 
- refactoring environment encryption check 
- fixed path to mantis key when dirname of config file is empty 

## v6.0.0 (2023-08-22)
- refactoring
- build_image fix 
- more helpful error message for mantis key 
- more universal services, configrable paths 

## v5.1.2 (2023-04-03) 
- create new container if not running 

## v5.1.1 (2023-02-01) 
- added default.conf nginx config to include all available sites configs 

## v5.1.0 (2023-01-22) 
- updated webserver paths in upload() 

## v5.0.0 (2023-01-17) 
- support for manager extensions (Django etc.) 

## v4.1.0 (2023-01-17) 
- setting project path in connection details 
- refactoring project path 
- sh and bash 
- validating ImportError 
- decrypt environment - force param (hide variables in console) 
- decrypt/encrypt environment - force param (params optional) 
- decrypt/encrypt environment - force param 

## v4.0.2 (2022-04-13) 
- -hc proxy to --healthcheck command 
- sleeping during health-checking 

## v4.0.1 (2022-04-13) 
- increased healthcheck retries from 10 to 30, added retry counter into output 

## v4.0.0 (2022-04-13) 
- service health-checking during zero-downtime deployment 
- healthcheck 

## v3.5.0 (2022-03-31) 
- fix 
- pg-restore-data, pg-dump-data 
- pg-dump-data command 

## v3.4.0 (2022-02-28) 
- --mode help 
- bash command, improved pg-dump 
- docker repository and tag in messages 
- success message when image pushed 

## v3.3.0 (2022-01-17) 
- improved checking environments, new --check-env argument 
- fixed saving encrypted environment to file, improved checking environments 

## v3.2.0 (2022-01-17) 
- saving encrypted environment to file 
- saving decrypted environment to file 

## v3.1.1 (2022-01-04) 
- not required project_path nor connections 

## v3.1.0 (2021-12-28) 
- updated CLI, improved error messages 
- refactoring connections 
- removing environment_id prefix from proxy docker-compose file 
- refactoring docker connection 
- using docker context connection 
- create context 
- Production/Stable in setup.py 
- refactoring docker commands 
- DOCKER_HOST vs -H in favor of new Docker compose version 

## v2.4.1 (2021-12-19) 
- redundant environment for push command 

## v2.4.0 (2021-12-19) 
- redundant environment for build command 

## v2.3.0 (2021-12-12) 
- output of mismatched environments comparison 

## v2.2.0 (2021-11-21) 
- config option to set deterministic encryption 
- except ImportError of cryptography libraries 

## v2.1.0 (2021-11-20) 
- deterministic encryption by default 

## v2.0.2 (2021-11-19) 
- multiple DEV environments (containing dev in ID) 

## v2.0.1 (2021-11-19) 
- fixed duplicated output of decrypted environment 

## v2.0.0 (2021-11-19) 
- encoding/decoding environment files 
- refactoring command line interface 
- uploading postgres conf to host 

## v1.8.1 (2021-09-13) 
- docker push by environment 

## v1.8.0 (2021-09-09) 
- option to override manager config via parameters 

## v1.7.0 (2021-08-10) 
- up, run, removed collectstatic step 

## v1.6.3 (2021-04-24) 
- configurable dockerfile 
- fixed parsing arguments with = in params 
- upload context, v1.6.2 

## v1.6.1 (2021-04-17) 
- removed origin settings, added host mode instead 
- remote/host origin 

## v1.6.0 (2021-04-17) 
- mantis mode 
- reload(), deploy() commands 

## v1.5.1 (2021-04-17) 
- ignoring copying files when using --no-ssh directive 
- upload_docker_configs command upload mantis config as well 

## v1.5.0 (2021-04-17) 
- command to upload docker configs 
- --no-ssh, upload command uploads environment and compose files 
- reloading webserver as the last deployment step 

## v1.4.0 (2021-04-12) 
- updated deployment 
- updated manager to use config json file instead of environment variables 
- cache config 

## v1.3.1 (2021-03-03) 
- pull command 

## v1.3.0 (2020-12-09) 
- exec() command 
- removed .htpasswd and temporary workaround for existing rqworker 
- sleeping 10 seconds before reloading worker 
- waiting 5 seconds instead of 3 when restarting containers (required for rq workers) 
- waiting 3 seconds before creating new restart container during deployment 
- fixed deployment 
- updated deployment 
- CONFIGS_FOLDER_PATH setting 

## v1.2.1 (2020-07-18) 
- fixed deploying 

## v1.2.0 (2020-07-18) 
- custom port and queue settings 
- fixed build method 
- remove method takes params 
- push method 
- custom build params using MANTIS_BUILD_ARGS setting 
- loading environment 
- build takes params, environment compose prefixes 

## v1.0.0 (2020-06-19) 
- MANTIS_COMPOSE_NAME setting for multi-tenant solutions 

## v0.9.0 (2020-06-17) 
- pg_dump and pg_restore commands 
- refactoring nginx to webserver 
- refactoring 
- docker swarm 
- Revert "add MANAGE_FILE variable" 
- add MANAGE_FILE variable 

## v0.8.2 (2020-03-13) 
- fixing pgpass 

## v0.8.1 (2020-03-13) 
- fixing pgpass

## v0.8.0 (2020-03-13) 
- updated psql command 

## v0.7.0 (2020-03-12) 
- checking correct command 

## v0.6.0 (2020-03-11) 
- clean command 

## v0.5.0 (2020-03-11)
- environment is not mandatory for build command

## v0.4.0 (2020-03-11)
- absolute imports 

## v0.3.0 (2020-03-11)
- fixing command_line 

## v0.2.0 (2020-03-11)
- execution from command line 

## v0.1.0 (2020-03-11)
- setup.entry_points 
- setup 
