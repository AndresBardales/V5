import logging
import json
import os
import config
from xray_service import (
    update_test_type,
    update_gherkin_test_definition,
    update_unstructured_test_definition,
    add_test_step,
    update_precondition,
    add_preconditions_to_test,
    add_test_sets_to_test,
    escape_definition_text
)
logger = logging.getLogger()

# Leer archivo preconditions.json
def read_preconditions():
    with open('preconditions.json', 'r', encoding='utf-8') as f:
        return json.load(f)

preconditions_data = read_preconditions()

# Leer archivo testSets.json
def read_test_sets():
    with open('testSets.json', 'r', encoding='utf-8') as f:
        return json.load(f)

test_sets_data = read_test_sets()

def get_precondition_id(precondition_key):
    for issue in preconditions_data['issues']:
        if issue['key'] == precondition_key:
            return issue.get(f'id{config.ambiente}')
    return None

def get_test_set_ids(test_key):
    for issue in test_sets_data['issues']:
        if issue['key'] == test_key:
            return [ts.get(f'id{config.ambiente}') for ts in issue.get('associated_test_sets', [])]
    return []

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

def log_test_case_ready(test_key):
    log_file = 'logs/TestCaseReady.json'
    if os.path.exists(log_file):
        with open(log_file, 'r', encoding='utf-8') as f:
            test_cases = json.load(f)
    else:
        test_cases = []

    test_cases.append(test_key)

    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump(test_cases, f, indent=4)

def log_precondition_ready(precondition_key):
    log_file = 'logs/preconditionReadyUpdated.json'
    if os.path.exists(log_file):
        with open(log_file, 'r', encoding='utf-8') as f:
            preconditions = json.load(f)
    else:
        preconditions = []

    preconditions.append(precondition_key)

    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump(preconditions, f, indent=4)

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

def has_been_processed(test_key, processed_tests):
    return test_key in processed_tests

def has_been_processed_precondition(precondition_key, processed_preconditions):
    return precondition_key in processed_preconditions

def process_testcases(testServer, testCloud):
    issue_id = testCloud['id']
    test_key = testServer.get("key")
    test_type = testServer.get('type')
    print(test_type)
    definition = testServer.get('definition')
    steps = testServer.get('steps', [])  # Obtener los pasos del test, si existen

    logger.info(f"Processing test: {test_key} with type: {test_type}")

    try:
        with open('logs/TestCaseReady.json', 'r', encoding='utf-8') as f:
            processed_tests = json.load(f)

        if has_been_processed(test_key, processed_tests):
            logger.info(f"Test Case {test_key} already processed.")
            print("Test Case ignorado")
            return

        # Actualizar el tipo de test
        update_test_type(issue_id, test_type)

        if test_type == 'Manual':
            # Iterar sobre los pasos del test manual y agregarlos
            print(f"steps: {steps}")
            for step in steps:
                action = step.get('fields').get('Action')
                data = step.get('fields').get('Data')
                result = step.get('fields').get('ExpectedResult')
                add_test_step(issue_id, action, data, result)
        else:
            # Actualizar la definición del test
            if test_type == 'Cucumber':
                update_gherkin_test_definition(issue_id, definition)
            else:
                update_unstructured_test_definition(issue_id, definition)

        # Vincular test sets asociados
        test_set_ids = get_test_set_ids(test_key)
        print(f"test_set_ids: {test_set_ids}")
        if test_set_ids:
            try:
                res = add_test_sets_to_test(issue_id, test_set_ids)
                logger.info(f"Associated test sets to {res}")
            except Exception as e:
                logger.error(f"Error associating test sets to {test_key}: {e}")
                log_error(test_key, f"Error associating test sets: {e}")
                print(f"Error al asociar test sets a {test_key}")

        log_test_case_ready(test_key)
        print("Test Case procesado por primera vez")

    except Exception as e:
        logger.error(f"Error procesando test case {test_key}: {e}")
        log_error(test_key, str(e))
        print("Test Case con Error")

    try:
        # Procesar precondiciones
        preconditions = testServer.get('precondition', [])
        precondition_ids = []
        with open('logs/preconditionReadyUpdated.json', 'r', encoding='utf-8') as f:
            processed_preconditions = json.load(f)

        for precondition in preconditions:
            precondition_key = precondition.get('preconditionKey')
            precondition_id = get_precondition_id(precondition_key)

            if precondition_id:
                if not has_been_processed_precondition(precondition_key, processed_preconditions):
                    precondition_type = precondition.get('type')
                    precondition_definition = precondition.get('condition')
                    try:
                        update_precondition(precondition_id, precondition_type, precondition_definition)
                        precondition_ids.append(precondition_id)
                        log_precondition_ready(precondition_key)
                        print("Precondition vinculada y Actualizada")
                    except Exception as e:
                        logger.error(f"Error updating precondition {precondition_key}: {e}")
                        log_precondition_error(precondition_key, str(e))
                        print("Error al actualizar Precondition")
                else:
                    precondition_ids.append(precondition_id)
                    print("Precondition no Actualizada pero si vinculada")

        if precondition_ids:
            res = add_preconditions_to_test(issue_id, precondition_ids)
            print(res)
    except Exception as e:
        logger.error(f"Error procesando precondiciones para {test_key}: {e}")
        log_error(test_key, str(e))

    logger.info(f"Finished processing test: {test_key}")
