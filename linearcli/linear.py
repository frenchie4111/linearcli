#!/usr/bin/python3

import sys
from typing import Dict, List, Optional, TypedDict
import json
import os

import requests
from requests import api

def send_query(apikey, query) -> dict:
    res = requests.post(
        'https://api.linear.app/graphql',
        json=dict(
            query=query
        ),
        headers={
            "Authorization": apikey
        }
    )
    # print(query)
    assert res.status_code == 200, res.json()
    return res.json()

GET_TEAMS = """
query Teams {
    teams {
        nodes {
            id
            name
        }
    }
}
"""

GET_ME = """
query Me {
    viewer {
        id
    }
}
"""

GET_STATES = """
query States {
    workflowStates(
        filter: {
            team: {
                id: {
                    eq: "<teamId>"
                }
            }
        }
    ) {
        nodes {
            id
            name
            team {
                id
            }
        }
        pageInfo {
            hasNextPage
            endCursor
        }
    }
}
"""

GET_USERS = """
query Users {
    users(
        <cursor>
    ) {
        nodes {
            id
            name
            avatarUrl
        }
        pageInfo {
            hasNextPage
            endCursor
        }
    }
}
"""

GET_PROJECTS = """
query Projects {
    projects(
        <cursor>
    ){
        nodes {
            id
            name
            teams {
                nodes {
                    id
                }
            }
            slugId
        }
        pageInfo {
            hasNextPage
            endCursor
        }
    }
}
"""

SEARCH_ISSUES = """
query Issues {
    issueSearch(
        first: 100,
        query: "<query>"
    ) {
        nodes {
            id
            title
            description
            identifier
            project {
                id
                name
            }
        }
    }
}
"""

class Team(TypedDict):
        id: str
        name: str

class State(TypedDict):
    id: str
    name: str
    team: Team

class User(TypedDict):
    id: str
    name: str
    avatarUrl: Optional[str]

class Project(TypedDict):
    id: str
    name: str
    teams: List[Team]
    slugId: str

class Config(TypedDict):
    apikey: str
    teams: List[Team]
    users: List[User]
    projects: List[Project]
    states: List[State]
    teams_to_projects: Dict[str, List[str]]
    projects_by_id: Dict[str, Project]
    states_by_team: Dict[str, Dict[str, str]]
    me: str

    default_team: Optional[str]

def get_config_path():
    os.makedirs(os.path.expanduser("~/.linear/"), exist_ok=True)
    os.makedirs(os.path.expanduser("~/.linear/icons/"), exist_ok=True)
    return os.path.expanduser('~/.linear/data.json')

def load_config() -> Config:
    if not os.path.exists(get_config_path()):
        return {}
    with open(get_config_path(), 'r') as f:
        return json.load(f)

def save_config(config: Config) -> None:
    with open(get_config_path(), 'w') as f:
        json.dump(config, f, indent=4)

def get_icon_path(user_id):
    return os.path.expanduser("~/.linear/icons/") + user_id + ".png"

def download_icon(user_id, url):
    res = requests.get(url)
    with open(get_icon_path(user_id), 'wb') as f:
        f.write(res.content)

def init(apikey:Optional[str] = None, init="all"):
    config = load_config()

    if apikey is None:
        apikey = config['apikey']
    else:
        config['apikey'] = apikey

    if init == "all" or init == "me":
        print("Syncing Me")
        me = send_query(apikey, GET_ME)
        config['me'] = me["data"]["viewer"]["id"]

    if init == "all" or init == "teams":
        print("Syncing Teams")
        teams = send_query(apikey, GET_TEAMS)
        config['teams'] = teams["data"]["teams"]["nodes"]
        if 'default_team' not in config or config['default_team'] is None and len(config['teams']) > 0:
            print("Setting default team to: ", config['teams'][0]["name"], "(", config['teams'][0]['id'], ")")
            print("Change with linearcli config default_team <team_id>")
            config['default_team'] = config['teams'][0]['id']

    if init == "all" or init == "states":
        print("Syncing States")
        states = []
        for team in config['teams']:
            res = send_query(apikey, GET_STATES.replace("<teamId>", team["id"]))
            states.extend(res["data"]["workflowStates"]["nodes"])
        config['states'] = states
        states_by_team = {}
        for state in states:
            team_id = state["team"]["id"]
            if team_id not in states_by_team:
                states_by_team[team_id] = {}
            states_by_team[team_id][state["name"]] = state["id"]
        config["states_by_team"] = states_by_team

    if init == "all" or init == "users":
        print("Syncing Users")
        users = []
        cursor = "first: 100"
        while cursor:
            res = send_query(apikey, GET_USERS.replace("<cursor>", cursor))
            has_next_page = res["data"]["users"]["pageInfo"]["hasNextPage"]
            users.extend(res["data"]["users"]["nodes"])
            if has_next_page:
                cursor = f"first: 100, after: \"{res['data']['users']['pageInfo']['endCursor']}\""
            else:
                cursor = None
        config["users"] = users

    if init == "all" or init == "avatars":
        for user in config["users"]:
            if user["avatarUrl"] is None:
                continue
            download_icon(user["id"], user["avatarUrl"])

    if init == "all" or init == "projects":
        print("Syncing Projects")
        projects = []
        cursor = "first: 100"
        while cursor:
            res = send_query(apikey, GET_PROJECTS.replace("<cursor>", cursor))
            has_next_page = res["data"]["projects"]["pageInfo"]["hasNextPage"]
            projects.extend(res["data"]["projects"]["nodes"])
            if has_next_page:
                cursor = f"first: 100, after: \"{res['data']['projects']['pageInfo']['endCursor']}\""
            else:
                cursor = None

        teams_to_projects = {}
        projects_by_id = {}
        for project in projects:
            projects_by_id[project["id"]] = project
            for team in project["teams"]["nodes"]:
                teams_to_projects[team["id"]] = teams_to_projects.get(team["id"], [])
                teams_to_projects[team["id"]].append(project["id"])
        config["projects"] = projects
        config["teams_to_projects"] = teams_to_projects
        config["projects_by_id"] = projects_by_id

    save_config(config)

