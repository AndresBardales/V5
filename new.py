import json
import os

def split_test_sets(file_path, output_dir, num_parts=16):
    # Leer el archivo JSON completo
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Asegurarse de que el directorio de salida exista
    os.makedirs(output_dir, exist_ok=True)

    # Calcular el tamaño de cada parte
    total_issues = len(data['issues'])
    part_size = (total_issues // num_parts) + 1

    # Dividir los datos y escribirlos en archivos separados
    for i in range(num_parts):
        part_data = {
            'total': min(part_size, total_issues - i * part_size),
            'issues': data['issues'][i * part_size:(i + 1) * part_size]
        }
        part_file_path = os.path.join(output_dir, f'testSets_part_{i + 1}.json')
        with open(part_file_path, 'w', encoding='utf-8') as part_file:
            json.dump(part_data, part_file, indent=4)

    print(f'División completa. Archivos guardados en {output_dir}')

# Usar la función
split_test_sets('testSets.json', 'testSets_parts')
