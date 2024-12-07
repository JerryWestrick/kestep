import platform
import subprocess

from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from rich.console import Console
from rich.panel import Panel
from rich.style import Style
from rich.text import Text
from prompt_toolkit.key_binding import KeyBindings

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


def readfile(filename: str) -> dict[str, str]:
    """ Read a file from local disk and add it the prompt"""
    try:
        with open(filename, 'r') as file:
            file_contents = file.read()
        
    except Exception as err:
        console.print(f"Error while reading file {filename} ... ", err)
        return {'role': 'function','name': 'read_file', 'content': f'ERROR file not found: {filename}'}

    return {'name': 'read_file', 'content': file_contents}

def askuser(question: str) -> dict[str, str]:
    """The LLM asks the local user for clarification with improved formatting and advanced line editing."""


    # Create a styled question
    styled_question = Text(question, style="bold cyan")

    # Create a panel for the question
    question_panel = Panel(
        styled_question,
        title=f"[bold green]ask user[/bold green]",
        subtitle="[italic]Enter your response (Ctrl-D to finish)[/italic]",
        border_style="green",
        expand=False
    )

    # Display the question panel
    console.print(question_panel)

    # Set up key bindings
    kb = KeyBindings()

    @kb.add('c-d')
    def _(event):
        event.app.exit(result=event.app.current_buffer.text)

    # Set up prompt_toolkit session with styling
    style = Style.from_dict({
        'prompt': 'ansiyellow bold',
        'input': 'ansiwhite',
    })
    session = PromptSession(
        history=InMemoryHistory(),
        style=style,
        multiline=True,
        prompt_continuation=lambda width, line_number, is_soft_wrap: '▶ ' if not is_soft_wrap else '  ',
        key_bindings=kb
    )

    # Collect user input asynchronously
    try:
        user_response = session.prompt("Your response: ", )
    except EOFError:
        user_response = session.app.current_buffer.text

    # Display the user's response in a panel
    response_panel = Panel(
        Text(user_response, style="yellow"),
        title="[bold blue]Your Response[/bold blue]",
        border_style="blue",
        expand=False
    )
    console.print(response_panel)

    msg = {
        'name': 'exec',
        'role': 'User',
        'content': f'User Answer: {user_response}'
    }
    return msg


def wwwget(url: str):

    try:
        page_contents = get_webpage_content(url)
    except Exception as err:
        console.print(f"Error while retrieving url for AI... ", err)
        result = {'role': "function",
                'name': 'wwwget',
                'content': f'ERROR url not returned: {url}'
                }
        return result

    return {'name': 'wwwget', 'content': page_contents}


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
        "name": "exec",
        "description": f"Execute a command on the local {os_descriptor} system",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "command to be executed",
                },
            },
            "required": ["command"],
        },
    },
    {
        "name": "querydb",
        "description": f"Execute an SQL against psql (PostgreSQL) 14.11 (Ubuntu 14.11-0ubuntu0.22.04.1) database",
        "parameters": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "SQL command to be executed",
                },
            },
            "required": ["sql"],
        },
    },
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
    # "writefile": writefile,
    # "exec": execute_cmd_ai,
    # "querydb": query_db_ai,
    "askuser": askuser,
}

