import requests
import os
import time
from dotenv import load_dotenv
from retry_util import retry_request, make_request, get_thread_local_account, set_thread_local_account, client_delay_info, client_delay_lock
import threading
import json
import re

thread_local = threading.local()

load_dotenv(override=True)

XRAY_BASE_URL = os.getenv('XRAY_BASE_URL')
CLIENT_IDS = os.getenv('CLIENT_IDS').split(',')
CLIENT_SECRETS = os.getenv('CLIENT_SECRETS').split(',')

RETRIES = 10
DELAY = 6
MAX_BACKOFF = 60
SLEEP_BETWEEN_REQUESTS = 0.1  # Retardo en segundos entre solicitudes

if len(CLIENT_IDS) != len(CLIENT_SECRETS):
    raise ValueError("Las listas de CLIENT_IDS y CLIENT_SECRETS deben tener la misma longitud")

clients = [{'id': id, 'secret': secret, 'token': None, 'last_request_time': 0} for id, secret in zip(CLIENT_IDS, CLIENT_SECRETS)]
current_client_index = 0

def get_next_client():
    global current_client_index
    client = clients[current_client_index]
    current_client_index = (current_client_index + 1) % len(clients)
    return client

def get_auth_token(client):
    url = "https://xray.cloud.getxray.app/api/v2/authenticate"
    response = retry_request(make_request, client, url, method='POST', json={
        'client_id': client['id'],
        'client_secret': client['secret']
    }, retries=RETRIES, delay=DELAY)
    token = response.text.strip('"')
    return token

def send_graphql_request(query, variables=None, client=None):
    if client is None:
        client = get_thread_local_account()

    if client['token'] is None:
        client['token'] = get_auth_token(client)

    headers = {
        'Authorization': f'Bearer {client["token"]}',
        'Content-Type': 'application/json'
    }
    print(f"Petición con el cliente: {client['id']}")
    payload = {'query': query}
    if variables:
        payload['variables'] = variables

    attempt = 0
    while attempt < RETRIES:
        current_time = time.time()
        time_since_last_request = current_time - client['last_request_time']
        if time_since_last_request < SLEEP_BETWEEN_REQUESTS:
            time.sleep(SLEEP_BETWEEN_REQUESTS - time_since_last_request)

        try:
            response = requests.post(XRAY_BASE_URL, headers=headers, json=payload)
            response.raise_for_status()
            client['last_request_time'] = time.time()
            json_response = response.json()
            if 'errors' in json_response:
                print(f"Errores encontrados: {json_response['errors']}")
                raise Exception(json_response['errors'])
            return json_response
        except requests.exceptions.RequestException as e:
            if response.status_code == 429:
                with client_delay_lock:
                    backoff = client_delay_info[client['id']]['delay']
                    print(f"Attempt {attempt + 1} failed with error: {response.status_code} {response.reason}. Too Many Requests. Client ID: {client['id']} Retrying in {backoff} seconds...")
                time.sleep(backoff)
                attempt += 1
            elif response.status_code == 401:
                client['token'] = get_auth_token(client)
            else:
                print(f"Request failed with status code {response.status_code}: {response.text}")
                raise e

    raise Exception(f"All {RETRIES} attempts failed or encountered a non-retryable error.")

def getStatusXrayCloud():
    query = """
    {
        getStatus(name: "PASSED") {
            name
            description
            final
            color
        }
    }
    """
    client = get_next_client()
    set_thread_local_account(client)
    return send_graphql_request(query)

def escape_definition_text(definition):
    if definition is None:
        return ""
    definition = definition.replace('\\', '\\\\')
    definition = definition.replace('"', '\\"')
    definition = definition.replace('\n', '\\n')
    definition = definition.replace('\r', '\\r')
    definition = definition.replace('\t', '\\t')
    definition = re.sub(r'[^\x20-\x7E]', '', definition)  # Remove non-printable characters
    return definition

def add_test_step(issue_id, action, data, result):
    escaped_action = escape_definition_text(action)
    escaped_data = escape_definition_text(data)
    escaped_result = escape_definition_text(result)
    
    query = f'''
    mutation {{
        addTestStep(
            issueId: "{issue_id}",
            step: {{
                action: "{escaped_action}",
                data: "{escaped_data}",
                result: "{escaped_result}"
            }}
        ) {{
            id
            action
            data
            result
        }}
    }}
    '''
    client = get_thread_local_account()
    try:
        response = send_graphql_request(query, client=client)
        return response
    except Exception as e:
        log_error(issue_id, f"Error adding test step: {e}")
        raise e

