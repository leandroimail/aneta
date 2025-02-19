import json
import os
import lancedb
from typing import Union, Dict
from dotenv import load_dotenv

load_dotenv()

def create_lancedb_instance(path_db: str = "") -> lancedb.LanceDBConnection:
    """
    Conecta a um banco de dados LanceDB.

    Parâmetros:
      db_path (str): Caminho para o diretório do banco de dados LanceDB.

    Retorna:
      LanceDB: Instância do banco de dados.
    """
    if not path_db:
        path_db = os.getenv("PATH_DB")
        path_data = os.getenv("PATH_DATA")
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


def save_bibliographic_database( type_source: str,
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
    
    records = []
    try:
        table = db.open_table("enriched_data")
        where = f"type_source='{type_source}' AND doi='{doi}'"
        records = table.search().where(where=where).to_list()
    except Exception as e:
        print(f"Error: {e}")
        raise ValueError(f"Erro ao buscar registro: {e}")
    
    return records






if __name__ == "__main__":
    db = create_lancedb_instance()
    save_bibliographic_database("openalex", "10.1234/5678", {"title": "Teste"}, db)
    save_bibliographic_database("openalex", "10.4321/5678", {"title": "Teste2"}, db)

    
    print(fetch_bibliographic_database("openalex", "10.1234/5678", db))
    print(fetch_bibliographic_database("openalex", "10.4321/5678", db))
    
    db._conn.close()
    
    
    
    