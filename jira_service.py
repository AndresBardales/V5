import requests
import os
from dotenv import load_dotenv
from retry_util import retry_request, make_request
from requests.auth import HTTPBasicAuth

load_dotenv(override=True)

JIRA_BASE_URL = os.getenv('JIRA_BASE_URL')
API_TOKEN = os.getenv('API_TOKEN')
USERNAMEJIRA = os.getenv('USERNAMEJIRA')
JIRA_BASE_URL_SERVER = os.getenv('JIRA_BASE_URL_SERVER')
API_TOKEN_SERVER = os.getenv('API_TOKEN_SERVER')

# Variables globales para reintentos
RETRIES = 10
DELAY = 6
# Añadiendo mensaje de depuración para verificar las variables de entorno
print(f"JIRA_BASE_URL: {JIRA_BASE_URL}")
print(f"API_TOKEN: {API_TOKEN[:4]}...") 
print(f"JIRA_BASE_URL_SERVER: {JIRA_BASE_URL_SERVER}")
print(f"API_TOKEN_SERVER: {API_TOKEN_SERVER}")
print(f"USERNAMEJIRA: {USERNAMEJIRA}")
# Muestra solo los primeros caracteres del token por seguridad

def get_issue(issue_id_or_key):
    url = f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_id_or_key}?fields=key,summary"
    headers = {
        'Accept': 'application/json'
    }
    auth = HTTPBasicAuth(USERNAMEJIRA, API_TOKEN)
    
    #print(f"Fetching URL: {url}")
    response = retry_request(make_request, url, method='GET', headers=headers, auth=auth, retries=RETRIES, delay=DELAY)
    return response.json()

def get_userCloud(userEmail):
    url = f"{JIRA_BASE_URL}/rest/api/3/user/search?query={userEmail}"
    print(f"URL: {url}")
    headers = {
        'Accept': 'application/json'
    }
    auth = HTTPBasicAuth(USERNAMEJIRA, API_TOKEN)
    
    #print(f"Fetching URL: {url}")
    response = retry_request(make_request, url, method='GET', headers=headers, auth=auth, retries=RETRIES, delay=DELAY)
    return response.json()


def getIssueJQL(query):
    url = f"{JIRA_BASE_URL}/rest/api/3/search"
    headers = {
        'Accept': 'application/json'
    }
    auth = HTTPBasicAuth(USERNAMEJIRA, API_TOKEN)
    max_results = 100
    start_at = 0
    all_issues = []

    while True:
        body_data = {
            "fields": ["summary", "key"],
            "jql": query,
            "maxResults": max_results,
            "startAt": start_at
        }

        print(f"Fetching URL: {url}")
        print(f"CONSULTA JQL: {body_data}")
        response = retry_request(make_request, url, method='POST', headers=headers, json=body_data, auth=auth, retries=RETRIES, delay=DELAY)
        response_json = response.json()

        # Añadir los problemas obtenidos a la lista total de problemas
        issues = response_json.get('issues', [])
        all_issues.extend(issues)

        # Verificar si se han recuperado todos los problemas
        if len(issues) < max_results:
            break

        # Actualizar start_at para la siguiente página
        start_at += max_results

    # Devolver todos los problemas en una sola estructura de datos
    return {
        "expand": response_json.get("expand"),
        "startAt": 0,
        "maxResults": max_results,
        "total": response_json.get("total"),
        "issues": all_issues
    }

def getMyselfCloud(issue_id_or_key):
    url = f"{JIRA_BASE_URL}/rest/api/3/myself"
    headers = {
        'Accept': 'application/json'
    }
    auth = HTTPBasicAuth(USERNAMEJIRA, API_TOKEN)
    
    #print(f"Fetching URL: {url}")
    response = retry_request(make_request, url, method='GET', headers=headers, auth=auth, retries=1, delay=1)
    return response.json()

# Jira SERVER con autenticación Bearer y paginación customfield_10135

def getIssueJQLServer(query, fields, only=None):
    url = f"{JIRA_BASE_URL_SERVER}/rest/api/2/search"
    headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {API_TOKEN_SERVER}'
    }
    max_results = 100
    start_at = 0
    total_issues = []

    # Usar el campo customfield de config.execution_config
    customfield = config.execution_config['testplan_customfield']

    while True:
        body_data = {
            "fields": fields,  # Pasar directamente la lista de campos
            "jql": query,
            "maxResults": max_results,
            "startAt": start_at
        }

        print(f"Fetching URL: {url} (startAt={start_at})")
        response = retry_request(make_request, url, method='POST', headers=headers, json=body_data, retries=RETRIES, delay=DELAY)
        
        data = response.json()
        for issue in data['issues']:
            # Renombrar el campo customfield a 'testplan'
            issue['fields']['testplan'] = issue['fields'].pop(customfield, None)
        total_issues.extend(data['issues'])

        # Check if the limit specified by 'only' is reached
        if only is not None and len(total_issues) >= only:
            return total_issues[:only]

        if start_at + max_results >= data['total']:
            break
        start_at += max_results

    return total_issues
def getMyselfServer():
    url = f"{JIRA_BASE_URL_SERVER}/rest/api/2/myself"
    headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {API_TOKEN_SERVER}'
    }

    print(f"Fetching URL: {url}")
    response = retry_request(make_request, url, method='GET', headers=headers, retries=1, delay=1)
    data = response.json()

    return data

def getUserServer(user):
    url = f"{JIRA_BASE_URL_SERVER}/rest/api/2/user?username={user}"
    headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {API_TOKEN_SERVER}'
    }

    print(f"Fetching URL: {url}")
    response = retry_request(make_request, url, method='GET', headers=headers, retries=1, delay=1)
    data = response.json()

    return data
#NUEVO EDIT
def get_specific_issue(issue_key, custom_field):
    url = f"{JIRA_BASE_URL_SERVER}/rest/api/2/issue/{issue_key}"
    headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {API_TOKEN_SERVER}'
    }

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        issue_details = response.json()
        custom_field_value = issue_details.get('fields', {}).get(custom_field, 'No custom field found')
        return custom_field_value
    else:
        print(f'Error: {response.status_code}, {response.text}')
        return None