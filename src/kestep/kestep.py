import glob
import json
import os
import sys
import threading
import time

import keyring
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from kestep.cfunctions import DefinedFunctions
from kestep.kestep_api_config import api_config

models_config: dict[str,any]
json_path = os.path.join(os.path.dirname(__file__), 'kestep_models.json')
with open(json_path, "r") as json_file:
    models_config = json.load(json_file)

console = Console()
stop_event = threading.Event()  # Event to signal when to stop the thread



def print_step_msgs(step_files: list[str]) -> None:
    table = Table(title="Execution Messages")
    table.add_column("Step", style="cyan bold", no_wrap=True)
    table.add_column("Lno", style="blue bold", no_wrap=True)
    table.add_column("Cmd", style="green bold", no_wrap=True)
    table.add_column("Message", style="green bold")

    for step_file in step_files:
        # console.print(f"{step_file}")
        try:
            step: KepfStep = KepfStep(step_file)
            step.parse_kepf()
        except Exception as e:
            console.print(f"[bold red]Error parsing file {step_file} : {str(e)}[/bold red]")
            console.print_exception()
            sys.exit(1)
        title = os.path.basename(step_file)
        if step.statements:
            for stmt in step.statements:
                table.add_row(title, f"{stmt.msg_no:03}", stmt.keyword, stmt.value)
                title = ''
            table.add_row('───────────────', '───', '─────────', '──────────────────────────────')
    console.print(table)

def print_step_names(step_files: list[str]) -> None:
    table = Table(title="Step Files")

    table.add_column("Step", style="cyan", no_wrap=True)
    table.add_column("Description", style="magenta")

    for step_file in step_files:
        try:
            with open(step_file, 'r') as file:
                first_line = file.readline().strip()[2:]  # Read first line
        except Exception as e:
            first_line = f"Error reading file: {str(e)}"

        table.add_row(os.path.basename(step_file), first_line)

    console.print(table)


def print_dot():
    while not stop_event.is_set():
        console.print('.', end='')
        time.sleep(0.5)

def get_llm(model: str) -> dict[str,any] | None:
    if model in models_config:
        if models_config[model]['company'] in api_config:
            return api_config[models_config[model]['company']]
    return None


def create_dropdown(options, prompt_text="Select an option"):
    console = Console()

    # Display numbered options
    for i, option in enumerate(options, 1):
        console.print(f"{i}. {option}", style="cyan")

    # Get user input with validation
    while True:
        choice = Prompt.ask(
            prompt_text,
            choices=[str(i) for i in range(1, len(options) + 1)],
            show_choices=False
        )

        return options[int(choice) - 1]


def get_new_api_key()-> None:
    companies = list(api_config.keys())
    companies.sort()
    company = create_dropdown(companies, "AI Company?")
    api_key = console.input(f"[bold green]Please enter your [/][bold cyan]{company} API key: [/]")
    keyring.set_password("kestep", username=company, password=api_key)


def print_models():
    table = Table(title="Available Models")
    table.add_column("Company", style="cyan", no_wrap=True)
    table.add_column("Model", style="green")
    table.add_column("Max Token", style="magenta", justify="right")
    table.add_column("$/mT In", style="green", justify="right")
    table.add_column("$/mT Out", style="green", justify="right")

    # Sort by LLM name, then model.
    sortable_keys = [f"{models_config[model]['company']}:{model}" for model in models_config.keys()]
    sortable_keys.sort()

    last_company = ''
    for k in sortable_keys:
        company, model_name = k.split(':', maxsplit=1)
        model = models_config.get(model_name)
        if company != last_company:
            table.add_row(company,
                          model_name,
                          str(model['context']),
                          f"{model['input']*1_000_000:06.4f}",
                          f"{model['output']*1_000_000:06.4f}"
                          )
            last_company = company
        else:
            table.add_row("", model_name, str(model['context']), f"{model['input']*1_000_000:06.4f}",
                      f"{model['output']*1_000_000:06.4f}")

    console.print(table)


