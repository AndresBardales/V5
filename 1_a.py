import pandas as pd
import json

# Leer el archivo testSets.json
with open('testSets.json', 'r', encoding='utf-8') as file:
    data = json.load(file)

# Crear una lista para almacenar los datos transformados
transformed_data = []

# Recorrer cada issue y cambiar los nombres de las propiedades
for issue in data.get('issues', []):
    transformed_issue = issue.copy()
    transformed_issue['associated_test_sets'] = []
    for associated_test_set in issue.get('associated_test_sets', []):
        transformed_test_set = associated_test_set.copy()
        if 'cloud_id' in associated_test_set:
            transformed_test_set['idPROD'] = associated_test_set['cloud_id']
            del transformed_test_set['cloud_id']
        if 'cloud_id_dev' in associated_test_set:
            transformed_test_set['idDEV'] = associated_test_set['cloud_id_dev']
            del transformed_test_set['cloud_id_dev']
        transformed_issue['associated_test_sets'].append(transformed_test_set)
    transformed_data.append(transformed_issue)

# Crear un nuevo diccionario con los datos transformados
transformed_dict = {
    'total': data['total'],
    'issues': transformed_data
}

# Guardar los cambios en un nuevo archivo
with open('testSets_updated.json', 'w', encoding='utf-8') as file:
    json.dump(transformed_dict, file, indent=4)

print("Archivo actualizado guardado como 'testSets_updated.json'.")
