# config.py

import argparse

def get_args():
    parser = argparse.ArgumentParser(description='Descripción de tu script')
    parser.add_argument('--ambiente', type=str, help='Ambiente (DEV o PROD)', required=True)
    parser.add_argument('--sort', type=str)
    parser.add_argument('--process', type=str)
    return parser.parse_args()

# Variables globales
args = get_args()
ambiente = args.ambiente
sort = args.sort
process = args.process