# def send_request(llm, question: str):
#     llm['user_input'] = question
#     header_template = Template(llm['tplHeader'])
#     hdr_str = header_template.render(llm)
#     hdr = json.loads(hdr_str)
#
#     data_template = Template(llm['tplData'])
#     data = data_template.render(llm)
#
#     if llm['debug']:
#         console.print(f"[bold blue]Data to be sent to {llm['company']} API:[/bold blue]")
#         console.print(data)
#
#     console.print(f"[bold blue]asking {llm['company']}::{llm['model']}", end='')
#     # Create a thread to run the print_dot function
#     dot_thread = threading.Thread(target=print_dot)
#     start_time = time.time()
#     elapsed_time = 0
#     model = models_config[llm['model']]
#     try:
#         dot_thread.start()  # Start the thread
#         response = requests.post(llm['url'], headers=hdr, data=data)
#     finally:
#         elapsed_time = time.time() - start_time
#         stop_event.set()  # Signal the thread to stop
#         dot_thread.join()  # Wait for the thread to finish
#         # console.print(f" {elapsed_time:.2f} secs Tokens In={response.usage.prompt_tokens}, Out={response.usage.completion_tokens},")
#
#     if response.status_code != 200:
#         console.print(f"[bold red]Error calling {llm['company']}::{llm['model']} API: {response.status_code} {response.reason}[/bold red]")
#         console.print(f"url: {llm['url']}")
#         console.print("header: ", hdr)
#         console.print("data: ", data)
#
#         if llm['response_text_is_json']:
#             err = json.loads(response.text)
#             console.print(f"[bold red]{err}[/bold red]")
#         else:
#             console.print(f"[bold blue]Response from {llm['company']} API:[/bold blue]")
#             console.print(response.text)
#
#         exit(1)
#
#     try:
#         response_obj = json.loads(response.text)
#     except KeyError as err:
#         console.print(f"[bold red]Json Error from {llm['company']} API:[/bold red]")
#         console.print(response.text)
#         exit(1)
#
#     usage = response_obj['usage']
#     toks_in = usage[llm['usage_keys'][0]]
#     cost_in = toks_in * model['input']
#     toks_out = usage[llm['usage_keys'][1]]
#     cost_out = toks_out * model['output']
#     total = cost_in + cost_out
#     console.print(f" {elapsed_time:.2f} secs Tokens In={toks_in}(${cost_in:06.4f}), Out={toks_out}(${cost_out:06.4f}) Total=${total:06.4f}")
#
#     if llm['debug']:
#         console.print(f"[bold blue]Response from {llm['company']} API:[/bold blue]")
#         console.print(response_obj)
#
#     return_obj = response_obj
#     for idx in llm['response_keys']:
#         return_obj = return_obj[idx]
#
#     return return_obj


top_left = '╭'
top_right = '╮'
bottom_left = '╰'
bottom_right = '╯'
vertical_mid = '│'
horizontal_mid = '─'

keywords = {
    '.#': {'multi': False, },
    '.llm': {'multi': False, },
    '.clear': {'multi': False,},
    '.include': {'multi': False,},
    '.cmd': {'multi': False,},
    '.exec': {'multi': False,},
    '.system': {'multi': True,},
    '.user': {'multi': True,},
    '.assistant': {'multi': True,},
}
keys = keywords.keys()



class KepfSyntaxError(Exception):
    pass

