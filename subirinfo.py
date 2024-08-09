import json
import os
import threading
import time
import logging
import config
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from xray_service import (
    getStatusXrayCloud,
    set_thread_local_account,
    get_thread_local_account,
    get_next_client
)
from CacheIssue import CacheIssue
from test_processor import process_testcases
import retry_util  # Importa el módulo para threading.local
from accessValidator import accessValidator

# Configuración del logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.StreamHandler()])
logger = logging.getLogger()

# Validar accesos
res = accessValidator()
if res == 0:
    logger.info("...Accesos Validados...")
    logger.info("****************************************************")
else:
    logger.error(f"...Accesos NO Validados [{res}]...")
    logger.info("****************************************************")
    sys.exit("La validación de accesos falló. Deteniendo la ejecución.")




# Variables globales para conteo de operaciones
tests_updated_successfully = 0
tests_updated_failed = 0
testProcesados = 0

# Configuración de rutas de caché
cache_paths = {
    "testcases": "/tmp/testcase/",
    "testsets": "/tmp/testsets/",
    "testruns": "/tmp/testruns/",
    "testplans": "/tmp/testplans/",
    "testexecs": "/tmp/testexecs/",
    "urls": "/tmp/urls/"
}

# Número global de hilo
NUM_THREADS = 25  # Ajusta según tus necesidades

def process_key(keyIssueServer):
    client = get_next_client()
    set_thread_local_account(client)
    
    if cache_cloud.get_data(keyIssueServer):  # Buscamos issues que si existen en cache
        dataServer = cache_server.get_data(keyIssueServer).json
        process_testcases(dataServer, cache_cloud.get_data(keyIssueServer).json)
    else:  # Buscamos issues que no existen en cache
        print(f"No existe en cloud asi que buscamos por API {keyIssueServer}")

def process_keys(filtered_keys, max_to_process):
    global tests_updated_successfully, tests_updated_failed
    count = 0
    with ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
        futures = []
        for keyIssueServer in filtered_keys:
            if count >= max_to_process:
                break  # Detiene la iteración si se ha alcanzado el máximo
            futures.append(executor.submit(process_key, keyIssueServer))
            count += 1  # Incrementa el contador después de procesar un elemento

        for future in as_completed(futures):
            try:
                future.result()  # Obtenemos el resultado para manejar excepciones
                tests_updated_successfully += 1
            except Exception as e:
                logger.error(f"Error procesando key: {e}")
                tests_updated_failed += 1

def main(sortProject=[], testToProcess=[]):
    global cache_server, cache_cloud

    caches_server = {key: CacheIssue(f'{path}in/', f'{path}out/', key, "server") for key, path in cache_paths.items()}
    caches_cloud = {key: CacheIssue(f'{path}in/', f'{path}out/', key, "cloud") for key, path in cache_paths.items()}

    cache_server = caches_server["testcases"]
    cache_cloud = caches_cloud["testcases"]

    max_to_process = 20  # Define cuántos elementos quieres procesar

    # Leer claves de ErrorTestCase.json
    error_testcases_file = 'logs/ErrorTestCase.json'
    error_testcases = []
    if os.path.exists(error_testcases_file):
        with open(error_testcases_file, 'r', encoding='utf-8') as f:
            error_testcases = [entry['key'] for entry in json.load(f)]
        # Vaciar el contenido de ErrorTestCase.json después de leer
        with open(error_testcases_file, 'w', encoding='utf-8') as f:
            json.dump([], f)

    # Leer claves ya procesadas de TestCaseReady.json
    test_case_ready_file = 'logs/TestCaseReady.json'
    test_case_ready = []
    if os.path.exists(test_case_ready_file):
        with open(test_case_ready_file, 'r', encoding='utf-8') as f:
            test_case_ready = json.load(f)

    # Combinar claves fallidas con nuevas claves a procesar, excluyendo las que ya están listas
    all_test_to_process = list(set(testToProcess + error_testcases) - set(test_case_ready))

    def filter_keys(keys, sortProject, testToProcess):
        filtered_keys = set()

        if not sortProject and not testToProcess:
            return keys
        
        # Ordenar y filtrar por sortProject
        for project in sortProject:
            for key in keys:
                if key.startswith(project):
                    filtered_keys.add(key)
        
        # Filtrar por testToProcess
        for item in testToProcess:
            if '-' in item:
                if item in keys:
                    filtered_keys.add(item)
            else:
                for key in keys:
                    if key.startswith(item):
                        filtered_keys.add(key)
        
        return list(filtered_keys)

    # Primera ejecución
    logger.info("Primera ejecución del procesamiento de claves.")
    all_keys = cache_server.get_keys()
    filtered_keys = filter_keys(all_keys, sortProject, all_test_to_process)
    process_keys(filtered_keys, max_to_process)

    # Leer claves procesadas y actualizar registros
    processed_successfully = []
    if os.path.exists(test_case_ready_file):
        with open(test_case_ready_file, 'r', encoding='utf-8') as f:
            processed_successfully = json.load(f)

    # Segunda ejecución para reprocesar errores
    if os.path.exists(error_testcases_file):
        with open(error_testcases_file, 'r', encoding='utf-8') as f:
            error_testcases = [entry['key'] for entry in json.load(f)]

        if error_testcases:
            logger.info(f"Reprocesando {len(error_testcases)} tests fallidos.")
            process_keys(error_testcases, max_to_process)
            
            # Leer claves procesadas y actualizar ErrorTestCase.json
            error_testcases = []
            if os.path.exists(error_testcases_file):
                with open(error_testcases_file, 'r', encoding='utf-8') as f:
                    error_testcases = json.load(f)

            error_testcases_dict = {entry['key']: entry for entry in error_testcases}
            with open(test_case_ready_file, 'r', encoding='utf-8') as f:
                test_case_ready = json.load(f)
            
            for key in test_case_ready:
                if key in error_testcases_dict:
                    del error_testcases_dict[key]

            with open(error_testcases_file, 'w', encoding='utf-8') as f:
                json.dump(list(error_testcases_dict.values()), f, indent=4)
            
            logger.info(f"Finalizado el reprocesamiento de tests fallidos. Total resueltos: {tests_updated_successfully}, Total no resueltos: {tests_updated_failed}")

if __name__ == "__main__":
    print(config.sort)
    print(config.process)

    sortProject = config.sort.split(',') if config.sort else []
    testToProcess = config.process.split(',') if config.process else []
    print(f"sortProject: {sortProject}")
    print(f"testToProcess {testToProcess}")
    main(sortProject, testToProcess)

