"""Testes do parser tolerante clean_and_parse_json.

Offline. Cobre o caso que quebrava a consolidação: respostas do gemini com um '}'
extra ("Extra data"), além de vírgula final, blocos markdown e o unwrap {<id>:{...}}.
"""

import pytest

from src.GenerativeAI.LLMUtilExcel import clean_and_parse_json as cp


def test_json_valido_simples():
    assert cp('{"id":"w","a":2}') == {"id": "w", "a": 2}


def test_chave_extra_no_fim():
    # Caso real do gemini-3.1-flash-lite: um '}' a mais depois do objeto.
    out = cp('{"id":"x","is_relevant":{"answer":"yes"}}}')
    assert out["id"] == "x"
    assert out["is_relevant"]["answer"] == "yes"
    assert "raw_content" not in out


def test_texto_extra_apos_objeto():
    out = cp('{"id":"y","a":1} qualquer lixo aqui')
    assert out == {"id": "y", "a": 1}


def test_virgula_final():
    assert cp('{"id":"z","a":1,}') == {"id": "z", "a": 1}


def test_bloco_markdown():
    assert cp('```json\n{"id":"m","a":3}\n```') == {"id": "m", "a": 3}


def test_unwrap_single_id():
    # {"<id>": {...}} sem chave "id" -> promove a chave a campo "id".
    out = cp('{"10.1/abc":{"is_relevant":{"answer":"no"}}}')
    assert out["id"] == "10.1/abc"
    assert out["is_relevant"]["answer"] == "no"


def test_irrecuperavel_retorna_raw_content():
    out = cp("isto não é json de jeito nenhum")
    assert "raw_content" in out


# --- Reparo robusto via json_repair (último recurso) -------------------------
# Casos reais de malformação do gemini/deepseek que raw_decode não cobre porque
# o erro está no MEIO do JSON, não no fim.

def test_chave_sem_aspa_de_abertura():
    # Padrão real do gemini: },sq2": em vez de },"sq2":
    pytest.importorskip("json_repair")
    out = cp('{"id":"x","supporting_questions":{"sq1":{"answer":"a"},sq2":{"answer":"b"}}}')
    assert out["id"] == "x"
    assert out["supporting_questions"]["sq2"]["answer"] == "b"
    assert "raw_content" not in out


def test_virgula_faltando_entre_campos():
    # Padrão real do deepseek: falta a vírgula entre dois campos.
    pytest.importorskip("json_repair")
    out = cp('{"id":"y","a":1 "b":2}')
    assert out["id"] == "y"
    assert out["b"] == 2
    assert "raw_content" not in out
