# retry_util.py

import time
import requests
import logging
import threading

# Configuración del logger
logger = logging.getLogger('retry_util')
thread_local = threading.local()

# Variable global para manejar los retrasos por cliente
client_delay_info = {}
client_delay_lock = threading.Lock()

def set_thread_local_account(account):
    thread_local.account = account

def get_thread_local_account():
    return getattr(thread_local, 'account', None)

def retry_request(func, client, *args, retries=3, delay=6, **kwargs):
    global client_delay_info

    with client_delay_lock:
        if client['id'] not in client_delay_info:
            client_delay_info[client['id']] = {'delay': delay, 'last_attempt': 0}

    for attempt in range(retries):
        with client_delay_lock:
            client_delay_info[client['id']]['last_attempt'] = time.time()
        
        try:
            response = func(*args, **kwargs)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            if e.response is not None and e.response.status_code == 429:
                with client_delay_lock:
                    current_delay = client_delay_info[client['id']]['delay']
                    last_attempt = client_delay_info[client['id']]['last_attempt']
                    logger.warning(f"Attempt {attempt + 1} failed with error: {e}. Client ID: {client['id']} Too Many Requests. Retrying in {current_delay} seconds...")
                    time_to_wait = current_delay - (time.time() - last_attempt)
                    if time_to_wait > 0:
                        time.sleep(time_to_wait)
            elif e.response is not None and e.response.status_code == 401:
                logger.error(f"Attempt {attempt + 1} failed with error: {e}. Unauthorized. Retrying...")
                return func(*args, **kwargs)  # Retry without delay for authentication errors
            elif e.response is not None and e.response.status_code == 400:
                logger.error(f"Attempt {attempt + 1} failed with error: {e}. Error 400 detected. No retry will be made.")
                break
            else:
                logger.error(f"Attempt {attempt + 1} failed with error: {e}. Retrying in {delay} seconds...")
                if e.response is not None:
                    try:
                        logger.error(f"Error response JSON: {e.response.json()}")
                    except ValueError:
                        logger.error(f"Error response text: {e.response.text}")
            time.sleep(client_delay_info[client['id']]['delay'])
    raise Exception(f"All {retries} attempts failed or encountered a non-retryable error.")

def make_request(url, method='GET', headers=None, json=None, params=None, files=None, auth=None):
    if method.upper() == 'GET':
        return requests.get(url, headers=headers, params=params, auth=auth)
    elif method.upper() == 'POST':
        return requests.post(url, headers=headers, json=json, params=params, files=files, auth=auth)
    elif method.upper() == 'PUT':
        return requests.put(url, headers=headers, json=json, params=params, auth=auth)
    elif method.upper() == 'DELETE':
        return requests.delete(url, headers=headers, params=params, auth=auth)
    else:
        raise ValueError(f"Unsupported HTTP method: {method}")
