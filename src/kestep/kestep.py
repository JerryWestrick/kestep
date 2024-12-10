import copy
import glob
import json
import logging
import os

import sys
import threading
import time

import keyring
import requests
from jinja2 import Template
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from kestep.DrawCharacters import TOP_LEFT, BOTTOM_LEFT, VERTICAL, HORIZONTAL
from kestep.kestep_util import versioned_file
from kestep.kestep_api_config import api_config
from kestep.kestep_functions import DefinedFunctions, readfile

FORMAT = "%(message)s"
logging.basicConfig(level="NOTSET", format=FORMAT, datefmt="[%X]", handlers=[RichHandler()])

log = logging.getLogger(__file__)



models_config: dict[str,any]
json_path = os.path.join(os.path.dirname(__file__), 'kestep_models.json')
with open(json_path, "r") as json_file:
    models_config = json.load(json_file)

console = Console()
terminal_width = console.size.width
stop_event = threading.Event()  # Event to signal when to stop the thread

keywords = ['.#', '.assistant', '.cmd', '.clear', '.include', '.debug', '.exec', '.llm', '.system', '.user',]

def print_step_code(step_files: list[str]) -> None:
    table = Table(title="Execution Messages")
    table.add_column("Step", style="cyan bold", no_wrap=True)
    table.add_column("Lno", style="blue bold", no_wrap=True)
    table.add_column("Cmd", style="green bold", no_wrap=True)
    table.add_column("Params", style="dark_green bold")

    for step_file in step_files:
        # console.print(f"{step_file}")
        try:
            step: PromtpStep = PromtpStep(step_file)
            step.parse_prompt()
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



def print_dot():
    while not stop_event.is_set():
        console.print('.', end='')
        time.sleep(1)


def get_llm(model: str) -> dict[str,any] | None:
    if model in models_config:
        model_parms = models_config[model]
        if 'company' in model_parms:
            company_name = model_parms['company']
            if company_name in api_config:
                return copy.deepcopy(api_config[company_name])
            else:
                raise PromptSyntaxError(f"kestep_models.json error:  model {model} company {company_name} is not defined")
        else:
            raise PromptSyntaxError(f"kestep_models.json error:  model '{model}' must have 'company' key")
    else:
        models = list(models_config.keys())
        list_of_models = '\n'.join(models)
        raise PromptSyntaxError(f".llm error: unknown model {model}. Please use one of: \n{list_of_models}")





class PromptSyntaxError(Exception):
    pass



