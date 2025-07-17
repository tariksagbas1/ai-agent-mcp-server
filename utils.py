import re
# from pandasai import Agent
# from pandasai.llm import OpenAI as Pandasai_OpenAI
# import re
# from system_prompts import *

# NOTE: Update "E:\furkan.canturk\AI_projects\pandas-ai\pandasai\schemas\df_config.py", line 37, in Config @validator("llm", always=True)
# C:\ICRON\Analytics\Analytics.2.4791\envs\icronai_demo\Lib\site-packages\pandasai\prompts\templates

def split_by_capitals(s):
    # Use regular expression to split the string based on capital letters
    words = re.findall(r'[A-Z][a-z]+|ID|[A-Z](?=[A-Z][a-z])', s)
    return ' '.join(words)

def rename_columns(df):
    # Rename each column in the DataFrame by splitting on capital letters
    new_columns = {col: split_by_capitals(col) for col in df.columns}
    df.rename(columns=new_columns, inplace=True)


# def get_pandasai_agent(api_key, data_list = [], llm = None, skills: list = None) -> Agent:
#     """
#     The function creates an agent on the dataframes exctracted from the uploaded files
#     Args: 
#         data: A Dictionary with the dataframes extracted from the uploaded data
#         llm:  llm object based on the ll type selected
#     Output: PandasAI Agent
#     """
#     #llm = LocalLLM(api_base="http://127.0.0.1:11434/v1", model='llama3.1')
    
#     if llm is None:
#         llm = Pandasai_OpenAI(api_key)

#     agent = Agent(data_list, 
#                   #description=prompt2,
#                   memory_size = 1,
#                   config={"llm": llm, 
#                            'verbose':True, 
#                            'max_retries':0, 
#                            'allow_reuse': True, 
#                            'enforce_privacy':True, 
#                            #"response_parser": StreamlitResponse, 
#                            'enable_cache':False, 
#                            'custom_whitelisted_dependencies': ['pandasai', 'functools']}
#                            )
#     for skill in skills:
#         agent.add_skills(skill)

#     return agent

def convert_to_builtin_type(type_str):
    # Define regex patterns for each built-in type

    if type_str == 'text':
        type_str = 'string'

    elif type_str == 'datetime':
        type_str = 'string'

    elif type_str == 'real':
        type_str = 'float'

    type_patterns = {
        int: re.compile(r'^(int(eger)?(64)?)$', re.IGNORECASE),
        float: re.compile(r'^(float|decimal)$', re.IGNORECASE),
        str: re.compile(r'^(str(ing)?)$', re.IGNORECASE)
    }
    
    # Match type_str against each pattern
    for builtin_type, pattern in type_patterns.items():
        if pattern.match(type_str):
            return builtin_type
    
    # Return None if no match is found
    return None


from typing import Any, Dict, Type
from pydantic import create_model, BaseModel, Field

def remove_spaces(s: str) -> str:
    """Remove spaces from string."""
    return s.replace(' ', '')


def split_by_capitals(s):
    # Use regular expression to split the string based on capital letters
    words = re.findall(r'[A-Z][a-z]+|ID|[A-Z](?=[A-Z][a-z])', s)
    return ' '.join(words)
