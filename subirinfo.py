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
    get_next_client,
    getTestCasesUpdated
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

def lookUpdatedTest(filter_keys=None):
    caches_cloud = {key: CacheIssue(f'{path}in/', f'{path}out/', key, "cloud") for key, path in cache_paths.items()}
    caches_server = {key: CacheIssue(f'{path}in/', f'{path}out/', key, "server") for key, path in cache_paths.items()}

    cache_server = caches_server["testcases"]
    
    if filter_keys:
        filter_keys = filter_keys.split(',')
    else:
        filter_keys = None

    # Obtén las keys del cache
    cache_keys = cache_server.get_keys()

    # Si filter_keys es None o una lista vacía, no aplicar filtrado
    if filter_keys:
        filtered_keys = [key for key in cache_keys if any(key.startswith(fk) for fk in filter_keys)]
    else:
        filtered_keys = cache_keys

    # Abre el archivo JSON para leer los test cases ya listos
    with open('logs/TestCaseReady.json', 'r') as file:
        testCasesReady = json.load(file)
    
    # Calcula la diferencia entre las keys filtradas y las ya listas
    difference = list(set(filtered_keys) - set(testCasesReady))
    
    # Lista para guardar las keys de los test cases que necesitan edición
    test_cases_to_update = []

    # Paginación - Procesar en lotes de 100
    batch_size = 100
    batches = [difference[i:i + batch_size] for i in range(0, len(difference), batch_size)]
    
    # Usar ThreadPoolExecutor para realizar consultas en paralelo
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(getTestCasesUpdated, batch): batch for batch in batches}
        
        for future in as_completed(futures):
            test_cases_data = future.result()
            
            # Procesar cada test case en el batch
            for testcase in test_cases_data["data"]["getTests"]["results"]:
                key = testcase["jira"]["key"]
                test_type = testcase["testType"]["kind"]
                steps = testcase.get("steps", None)
                gherkin_content = testcase.get("gherkin", None)
                #print(f"steps: {steps}")
                if test_type == "Steps" and steps:
                    # Manual test case with steps, should be updated
                    test_cases_to_update.append(key)
                elif test_type in ["Gherkin", "Cucumber"]:
                    if gherkin_content and gherkin_content != "{}":
                        # Cucumber/Gherkin test case with valid content
                        test_cases_to_update.append(key)
    
    # Guardar las keys en el archivo TestCasesUpdated.json
    with open('logs/TestCasesUpdated.json', 'w') as outfile:
        json.dump(test_cases_to_update, outfile, indent=4)
    
    print(f"Test cases to update: {test_cases_to_update}")

if __name__ == "__main__":
    
    print(config.sort)
    print(config.process)
    if config.process == "ALL":
        config.process=[]

    lookUpdatedTest(config.process)
    sortProject = config.sort.split(',') if config.sort else []
    testToProcess = config.process.split(',') if config.process else []
    print(f"sortProject: {sortProject}")
    print(f"testToProcess {testToProcess}")
    main(sortProject, testToProcess)