def update_test_type(issue_id, test_type):
    query = f'''
    mutation {{
        updateTestType(issueId: "{issue_id}", testType: {{name: "{test_type}"}} ) {{
            issueId
            testType {{
                name
                kind
            }}
        }}
    }}
    '''
    client = get_thread_local_account()
    try:
        response = send_graphql_request(query, client=client)
        return response
    except Exception as e:
        log_error(issue_id, f"Error updating test type: {e}")
        raise e

def update_unstructured_test_definition(issue_id, unstructured):
    escaped_unstructured = escape_definition_text(unstructured)
    query = f'''
    mutation {{
        updateUnstructuredTestDefinition(issueId: "{issue_id}", unstructured: "{escaped_unstructured}" ) {{
            issueId
            unstructured
        }}
    }}
    '''
    client = get_thread_local_account()
    try:
        response = send_graphql_request(query, client=client)
        return response
    except Exception as e:
        log_error(issue_id, f"Error updating unstructured test definition: {e}")
        raise e

def update_gherkin_test_definition(issue_id, gherkin):
    escaped_gherkin = escape_definition_text(gherkin)
    query = f'''
    mutation {{
        updateGherkinTestDefinition(issueId: "{issue_id}", gherkin: "{escaped_gherkin}" ) {{
            issueId
            gherkin
        }}
    }}
    '''
    client = get_thread_local_account()
    try:
        response = send_graphql_request(query, client=client)
        return response
    except Exception as e:
        log_error(issue_id, f"Error updating gherkin test definition: {e}")
        raise e

def update_precondition(precondition_id, precondition_type, precondition_definition):
    escaped_precondition_type = escape_definition_text(precondition_type)
    escaped_precondition_definition = escape_definition_text(precondition_definition)
    query = f'''
    mutation {{
        updatePrecondition(
            issueId: "{precondition_id}",
            data: {{ preconditionType: {{ name: "{escaped_precondition_type}" }}, definition: "{escaped_precondition_definition}" }}
        ) {{
            issueId
            preconditionType {{
                kind
                name
            }}
            definition
        }}
    }}
    '''
    client = get_thread_local_account()
    try:
        response = send_graphql_request(query, client=client)
        return response
    except Exception as e:
        log_precondition_error(precondition_id, f"Error updating precondition: {e}")
        raise e

def add_preconditions_to_test(test_id, precondition_ids):
    query = f'''
    mutation {{
        addPreconditionsToTest(
            issueId: "{test_id}",
            preconditionIssueIds: {json.dumps(precondition_ids)}
        ) {{
            addedPreconditions
            warning
        }}
    }}
    '''
    client = get_thread_local_account()
    try:
        response = send_graphql_request(query, client=client)
        return response
    except Exception as e:
        log_precondition_error(test_id, f"Error adding preconditions to test: {e}")
        raise e

def log_error(test_key, error_message):
    log_file = 'logs/ErrorTestCase.json'
    if os.path.exists(log_file):
        with open(log_file, 'r', encoding='utf-8') as f:
            errors = json.load(f)
    else:
        errors = []

    errors.append({'key': test_key, 'error': error_message})

    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump(errors, f, indent=4)

def log_precondition_error(precondition_key, error_message):
    log_file = 'logs/preconditionError.json'
    if os.path.exists(log_file):
        with open(log_file, 'r', encoding='utf-8') as f:
            errors = json.load(f)
    else:
        errors = []

    errors.append({'key': precondition_key, 'error': error_message})

    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump(errors, f, indent=4)


def add_test_sets_to_test(issue_id, test_set_ids):
    print(f"test_set_ids: {test_set_ids}")
    query = f'''
    mutation {{
        addTestSetsToTest(
            issueId: "{issue_id}",
            testSetIssueIds: {json.dumps(test_set_ids)}
        ) {{
            addedTestSets
            warning
        }}
    }}
    '''
    print(f"Eso mando: {query}")
    client = get_thread_local_account()
    try:
        response = send_graphql_request(query, client=client)
        return response
    except Exception as e:
        log_precondition_error(test_id, f"Error adding preconditions to test: {e}")
        raise e