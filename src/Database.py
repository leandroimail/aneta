import json
import os
import lancedb
from datetime import timedelta
from typing import Union, Dict
from dotenv import load_dotenv

load_dotenv(os.path.abspath(".conf"))
load_dotenv(os.path.abspath("config/.env"))

def create_lancedb_instance(path_db: str = ".db") -> lancedb.LanceDBConnection:
    """
    Conecta a um banco de dados LanceDB.

    Parâmetros:
      db_path (str): Caminho para o diretório do banco de dados LanceDB.

    Retorna:
      LanceDB: Instância do banco de dados.
    """
    path_db = ".db"
    path_data = os.path.abspath(os.getenv("PATH_DATA", "Data"))
    if not path_db:
        raise ValueError("Caminho do banco de dados não informado")
    if not path_data:
        raise ValueError("Caminho dos dados não informado")
    path_db = os.path.join(path_data, path_db)
    try:
        db = lancedb.connect(path_db)
    except Exception as e:
        raise ValueError("Erro ao conectar ao banco de dados")

    return db


def save_bibliographic_database(type_source: str,
                doi: str, 
                json_data: Union[str, Dict], 
                db: lancedb.LanceDBConnection) -> None:
    """
    Armazena o JSON informado em um banco de dados LanceDB.

    O JSON deve ser um texto que contenha as chaves 'doi' e 'type_source'.
    Os dados serão armazenados em uma tabela chamada 'json_data'.

    Parâmetros:
      db_path (str): Caminho para o diretório do banco de dados LanceDB.
      json_text (str): Texto contendo o JSON.
    """
    try:
        
        if isinstance(json_data, dict):
            data = json.dumps(json_data)
        elif isinstance(json_data, str):
            data = str(json_data)
        elif isinstance(json_data, str):
            data = json_data
    except json.JSONDecodeError as e:
        raise ValueError("Texto JSON inválido") from e
    except Exception as e:
        raise ValueError("Erro ao converter JSON") from e
    
    records = [{
        "vector" : [1],
        "type_source": type_source,
        "doi": doi,        
        "json_text": data
    }]
    try:
        table = db.open_table("enriched_data")
        # table.add(records, mode="append")        
        table.merge_insert(["type_source", "doi"]) \
            .when_matched_update_all()             \
            .when_not_matched_insert_all()         \
            .execute(records)
            
        table.optimize()
        if table.version % 50 == 0:
            table.cleanup_old_versions(older_than=timedelta(seconds=0))
    except ValueError as e:
        try:
            print("Tentando criar a tabela")
            table = db.create_table("enriched_data", data=records)
        except Exception as e:
            raise ValueError(f"Erro ao inserir registro: {e}")
    except Exception as e:
        raise ValueError(f"Erro ao inserir registro: {e}")


def fetch_bibliographic_database(type_source: str, doi: str, db: lancedb.LanceDBConnection) -> Dict:
    """
    Lê um registro JSON de um banco de dados LanceDB.

    Parâmetros:
      db_path (str): Caminho para o diretório do banco de dados LanceDB.
      doi (str): DOI do registro JSON.

    Retorna:
      dict: Dados do registro JSON.
    """
    
    records = {}
    try:
        table = db.open_table("enriched_data")
        where = f"type_source='{type_source}' AND doi='{doi}'"
        records = table.search().limit(1).where(where=where).to_list()
        
        if records:
            records = json.loads(records[0]["json_text"])
    except Exception as e:
        print(f"Error: {e}")
        raise ValueError(f"Erro ao buscar registro: {e}")
    
    return records


    
    
    
    