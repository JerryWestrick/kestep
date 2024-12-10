import platform
import subprocess
import sys

from rich.console import Console
from rich.prompt import Prompt
from rich.theme import Theme

from kestep.kestep_util import versioned_file

console = Console()

def get_webpage_content(url: str) -> str:
    # Command to fetch the content and convert it to text
    command = f"wget2 --content-on-error -O - {url} | html2text"

    # Create a subprocess
    process = subprocess.run(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    if process.returncode != 0:
        # If there was an error, raise an exception with the error message
        raise Exception(f"Error fetching URL: {process.stderr.decode()}")

    # Return the output as a string
    return process.stdout.decode()


def readfile(filename: str) -> str:
    """ Read a file from local disk and add it the prompt"""
    try:
        with open(filename, 'r') as file:
            file_contents = file.read()
    except Exception as err:
        console.print(f"Error accessing file: {str(err)}\n\n")
        console.print_exception()
        sys.exit(9)

    return file_contents

# Create custom theme for prompts
theme = Theme({"prompt": "bold blue", "answer": "italic cyan"})

question_console = Console(theme=theme)

def askuser(question: str) -> str:
    """The LLM asks the local user for clarification with improved formatting and advanced line editing."""

    answer = Prompt.ask(
        f"[prompt]{question}[/prompt]",
        console=question_console
    )
    return answer


def wwwget(url: str) -> str:

    try:
        page_contents = get_webpage_content(url)
    except Exception as err:
        console.print(f"Error while retrieving url for AI... ", err)
        result = {'role': "function",
                'name': 'wwwget',
                'content': f'ERROR url not returned: {url}'
                }
        return result

    return page_contents

def writefile(filename: str, content: str) -> str:
    """Write content to file with versioning.
    Returns the path of the written file."""
    new_filename = versioned_file(filename)

    with open(new_filename, 'w', encoding='utf-8') as f:
        f.write(content)

    return f"Content written to file '{new_filename}'"


def execcmd(cmd: str) -> str:
    """Execute shell command and return output."""
    import subprocess
    if cmd[0] in ['"', "'"]:
        cmd = cmd[1:-1]
    try:
        result = subprocess.run(['/bin/sh', '-c', cmd], capture_output=True, text=True, encoding='utf-8', check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"stderr: {e.stderr}"
    except Exception as e:
        return f"Error: {str(e)}"


os_descriptor = platform.platform()

DefinedFunctionsArray = [
    {   "name": "readfile",
        "description": "Read the contents of a named file",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "The name of the file to read",
                },
            },
            "required": ["filename"],
        },
    },
    {   "name": "wwwget",
        "description": "Read a webpage url and return the contents",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The url of the web page to read",
                },
            },
            "required": ["url"],
        },
    },
    {
        "name": "writefile",
        "description": "Write the contents to a named file on the local file system",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "The name of the file to write",
                },
                "content": {
                    "type": "string",
                    "description": "The contents of the file",
                },
            },
            "required": ["filename", "content"],
        },
    },
    {
        "name": "execcmd",
        "description": f"Execute a command on the local {os_descriptor} system",
        "parameters": {
            "type": "object",
            "properties": {
                "cmd": {
                    "type": "string",
                    "description": "command to be executed",
                },
            },
            "required": ["cmd"],
        },
    },
    # {
    #     "name": "querydb",
    #     "description": f"Execute an SQL against psql (PostgreSQL) 14.11 (Ubuntu 14.11-0ubuntu0.22.04.1) database",
    #     "parameters": {
    #         "type": "object",
    #         "properties": {
    #             "sql": {
    #                 "type": "string",
    #                 "description": "SQL command to be executed",
    #             },
    #         },
    #         "required": ["sql"],
    #     },
    # },
    {
        "name": "askuser",
        "description": f"Get Clarification by Asking the user a question",
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "Question to ask the user",
                },
            },
            "required": ["question"],
        },
    }
]

DefinedFunctionsDescriptors = {func["name"]: func for func in DefinedFunctionsArray}

DefinedFunctions = {
    "readfile": readfile,
    "wwwget": wwwget,
    "writefile": writefile,
    "execcmd": execcmd,
    # "querydb": query_db_ai,
    "askuser": askuser,
}

