import requests
import os
from dotenv import load_dotenv
from retry_util import retry_request, make_request
load_dotenv()

JIRA_BASE_URL_SERVER = os.getenv('JIRA_BASE_URL_SERVER')
API_TOKEN_SERVER = os.getenv('API_TOKEN_SERVER')

# Variables globales para reintentos
RETRIES = 10
DELAY = 6

def get_test_executions_for_test_plan(testPlanKey):
    url = f"{JIRA_BASE_URL_SERVER}/rest/raven/1.0/api/testplan/{testPlanKey}/testexecution"
    headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {API_TOKEN_SERVER}'
    }

    print(f"Fetching URL: {url}")
    response = retry_request(make_request, url, method='GET', headers=headers, retries=RETRIES, delay=DELAY)
    return response.json()

# Obtener test de TestExecutions
def get_tests_for_testExecutions(testExecKey):
    url = f"{JIRA_BASE_URL_SERVER}/rest/raven/1.0/api/testexec/{testExecKey}/test?detailed=true"
    headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {API_TOKEN_SERVER}'
    }

    all_tests = []
    page = 1
    limit = 100

    while True:
        paginated_url = f"{url}?limit={limit}&page={page}"
        #print(f"Fetching URL: {paginated_url}")
        response = retry_request(make_request, paginated_url, method='GET', headers=headers, retries=RETRIES, delay=DELAY)
        data = response.json()
        
        if not data:
            break

        all_tests.extend(data)
        page += 1

    return all_tests

def getTestRun(testExecution,testRun):
    url = f"{JIRA_BASE_URL_SERVER}/rest/raven/2.0/api/testrun?testExecIssueKey={testExecution}&testIssueKey={testRun}"
    headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {API_TOKEN_SERVER}'
    }

    print(f"Fetching URL: {url}")
    response = retry_request(make_request, url, method='GET', headers=headers, retries=RETRIES, delay=DELAY)
    return response.json()

def getStatusXrayServer():
    url = f"{JIRA_BASE_URL_SERVER}/rest/raven/1.0/api/settings/teststatuses"
    headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {API_TOKEN_SERVER}'
    }

    print(f"Fetching URL: {url}")
    response = retry_request(make_request, url, method='GET', headers=headers, retries=2, delay=1)
    return response.json()
    
    
def getTestInfo(keyTest):
    url = f"{JIRA_BASE_URL_SERVER}/rest/raven/1.0/api/test/{keyTest}/step"
    headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {API_TOKEN_SERVER}'
    }

    print(f"Fetching URL: {url}")
    response = retry_request(make_request, url, method='GET', headers=headers, retries=2, delay=1)
    return response.json()
    