import json
import re
from typing import Any, Dict


def clean_and_parse_json(file_content: str) -> Dict[str, Any]:
    """
    Cleans and parses JSON content from raw responses.
    
    Args:
        file_content: Response file content
        
    Returns:
        Dictionary containing the parsed JSON data
    """
    # Check if content is within code blocks
    json_block_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
    matches = re.findall(json_block_pattern, file_content)
    
    if matches:
        # Get the first JSON block
        content = matches[0]
    else:
        # No code blocks, use raw content
        content = file_content
    
    # Additional cleaning
    content = content.replace("```json", "").replace("```", "").strip()
    content = content.strip("[").strip("]")
    
    # Try to parse as JSON
    try:
        dict_json = json.loads(content)
        if len(dict_json) == 1 and "id" not in dict_json:
            new_dict = {}
            for key, value in dict_json.items():
                new_dict["id"] = key
                if isinstance(value, dict):
                    new_dict = new_dict | value
                else:
                    # payload canônico {"articles": [...]}: mesclar apagaria o valor
                    return dict_json
            return new_dict
        return dict_json

    except json.JSONDecodeError:
        try:
            # Handle possible trailing commas
            content = re.sub(r',\s*}', '}', content)
            content = re.sub(r',\s*]', ']', content)
            return json.loads(content)
        except json.JSONDecodeError:
            # Return raw content as fallback
            return {"raw_content": content}