class PromtpStep:
    """Class to hold Step execution state"""

    def __init__(self, filename: str, debug: bool = False):
            self.filename = filename
            self.debug = debug
            self.ip: int = 0
            self.llm: dict[str, any] = {}
            self.vdict: dict[str, str] = {}
            self.statements: list[_PromptStatement] = []
            self.messages: list[dict[str,str]] = []
            self.header: str = ''
            self.data: str = ''
            self.url: str = ''
            self.conversation: list[dict[str,str]] = []
            self.console = Console()  # Console for terminal
            self.file_console = None  # Console for file, initialized in execute
            if debug:
                log.info(f'Instantiated PromptStep(filename="{filename}",debug="{debug}")')

    def print(self, *args, **kwargs):
        """Print method to output to both console and file."""
        self.console.print(*args, **kwargs)  # Print to terminal
        if self.file_console:  # Ensure file is open
            self.file_console.print(*args, **kwargs)  # Print to file

    def debug_print_2(self):
        from rich.pretty import Pretty
        from rich.panel import Panel

        pretty = Pretty(self, expand_all=True)
        panel = Panel(pretty)
        console.print(panel)

    def debug_print(self, elements: list[str]) -> None:
        """Pretty prints the PromptStep class state for debugging"""
        # table = Table(title=f"PromptStep Debug Info for {self.filename}::{value}")
        table = Table()

        # Basic info section
        table.add_column("Step Property", style="cyan", no_wrap=True)
        table.add_column("Value", style="green")


        table.add_row("Filename", self.filename)
        table.add_row("Debug Mode", str(self.debug))
        table.add_row("Instruction Pointer", str(self.ip))

        if 'all' in elements:
            elements = ['llm', 'variables', 'statements', 'messages', 'header', 'data', 'url', 'conversation']

        # print varname: value
        if 'llm' in elements:
            if self.llm:
                table.add_row("LLM Config", "")
                for key, value in self.llm.items():
                    if key == 'API_KEY':
                        value ='... top secret ...'
                    table.add_row(f"  {key}", str(value))
            else:
                table.add_row("LLM Config", "Not Set")

        # Variables dictionary
        if 'variables' in elements:
            if self.vdict:
                table.add_row("Variables", "")
                for key, value in self.vdict.items():
                    table.add_row(f"  {key}", str(value))
            else:
                table.add_row("Variables", "Empty")

        # Statements
        if 'statements' in elements:
            if self.statements:
                table.add_row("Statements", f"Count: {len(self.statements)}")
                for idx, stmt in enumerate(self.statements):
                    table.add_row(f"  Statement {idx}", f"{stmt.keyword}: {stmt.value}")
            else:
                table.add_row("Statements", "Empty")

        # Messages
        if 'messages' in elements:
            if self.messages:
                table.add_row("Messages", f"Count: {len(self.messages)}")
                for idx, msg in enumerate(self.messages):
                    table.add_row(f"  Message {idx}", f"{msg['role']}: {msg['content']}")
            else:
                table.add_row("Statements", "Empty")

        # conversation
        if 'conversation' in elements:
            if self.conversation:
                table.add_row("conversation", f"Count: {len(self.conversation)}")
                for idx, msg in enumerate(self.messages):
                    table.add_row(f"  Message {idx}", f"{msg['type']}: {msg['content']}")
            else:
                table.add_row("conversation", "Empty")

        table.add_row("url", str(self.url))
        table.add_row("header", str(self.header))
        table.add_row("data", str(self.data))

        console.print(table)


    def parse_prompt(self) -> bool :
        if self.debug: log.info(f'parse_prompt()')
        lines: list[str]

        # read .prompt file
        with open(self.filename, 'r') as file:
            lines = file.readlines()


        # Delete trailing blank lines
        while lines[-1][0].strip() == '':
            lines.pop()

        # If Missing.. Add implied .exec at end of lines
        if lines[-1][0:5] != '.exec':
            lines.append('.exec')

        # Storage for multiline cmds: .system .user .assistant
        last_keyword = None
        last_value = ''

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
                if keyword not in keywords:
                    last_value += f"{line}\n"
                    continue

                # We got us a valid dot keyword!!!
                # That completes the "last" statement
                if last_value:
                    # Okay Lets add it to msg list
                    self.statements.append(make_statement(self, len(self.statements), last_keyword, last_value[:-1]))
                    last_value = ''

                # Does this represent the end of a Multi Line?
                if keyword in ['.assistant', '.user', '.system']:
                    last_keyword = keyword
                    last_value = ''
                    continue    # .user, .system, .assistant do not have info on line...

                # and now for the single line dot keywords
                self.statements.append(make_statement(self, len(self.statements), keyword, rest))

            except Exception as e:
                raise PromptSyntaxError(f"{VERTICAL} [red]Error parsing file {self.filename}:{lno} error: {str(e)}.[/]\n\n")

        # console.print(f'Generated statements:')
        # for sno, stmt in enumerate(self.statements):
        #     console.print(f"{sno}: {stmt}")

        return True

    def print_exception(self) -> None:
        """Print exception information to both console and file outputs."""
        self.console.print_exception()  # Print to terminal
        if self.file_console:  # Ensure file is open
            self.file_console.print_exception()  # Print to file


    def execute(self) -> None:
        if self.debug: log.info(f'execute({self.filename} with {len(self.statements)} statements)')

        base_name = os.path.splitext(os.path.basename(self.filename))[0]
        logfile_name = versioned_file(f"logs/{base_name}.log", backup_dir='logs', extension='.log')
        with open(logfile_name, 'w') as file:
            self.file_console = Console(file=file)  # Open file for writing

            self.print(
                f"[bold white]{TOP_LEFT}{HORIZONTAL * 2}[/][bold white]{os.path.basename(self.filename)}[/][bold white]{HORIZONTAL * (78 - len(os.path.basename(self.filename)))}[/]"
            )

            for stmt_no, stmt in enumerate(self.statements):
                try:
                    stmt.execute(self)
                except Exception as e:
                    self.print(f"{VERTICAL} [bold red]Error executing statement above : {str(e)}[/bold red]\n\n")
                    self.print_exception()
                    sys.exit(9)
            self.print(f"{BOTTOM_LEFT}{HORIZONTAL * 80}")

            self.file_console.file.close()  # Close file console at end