class KepfStep:
    """Class to hold Step execution state"""

    def __init__(self, filename: str, debug: bool = False):
            self.filename = filename
            self.debug = debug
            self.ip: int = 0
            self.llm: dict[str, any] = {}
            self.vdict: dict[str, str] = {}
            self.statements: list[_KepfStatement] = []


    def parse_kepf(self) -> bool :
        lines: list[str]

        # read .kepf file
        with open(self.filename, 'r') as file:
            lines = file.readlines()

        # Delete trailing blank lines
        while lines[-1][0] == '':
            lines.pop()

        # Add implied .exec at end of lines
        if lines[-1][0:5] != '.exec':
            lines.append('.exec')

        # Storage for multiline cmds: .system .user .assistant
        last_keyword = None
        last_value = '\n'

        for lno, line in enumerate(lines):
            try:
                line = line.strip()

                # skip blank lines
                if not line:
                    continue

                # Process all lines that do not start with .
                if line[0] != '.':
                    last_value += f"{line}\n"
                    continue

                if ' ' in line:
                    keyword, rest = line.split(' ', 1)
                else:
                    keyword = line
                    rest = ''

                # Process all lines that do not start with a dot keyword
                if keyword not in keys:
                    last_value += f"{line}\n"
                    continue

                # We got us a valid dot keyword!!!
                # Do we have a .system, .user, or .assistant?
                if last_keyword is not None:
                    # Okay Lets add it to msg list
                    self.statements.append(make_statement(self, len(self.statements), last_keyword, last_value[1:-1]))
                    last_keyword = None
                    last_value = '\n'

                # Is it the beginning of a multiline dot keyword?
                if keywords[keyword]['multi']:
                    last_keyword = keyword
                    last_value = '\n'
                    continue

                # and now for the single line dot keywords
                self.statements.append(make_statement(self, len(self.statements), keyword, rest))

            except Exception as e:
                raise KepfSyntaxError(f"{vertical_mid} [red]Error parsing file {self.filename}:{lno} error: {str(e)}.[/]\n\n")

        return True


    def execute(self) -> None:

        console.print(
            f"[bold white]{top_left}{horizontal_mid * 2}[/][bold white]{os.path.basename(self.filename)}[/][bold white]{horizontal_mid * (78 - len(os.path.basename(self.filename)))}[/]")

        for stmt_no, stmt in enumerate(self.statements):
            try:
                stmt.execute(self.debug)
            except Exception as e:
                console.print(f"{vertical_mid} [bold red]Error executing statement {stmt_no} {stmt}: {str(e)}[/bold red]\n\n")
                console.print_exception()
                raise KepfSyntaxError(f"Error executing statement {stmt_no} {stmt}: {str(e)}")
        console.print(f"{bottom_left}{horizontal_mid * 80}")


class _KepfStatement:

    def __init__(self, step:KepfStep, msg_no:int, keyword:str, value:str):
        self.msg_no = msg_no
        self.keyword = keyword
        self.value = value
        self.step = step


    def console_str(self):
        return (f"[bold white]{vertical_mid}[/][white]{self.msg_no:02}[/] "
                f"[cyan]{self.keyword:<8}[/] [green]{self.value}[/]")

    def __str__(self):
        return (f"[bold white]{vertical_mid}[/][white]{self.msg_no:02}[/] "
                f"[cyan]{self.keyword:<8}[/] [green]{self.value}[/]")

    def execute(self, debug: bool):
        if debug:
            console.print(self.console_str())

class _Comment(_KepfStatement):
    pass

class _Clear(_KepfStatement):

    def execute(self, debug: bool):
        if debug:
            console.print(f"[bold white]{vertical_mid}[/][white]{self.msg_no:02}[/] [cyan]{self.keyword:<8}[/] [green]{self.value}[/]")

        try:
            parms = json.loads(self.value)
        except Exception as e:
            console.print(f"{vertical_mid} [white on red]Error parsing .clear parameters: {str(e)}[/]\n\n")
            console.print_exception()
            raise KepfSyntaxError(f"Error parsing .clear parameters: {str(e)}")

        if not isinstance(parms, list):
            raise KepfSyntaxError(f".clear parameters must be a list, but got {type(parms).__name__}: {self.value}")

        for k in parms:
            try:
                log_files = glob.glob(k)  # Use glob to find all files matching the pattern

                for file_path in log_files:
                    if os.path.isfile(file_path):  # Ensure that it's a file
                        if debug:
                            console.print(f"{vertical_mid} [bold green] Deleting {k}[/bold green]")
                        try:
                            os.remove(file_path)
                            console.print(f"File {file_path} deleted successfully.")
                        except OSError as e:
                            console.print(f"Error deleting file {file_path}: {str(e)}")

                    if debug:
                        console.print(f"{vertical_mid} [bold green]File {k} deleted successfully.[/bold green]")
            except OSError as e:
                console.print(f"{vertical_mid} [white or red]Error deleting file {k}: {str(e)}[/]\n\n")

