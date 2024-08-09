import json
import os
import shutil
import logging
import threading
from datetime import datetime

from Issue import Issue

# Configuración del logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.StreamHandler()])
logger = logging.getLogger()

class CacheIssue:
    def __init__(self, input_dir, output_dir, write_file_prefix, server="server"):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.write_file_prefix = write_file_prefix
        self.server = server
        self.copy_and_rename_files()
        self.data = self.load_data()
        self.new_data = {}  # Almacenar nuevos elementos
        self.current_write_file = self.get_current_write_file()
        self.items = 0
        self.lock = threading.RLock()  # Crear un bloqueo de lectura-escritura

    def copy_and_rename_files(self):
        # Copiar archivos del directorio de salida al de entrada sin renombrar
        for file_name in os.listdir(self.output_dir):
            if (file_name.endswith('.json') or file_name.endswith('.jsonl')) and self.server in file_name:
                shutil.copy(os.path.join(self.output_dir, file_name), os.path.join(self.input_dir, file_name))
                logger.info(f"Archivo {file_name} copiado al directorio de entrada")
                os.remove(os.path.join(self.output_dir, file_name))  # Eliminar el archivo del directorio de salida

    def load_data(self):
        data = {}        
        for file_name in os.listdir(self.input_dir):
            if self.server not in file_name:
                continue
            file_path = os.path.join(self.input_dir, file_name)
            if not os.path.isfile(file_path):
                continue
            logger.info(f"Leyendo archivo: {file_path}")  # Imprime el nombre del archivo
            if file_path.endswith('.json'):
                with open(file_path, 'r') as file:
                    try:
                        issues = json.load(file)
                        data.update({issue['key']: Issue(issue['key'], issue['json']) for issue in issues})
                    except json.JSONDecodeError as e:
                        logger.error(f"Error al leer el archivo JSON {file_path}: {e}")
                        continue
            elif file_path.endswith('.jsonl'):
                with open(file_path, 'r') as file:
                    for line in file:
                        try:
                            issue = json.loads(line)
                            data[issue['key']] = Issue(issue['key'], issue['json'])
                        except json.JSONDecodeError as e:
                            logger.error(f"Error al leer la línea JSON en el archivo {file_path}: {e}")
                            continue        
        return data

    def get_current_write_file(self):
        # Generar el nombre del archivo con la fecha, hora y milisegundos actuales
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        return os.path.join(self.output_dir, f"{self.write_file_prefix}_{self.server}_{timestamp}.jsonl")

    def get_data(self, key):
        with self.lock:  # Adquirir el bloqueo
            issue = self.data.get(key, None)
        return issue if issue else None

    def add_element(self, issue: Issue):
        with self.lock:  # Adquirir el bloqueo
            # Añadir el nuevo elemento al diccionario en memoria
            self.data[issue.key] = issue
            self.new_data[issue.key] = issue  # Añadir a new_data

    def show_cache_count(self):
        logger.info(f"Elementos en la caché {self.server}:  {len(self.data)}")        
    
    def get_keys(self):
        keys = [str(key).strip() for key in self.data.keys()]
        return keys

    def save_to_file(self):
        with self.lock:  # Adquirir el bloqueo
            if not self.new_data:
                logger.info("No hay datos nuevos para guardar.")
                return

            logger.info("Guardando datos en el archivo JSON... " + self.current_write_file + " (" + str(len(self.new_data)) + " elementos)")
            # Convertir new_data a una lista de diccionarios para guardar en JSON
            new_issues_list = [{'key': k, 'json': v.json} for k, v in self.new_data.items()]

            # Guardar los nuevos datos en el archivo JSONL (JSON Lines)
            with open(self.current_write_file, 'a') as file:
                for issue in new_issues_list:
                    file.write(json.dumps(issue) + '\n')

            # Limpiar new_data después de guardar
            self.new_data.clear()

            # Verificar el tamaño del archivo y actualizar current_write_file si es necesario
            if os.path.getsize(self.current_write_file) >= 100 * 1024 * 1024:  # 100 MB
                self.current_write_file = self.get_current_write_file()