class _PromptStatement:

    def __init__(self, step:PromtpStep, msg_no:int, keyword:str, value:str):
        self.msg_no = msg_no
        self.keyword = keyword
        self.value = value
        self.step = step


    def console_str(self) -> str:
        rol = terminal_width - 23
        header = f"[bold white]{VERTICAL}[/][white]{self.msg_no:02}[/] [cyan]{self.keyword:<8}[/] "
        value = self.value
        if len(value) == 0:
            value = " "
        lines = value.split("\n")

        rtn = ""
        for line in lines:
            while len(line) > 0:
                rtn = f"{rtn}\n{header}[green]{line[:rol]}[/]"
                header = f"[bold white]{VERTICAL}[/]            "
                line = line[rol:]

        return rtn[1:]

    def __str__(self):
        return self.console_str()

    def execute(self, step: PromtpStep) -> None:
        step.print(self.console_str())

class _Assistant(_PromptStatement):

    def execute(self, step: PromtpStep) -> None:
        if step.debug:
            vls = self.value.split('\n')
            vl = vls.pop(0)
            step.print(f"[bold white]{VERTICAL}[/][white]{self.msg_no:02}[/] [cyan]{self.keyword:<8}[/] [green]{vl}[/]")
            for vl in vls:
                step.print(f"[bold white]{VERTICAL}[/]            [green]{vl}[/]")
        step.print(self.console_str())
        step.messages.append({'role':'assistant', 'content': self.value})

class _Clear(_PromptStatement):

    def execute(self, step: PromtpStep) -> None:
        if step.debug:
            step.print(f"[bold white]{VERTICAL}[/][white]{self.msg_no:02}[/] [cyan]{self.keyword:<8}[/] [green]{self.value}[/]")

        try:
            parms = json.loads(self.value)
        except Exception as e:
            step.print(f"{VERTICAL} [white on red]Error parsing .clear parameters: {str(e)}[/]\n\n")
            step.print_exception()
            sys.exit(9)
            # raise PromptSyntaxError(f"Error parsing .clear parameters: {str(e)}")

        if not isinstance(parms, list):
            step.print(f"{VERTICAL} [white on red]Error parsing .clear parameters expected list, but got {type(parms).__name__}: {self.value}")
            sys.exit(9)

        for k in parms:
            try:
                log_files = glob.glob(k)  # Use glob to find all files matching the pattern

                for file_path in log_files:
                    if os.path.isfile(file_path):  # Ensure that it's a file
                        if step.debug:
                            step.print(f"{VERTICAL} [bold green] Deleting {k}[/bold green]")
                        try:
                            os.remove(file_path)
                            step.print(f"File {file_path} deleted successfully.")
                        except OSError as e:
                            step.print(f"Error deleting file {file_path}: {str(e)}")

                    if step.debug:
                        step.print(f"{VERTICAL} [bold green]File {k} deleted successfully.[/bold green]")
            except OSError as e:
                step.print(f"{VERTICAL} [white or red]Error deleting file {k}: {str(e)}[/]\n\n")

class _Cmd(_PromptStatement):

    def execute(self, step: PromtpStep) -> None:
        """Execute a command that was defined in a prompt file (.prompt)"""


        function_name, args = self.value.split('(', maxsplit=1)
        args = args[:-1]
        args_list = args.split(",")
        function_args = {}

        if function_name == 'askuser':
            step.print(self.console_str()+': ',end='')
        else:
            step.print(self.console_str())


        for arg in args_list:
            name, value = arg.split("=", maxsplit=1)
            function_args[name] = value

        if function_name not in DefinedFunctions:
            step.print(f"[bold red]Error executing {function_name}({function_args}): {function_name} is not defined.[/bold red]")
            raise Exception(f"{function_name} is not defined.")

        try:
            text = DefinedFunctions[function_name](**function_args)
        except Exception as err:
            step.print(f"Error executing {function_name}({function_args})): {str(err)}")
            raise err

        last_msg = step.messages[-1]
        last_text = last_msg['content']
        new_text = f"{last_text}\n```{self.value}\n{text}\n```"
        last_msg['content'] = new_text

