# Linear CLI (Unmaintained)

Simple CLI interface for linear task manager (https://linear.app)


## Usage

### Install:

```
pip install linearcli
```

### Setup:

Generate a personal API key in the linear app, and run `linearcli init <apikey>`

This will create `~/.linear/data.json

### Sync:

The CLI tool creates a local cache of slowly changing data (teams, users,
task states, avatars), you can update the cache by doing `linearcli sync`

### Help:

```
linearcli help
```

```
Linear CLI

Format:
    linearcli [command] [command args]

Commands:
    help
        Prints this help message

    init [apikey]
        Initializes the CLI.
        If apikey is not specified, it will be read from the config file.

    sync [me|teams|states|users|avatars|projects]
        Syncs the local data with linear. Allows for rapid lookup of teams,
            states, users, projects, and avatars.

    config [key] [value]
        Sets a config value.
        Possible keys:
            default_team: The id of the default team to use when creating issues.

    create [*title] [project_id] [team_id] [assignee_id] [state_id] [description]
        Creates an issue on the specified team.
        Only title is required, project_id and team_id defaults can be configured

    search [query]
        Searches for issues in linear, will search all issues you have access to

    listteams
        Lists all synced teams
```
