# utils/logger.py
import logging
import sys

def setup_logger(name: str) -> logging.Logger:
    """
    Configura y retorna un logger estándar para el pipeline ETL.
    """
    logger = logging.getLogger(name)
    
    # Evitamos agregar manejadores duplicados si el logger ya fue instanciado
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        # Formato del log: Fecha - NombreDelModulo - NIVEL - Mensaje
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        
        # Manejador para imprimir en la consola (terminal)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        
        logger.addHandler(console_handler)
        
    return logger