class _Comment(_PromptStatement):
    pass

class _Debug(_PromptStatement):

    def execute(self, step: PromtpStep) -> None:

        step.print(self.console_str())

        if not self.value:
            self.value = '["all"]'

        if self.value[0] != '[':
            self.value = f"[{self.value}]"

        step.print(self.value)
        try:
            parms = json.loads(self.value)
        except Exception as e:
            step.print(f"{VERTICAL} [white on red]Error parsing .debug parameters: {str(e)}[/]\n\n")
            step.print_exception()
            sys.exit(9)

        if not isinstance(parms, list):
            step.print(f"{VERTICAL} [white on red]Error parsing .debug parameters expected list, but got {type(parms).__name__}: {self.value}")
            sys.exit(9)

        step.debug_print(elements=parms)

class _Exec(_PromptStatement):

    def execute(self, step: PromtpStep) -> None:
        """Execute a request to an LLM"""

        step.print(f"[bold white]{VERTICAL}[/][white]{self.msg_no:02}[/] [cyan]{self.keyword:<8}[/] ", end='')

        header_template = Template(step.llm['tplHeader'])
        hdr_str = header_template.render(step.llm)
        step.header = json.loads(hdr_str)
        step.url = step.llm['url']
        company = step.llm['company']
        model = models_config[step.llm['model']]

        msgs = []
        for msg in step.messages:
            if company in ['Anthropic'] and msg['role'] == 'system':
                system_value = msg['content']
            else:
                msgs.append({'role': msg['role'], 'content': msg['content']})

        if company in ['Anthropic']:
            step.data = {'model': step.llm['model'], 'messages': msgs, 'max_tokens': model['context'], 'system': system_value}
        else:
            step.data = {'model': step.llm['model'], 'messages': msgs, 'max_tokens': model['context']}

        step.print(f"[bold blue]requesting {step.llm['company']}::{step.llm['model']}", end='')

        # Create a thread to run the print_dot function
        dot_thread = threading.Thread(target=print_dot)
        start_time = time.time()
        elapsed_time = 0
        model = models_config[step.llm['model']]

        try:
            dot_thread.start()  # Start the thread
            response = requests.post(step.url, json=step.data, headers=step.header)
        except Exception as err:
            step.print(f"{VERTICAL} [white on red]Error during request: {str(err)}[/]\n\n")
            step.print_exception()
            sys.exit(9)

        finally:
            # if response: step.print(response)
            elapsed_time = time.time() - start_time
            stop_event.set()  # Signal the thread to stop
            dot_thread.join()  # Wait for the thread to finish
            # step.print(f" {elapsed_time:.2f} secs Tokens In={response.usage.prompt_tokens}, Out={response.usage.completion_tokens},")

        if response.status_code != 200:
            step.print(f"[bold red]Error calling {step.llm['company']}::{step.llm['model']} API: {response.status_code} {response.reason}[/bold red]")
            step.print(f"url: {step.url}")
            step.print("header: ", step.header)
            step.print("data: ", step.data)

            if step.llm['response_text_is_json']:
                err = json.loads(response.text)
                step.print(f"[bold red]{err}[/bold red]")
            else:
                step.print(f"[bold blue]Response from {step.llm['company']} API:[/bold blue]")
                step.print(response.text)

            exit(1)

        try:
            response_obj = json.loads(response.text)
        except KeyError as err:
            step.print(f"[bold red]Json Error from {step.llm['company']} API:[/bold red]")
            step.print(response.text)
            exit(1)

        usage = response_obj['usage']
        toks_in = usage[step.llm['usage_keys'][0]]
        cost_in = toks_in * model['input']
        toks_out = usage[step.llm['usage_keys'][1]]
        cost_out = toks_out * model['output']
        total = cost_in + cost_out
        header = f"\n[bold white]{VERTICAL}[/]            "
        step.print(f" {elapsed_time:.2f} secs output tokens {toks_out} at {toks_out/elapsed_time:.2f} tps",end="")

        if step.debug:
            step.print(f"[bold blue]Response from {step.llm['company']} API:[/bold blue]")
            step.print(response_obj)

        return_obj = response_obj
        for idx in step.llm['response_keys']:
            return_obj = return_obj[idx]

        txt = f"{return_obj}"
        lines = txt.split("\n")
        rol = terminal_width - 23
        for line in lines:
            while len(line) > 0:
                step.print(f"\n[bold white]{VERTICAL}[/]            [green]{line[:rol]}[/]", end="")
                line = line[rol:]
        # step.print()
        step.print(f"{header}Tokens In={toks_in}(${cost_in:06.4f}), Out={toks_out}(${cost_out:06.4f}) Total=${total:06.4f}")


