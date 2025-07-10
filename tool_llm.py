import os
from openai import OpenAI
from dotenv import load_dotenv


load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Define your tools as dicts with name and description
tools = [
    {
        "name": "get_employees",
        "description": (
            """
            Get employees filtered by name, department, gender, office, rank, or office days.
            Can return the count, or any desired information about the employees.
            """
        )
    },
    {
        "name": "send_mail",
        "description": (
            "Sends a mail to a specified email address."
        )
    }
    # Add more tools here as needed
]

user_prompt = "How many women work in the Product department?"

# Build a prompt for the LLM
tool_list_str = "\n".join([f"{i+1}. {tool['name']}: {tool['description']}" for i, tool in enumerate(tools)])
system_prompt = f"""You are a tool selector. Here are the available tools:\n{tool_list_str}\n"""
user_message = f"Given the user query: \"{user_prompt}\"\nWhich tools are the most appropriate? Reply with the tool names separated by commas."

client = OpenAI(api_key=OPENAI_API_KEY)
response = client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ],
    temperature=0
)

print("Prompt:")
print(system_prompt + "\n" + user_message)
print("\nLLM response:")
print(response.choices[0].message.content)