def set_config(key: str, value: str):
    config = load_config()
    config[key] = value
    save_config(config)

def create_issue(config, title, project_id=None, team_id=None, assignee_id=None, state_id=None, description="Created by miscript", ):
    if team_id is None:
        team_id = config["default_team"]

    if state_id is None:
        state_id = config["states_by_team"][team_id]["Todo"]

    project_part = f"projectId: \"{project_id}\"" if project_id else ""

    if assignee_id is None:
        assignee_id = config["me"]

    query = f"""
    mutation IssueCreate {{
        issueCreate(
            input: {{
                title: "{title}"
                description: "{description}"
                teamId: "{team_id}"
                stateId: "{state_id}"
                assigneeId: "{assignee_id}"
                {project_part}
            }}
        ) {{
            success
            issue {{
                id
                title
                identifier
            }}
        }}
    }}
    """
    res = send_query(config['apikey'], query)
    return res["data"]["issueCreate"]["issue"]["identifier"]

help = """Linear CLI

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
"""


def main():
    args = sys.argv

    if len(args) == 1:
        print(help)
        return

    args.pop(0)
    command = args.pop(0)

    if command == 'help':
        print(help)
        return

    if command == 'init':
        init(*args)
        return

    config = load_config()

    if config["apikey"] is None:
        print("No apikey found. Please run 'linearcli init [apikey]'")
        return

    if command == 'sync':
        init(None, *args)
        return

    if command == 'config':
        set_config(*args)
        return

    apikey = config['apikey']
    if command == 'create':
        print(create_issue(config, *args), end="")
        return

    if command == "listteams":
        teams = config["teams"]
        items = []
        for team in teams:
            items.append({
                "uid": team["id"],
                "title": team["name"],
                "arg": team["id"],
            })
        print(json.dumps({"items": items}, indent=4))
        return

    if command == "listprojectsforteam":
        team_id = args.pop(0)
        projects = config["teams_to_projects"][team_id]
        items = []
        for project_id in projects:
            project = config["projects_by_id"][project_id]
            items.append({
                "uid": project["id"],
                "title": project["name"],
                "arg": project["id"],
            })
        print(json.dumps({"items": items}, indent=4))
        return

    if command == "listprojectslugs":
        items = []
        for project in config["projects"]:
            items.append({
                "uid": project["id"],
                "title": project["name"],
                "arg": project["slugId"],
            })
        print(json.dumps({"items": items}, indent=4))
        return

    if command == "listusers":
        users = config["users"]
        items = []
        for user in users:
            items.append({
                "uid": user["id"],
                "title": user["name"],
                "arg": user["id"],
                "icon": {
                    "path": get_icon_path(user["id"]),
                }
            })
        print(json.dumps({"items": items}, indent=4))
        return

    if command == "search":
        query = args.pop(0)

        results = send_query(apikey, SEARCH_ISSUES.replace("<query>", query))
        issues = []
        for issue in results["data"]["issueSearch"]["nodes"]:
            project = "No Project"
            if issue["project"] and issue["project"]["name"]:
                project = issue["project"]["name"]
            issues.append({
                "uid": issue["id"],
                "title": issue["title"],
                "subtitle": project + " " + str(issue["description"] if issue["description"] else ""),
                "arg": issue["identifier"],
            })

        print(json.dumps({"items": issues, "query": query}, indent=4))

        return

    print("Dont understand: {query}", args )

if __name__ == '__main__':
    main()