class _Include(_KepfStatement):
    pass

class _Cmd(_KepfStatement):

    def execute(self, debug:bool) -> dict[str, str]:
        """Execute a command that was defined in a prompt file (.kepf)"""

        if debug:
            console.print(self.console_str())

        function_name, args = self.value.split('(', maxsplit=1)
        args = args[:-1]
        args_list = args.split(",")
        function_args = {}
        for arg in args_list:
            name, value = arg.split("=", maxsplit=1)
            function_args[name] = value

        if function_name not in DefinedFunctions:
            console.print(f"[bold red]Error executing {function_name}({function_args}): {function_name} is not defined.[/bold red]")
            raise Exception(f"{function_name} is not defined.")

        try:
            new_msg = DefinedFunctions[function_name](**function_args)
        except Exception as err:
            console.print(f"Error executing {function_name}({function_args})): {str(err)}")
            raise err

        if debug:
            # console.print(f"[bold white]{vertical_mid}[/][white]{self.msg_no:02}[/] [cyan]{self.keyword:<8}[/] "
            #               f"[green]{self.value}[/]")
            # vls = new_msg['content'].split('\n')
            # for vl in vls:
            #     console.print(f"[bold white]{vertical_mid}[/]            [green]{vl}[/]")
            vl,_ = new_msg['content'].split('\n',maxsplit=1)
            console.print(f"[bold white]{vertical_mid}[/]            [green]{vl}[/]")

        self.step.statements.append(new_msg)
        return {'role': 'function', 'content': f"```result of {function_name}({function_args})\n{new_msg['content']}\n```"}

class _Exec(_KepfStatement):
    pass

class _System(_KepfStatement):

    def execute(self, debug: bool):
        if debug:
            vls = self.value.split('\n')
            vl = vls.pop(0)
            console.print(f"[bold white]{vertical_mid}[/][white]{self.msg_no:02}[/] [cyan]{self.keyword:<8}[/] [green]{vl}[/]")
            for vl in vls:
                console.print(f"[bold white]{vertical_mid}[/]            [green]{vl}[/]")

class _User(_KepfStatement):

    def execute(self, debug: bool):
        if debug:
            vls = self.value.split('\n')
            vl = vls.pop(0)
            console.print(f"[bold white]{vertical_mid}[/][white]{self.msg_no:02}[/] [cyan]{self.keyword:<8}[/] [green]{vl}[/]")
            for vl in vls:
                console.print(f"[bold white]{vertical_mid}[/]            [green]{vl}[/]")

class _Assistant(_KepfStatement):

    def execute(self, debug: bool):
        if debug:
            vls = self.value.split('\n')
            vl = vls.pop(0)
            console.print(f"[bold white]{vertical_mid}[/][white]{self.msg_no:02}[/] [cyan]{self.keyword:<8}[/] [green]{vl}[/]")
            for vl in vls:
                console.print(f"[bold white]{vertical_mid}[/]            [green]{vl}[/]")

class _Llm(_KepfStatement):
    pass

# Create a _KepfStatement subclass depending on keyword
StatementTypes: dict[str, type(_KepfStatement)] = {
    '.#': _Comment,
    '.clear': _Clear,
    '.include': _Include,
    '.cmd': _Cmd,
    '.exec': _Exec,
    '.system': _System,
    '.user': _User,
    '.assistant': _Assistant,
    '.llm': _Llm,
}

def make_statement(step:KepfStep, msg_no: int, keyword: str, value: str) -> _KepfStatement:
    my_class = StatementTypes[keyword]
    return my_class(step, msg_no, keyword, value)