class _Include(_PromptStatement):

    def execute(self, step: PromtpStep) -> None:
        step.print(self.console_str())
        lines = readfile(filename=self.value)
        last_msg = step.messages[-1]
        last_text = last_msg['content']
        new_text = f"{last_text}\n{lines}\n"
        last_msg['content'] = new_text

class _Llm(_PromptStatement):

    def execute(self, step: PromtpStep) -> None:
        step.print(self.console_str())
        try:
            if step.llm:
                raise (PromptSyntaxError(f".llm syntax: only one .lls statement allowed in step {step.filename
                }"))

            if self.value[0] != '{':
                self.value = "{" + self.value + "}"

            try:
                parms = json.loads(self.value)
            except Exception as e:
                step.print(f"{VERTICAL} [white on red]Error parsing .llm parameters: {str(e)}[/]\n\n")
                step.print_exception()
                sys.exit(9)

            if not isinstance(parms, dict):
                raise(PromptSyntaxError(f".llm syntax: parameters expected dict, but got {type(parms).__name__}: {self.value}"))


            if 'model' not in parms:
                raise (PromptSyntaxError(f".llm syntax:  'model' parameter is required but missing {self.value}"))

            step.llm = get_llm(model=parms['model'])

            for k,v in parms.items():
                step.llm[k] = v

        except Exception as err:
                step.print_exception()
                sys.exit(9)

        # Now we that we have loaded the LLM,  we will load the API_KEY
        try:
            api_key = keyring.get_password('kestep', username=step.llm['api_key'])
        except keyring.errors.PasswordDeleteError:
            step.print(f"[bold red]Error accessing keyring ('kestep', username={step.llm['api_key']})[/bold red]")
            api_key = None

        if api_key is None:
            api_key = console.input(f"Please enter your {step.llm['company']} API key: ")
            keyring.set_password("kestep", username=step.llm['api_key'], password=api_key)
        if not api_key:
            step.print("[bold red]API key cannot be empty.[/bold red]")
            sys.exit(1)

        step.llm['API_KEY'] = api_key

class _System(_PromptStatement):

    def execute(self, step: PromtpStep) -> None:
        step.print(self.console_str())
        step.messages.append({'role': 'system', 'content': self.value})

class _User(_PromptStatement):

    def execute(self, step: PromtpStep) -> None:
        step.print(self.console_str())
        if step.messages[-1]['role'] == 'user':
            step.messages[-1]['content'] += f"\n{self.value}"
        else:
            step.messages.append({'role':'user', 'content': self.value})








# Create a _PromptStatement subclass depending on keyword
StatementTypes: dict[str, type(_PromptStatement)] = {
    '.#': _Comment,
    '.assistant': _Assistant,
    '.clear': _Clear,
    '.cmd': _Cmd,
    '.debug': _Debug,
    '.exec': _Exec,
    '.include': _Include,
    '.system': _System,
    '.user': _User,
    '.llm': _Llm,
}

def make_statement(step:PromtpStep, msg_no: int, keyword: str, value: str) -> _PromptStatement:
    my_class = StatementTypes[keyword]
    return my_class(step, msg_no, keyword, value)
