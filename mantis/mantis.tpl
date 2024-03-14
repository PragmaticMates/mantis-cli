{
  "extensions": {
    "Django": {
      "service": null
    },
    "Postgres": {
      "service": null
    },
    "Nginx": {
      "service": null
    }
  },
  "encryption": {
    "deterministic": true,
    "folder": "<MANTIS>"
  },
  "configs": {
    "folder": "<MANTIS>/.."
  },
  "build": {
    "tool": "compose",
    "args": {}
  },
  "compose": {
    "command": "docker-compose",
    "folder": "<MANTIS>/../compose"
  },
  "environment": {
    "folder": "<MANTIS>/../environments",
    "file_prefix": ""
  },
  "zero_downtime": [],
  "project_path": "~",
  "connections": {
  }
}
