import copy
import glob
import json
import logging
import os
import sys
import threading
import time
from time import sleep

import keyring
import requests
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table
from urllib3.util.util import reraise

from kestep.kestep_api_config import api_config
from kestep.kestep_functions import DefinedFunctions, readfile, DefinedToolsArray, AnthropicToolsArray
from kestep.kestep_util import TOP_LEFT, BOTTOM_LEFT, VERTICAL, HORIZONTAL, TOP_RIGHT, RIGHT_TRIANGLE, LEFT_TRIANGLE, \
    HORIZONTAL_LINE, BOTTOM_RIGHT
from kestep.kestep_util import backup_file

FORMAT = "%(message)s"
logging.basicConfig(level="NOTSET", format=FORMAT, datefmt="[%X]", handlers=[RichHandler()])

log = logging.getLogger(__file__)

models_config: dict[str, any]
json_path = os.path.join(os.path.dirname(__file__), 'kestep_models.json')
with open(json_path, "r") as json_file:
    models_config = json.load(json_file)

console = Console()
terminal_width = console.size.width
stop_event = threading.Event()  # Event to signal when to stop the thread

keywords = ['.#', '.assistant', '.cmd', '.clear', '.include', '.debug', '.exec', '.llm', '.system', '.user', ]


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
        self.messages: list[dict[str, str]] = []
        self.header: dict[str, any] = {}
        self.data: str = ''
        self.console = Console()  # Console for terminal
        self.file_console = None  # Console for file, initialized in execute
        self.model: dict[str, any] = None
        self.model_name:str = None
        self.company:str = None
        self.system_value: str = None

        if debug:
            log.info(f'Instantiated PromptStep(filename="{filename}",debug="{debug}")')

    def print(self, *args, **kwargs):
        """Print method to output to both console and file."""
        self.console.print(*args, **kwargs)  # Print to terminal
        if self.file_console:  # Ensure file is open
            self.file_console.print(*args, **kwargs)  # Print to file

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
            elements = ['llm', 'variables', 'statements', 'messages', 'header', 'data', 'url']

        # print varname: value
        if 'llm' in elements:
            if self.llm:
                table.add_row("LLM Config", "")
                for key, value in self.llm.items():
                    if key == 'API_KEY':
                        value = '... top secret ...'
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


        table.add_row("url", str(self.step.llm['url']))
        table.add_row("header", str(self.header))
        table.add_row("data", str(self.data))

        console.print(table)

    def parse_prompt(self) -> bool:
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
                    continue  # .user, .system, .assistant do not have info on line...

                # and now for the single line dot keywords
                self.statements.append(make_statement(self, len(self.statements), keyword, rest))

            except Exception as e:
                raise PromptSyntaxError(
                    f"{VERTICAL} [red]Error parsing file {self.filename}:{lno} error: {str(e)}.[/]\n\n")

        # console.print(f'Generated statements:')
        # for sno, stmt in enumerate(self.statements):
        #     console.print(f"{sno}: {stmt}")

        return True

    def print_exception(self) -> None:
        """Print exception information to both console and file outputs."""
        self.console.print_exception()  # Print to terminal
        if self.file_console:  # Ensure file is open
            self.file_console.print_exception()  # Print to file

    def load_llm(self, parms: dict[str,str]) ->  None:

        if 'model' not in parms:
            raise PromptSyntaxError(f".llm syntax error: model not defined")
        self.model_name = parms['model']

        if self.model_name not in models_config:
            raise PromptSyntaxError(f"kestep_models.json error: model {self.model_name} is not defined")
        self.model = models_config[self.model_name]

        if 'company' not in self.model:
            raise PromptSyntaxError(f"kestep_models.json error: company not defined for model {self.model_name}")
        self.company = self.model['company']

        if self.company not in api_config:
            raise PromptSyntaxError(f"kestep_models.json error: unknown company {self.company}")

        # copy over llm from kestep_api_config.py
        self.llm = copy.deepcopy(api_config[self.company])

        # over write values placed in .llm line
        for k, v in parms.items():
            self.llm[k] = v

    def execute(self) -> None:
        if self.debug: log.info(f'execute({self.filename} with {len(self.statements)} statements)')

        base_name = os.path.splitext(os.path.basename(self.filename))[0]
        logfile_name = backup_file(f"logs/{base_name}.log", backup_dir='logs', extension='.log')
        with open(logfile_name, 'w') as file:
            self.file_console = Console(file=file)  # Open file for writing

            self.print(
                f"[bold white]{TOP_LEFT}{HORIZONTAL * 2}[/][bold white]{os.path.basename(self.filename):{HORIZONTAL}<{terminal_width - 4}}{TOP_RIGHT}[/]"
            )

            for stmt_no, stmt in enumerate(self.statements):
                if self.company == 'Anthropic' and stmt.keyword == '.system':
                    self.system_value = stmt.value
                    continue
                try:
                    stmt.execute(self)
                except Exception as e:
                    self.print(f"{VERTICAL} [bold red]Error executing statement above : {str(e)}[/bold red]\n\n")
                    self.print(f"{BOTTOM_LEFT}{HORIZONTAL * (terminal_width - 2)}{VERTICAL}")
                    self.print_exception()
                    self.print(f"{BOTTOM_LEFT}{HORIZONTAL * (terminal_width - 2)}{VERTICAL}")
                    sys.exit(9)

            self.print(f"{BOTTOM_LEFT}{HORIZONTAL * (terminal_width - 2)}{BOTTOM_RIGHT}")

            self.file_console.file.close()  # Close file console at end


    def make_data(self) -> None:
        self.data = {
            "model": self.model_name,
            "messages": self.messages,
        }

        match self.company:
            case 'Anthropic':
                self.header = {"Content-Type": "application/json", "anthropic-version": "2023-06-01", "x-api-key": f"{self.llm['API_KEY']}"}
                self.data['system'] = self.system_value     # Anthropic wants system at data['system'] not in a msg
                self.data['tools'] =  AnthropicToolsArray   # Tools Array has 'input_schema' instead of 'parameters'
                self.data['max_tokens'] = int(int(self.model['context']) / 2)  # 1/2 of context size

            case 'XAI':
                self.header = {"Content-Type": "application/json", "Authorization": f"Bearer {self.llm['API_KEY']}"}
                self.data['tools'] = DefinedToolsArray

            case 'OpenAI':
                self.header = {"Content-Type": "application/json", "Authorization": f"Bearer {self.llm['API_KEY']}"}
                self.data['tools'] = DefinedToolsArray

            case 'MistralAI':
                self.header = {"Content-Type": "application/json", "Accept": "application/json","Authorization": f"Bearer {self.llm['API_KEY']}"}
                # Mistral wants a tools array instead of functions array
                self.data['tools'] = DefinedToolsArray

            case _:
                self.print(f"[bold red]Error {self.company} not defined[/bold red]")
                exit(9)

    def traverse_obj(self, _obj, llm_key_name:str):
        t = _obj
        key_list: list[any] = self.llm[llm_key_name]
        for tk in key_list:
            try:
                t = t[tk]
            except KeyError as e:
                self.print(f"[white on red]kestep_api_config.py:error::[/] Traverse '{llm_key_name}':{key_list} not possible in obj:\n{json.dumps(_obj,indent=4)}")
                self.print_exception()
                exit(9)

        return t

    def print_with_wrap(self, is_responce:bool, line:str)-> None:
        line_len = terminal_width - 14
        color = '[bold green]'
        if is_responce:
            color = '[bold blue]'

        line = f"{line}{' '*line_len}"
        print_line = line.replace('\n', '\\n')[:line_len]

        if is_responce:
            hdr = f"[bold white]{VERTICAL}[/]{color}   {LEFT_TRIANGLE}{HORIZONTAL_LINE*7} "
        else:
            hdr = f"[bold white]{VERTICAL}[/]{color}   {HORIZONTAL_LINE*7}{RIGHT_TRIANGLE} "


        lead, trail = print_line.split(':', 1)
        self.print(f"{hdr}{lead}[/]:{trail}[bold white]{VERTICAL}[/]")

    def do_conversation(self, response_obj: dict[str, any], header:str) -> bool:
        continue_converstaion = False


        match self.company:
            case 'Anthropic':
                # Do something when self.company is 'Anthropic'
                pass

            case 'MistralAI':
                # Do something when self.company is 'MistralAI'
                pass

            case 'OpenAI':
                finish_reason = response_obj['choices'][0]['finish_reason']
                is_function_call = False
                if finish_reason == "tool_calls":
                    is_function_call = True
                    continue_converstaion = True

                resp_msgs = response_obj["choices"][0]["message"]
                if type(resp_msgs) != list:
                    resp_msgs = [resp_msgs]

                for msg in resp_msgs:

                    function_name: str = ''
                    function_args: dict[str:any] = {}

                    if is_function_call:
                        if 'tool_calls' in msg:
                            function_call = msg['tool_calls'][0]
                            function_name = function_call['function']['name']
                            function_args = json.loads(function_call['function']['arguments'])

                            # print(f"It's a  Function Call!")
                            # print(f"function_call:{function_call}")
                            self.print_with_wrap(is_responce=True, line=f"Call {function_name}:({function_call['function']['arguments']})")
                            self.messages.append(msg)
                            ret = DefinedFunctions[function_name](**function_args)
                            self.print_with_wrap(is_responce=False, line=f"Call returned: {ret}")
                            self.messages.append({
                                "role": "tool",
                                "content": ret,
                                "tool_call_id": function_call['id']
                            })
                    else:
                        self.messages.append(msg)
                        self.print_with_wrap(is_responce=True, line=f"Response: {msg['content']}")

                return continue_converstaion

            case 'XAI':
                # Do something when self.company is 'XAI'
                finish_reason = self.traverse_obj(response_obj, 'finish_reason')
                is_function_call = finish_reason == self.llm['finish_reason_function_call']

            case _:
                raise PromptSyntaxError(f"Error Unknown company: {self.company}")




        # step.print(f"is_function_call: {is_function_call}")

        # loop over returned msgs, adding them to messages...
        # Process the returned msg, adding it to the messages.


        if type(resp_msgs) != list:
            resp_msgs = [resp_msgs]

        for msg in resp_msgs:

            # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
            # Looks like we will need to do this section individually by company
            # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
            function_name: str = ''
            function_args: dict[str:any] = {}

            if is_function_call:
                continue_converstaion = True
                if self.company == 'OpenAI' and 'tool_calls' in msg:
                    function_name = msg['name']
                    function_args = json.loads(msg['input'])
                elif self.company == 'Anthropic' and msg['type'] == 'tool_use':
                    function_name = msg['name']
                    function_args = msg['input']

                    # print(f"It's a  Function Call!")
                    # print(f"function_call:{function_call}")
                    self.print(f"{header}Call {function_name}({str(msg['input'])[:terminal_width - len(header) - 20]})")
                    ret = DefinedFunctions[function_name](**function_args)
                    self.messages.append(msg)
                    self.messages.append({
                        "role": "tool",
                        "content": ret,
                        "tool_call_id": msg['tool_calls'][0]['id']
                    })
            else:
                self.messages.append(msg)
                # step.print(f"{header}{msg['content'][:terminal_width-len(header)-2]}")
                self.print(f"{header}{msg['text'][:terminal_width - len(header) - 2]}")

        return continue_converstaion



class _PromptStatement:

    def __init__(self, step: PromtpStep, msg_no: int, keyword: str, value: str):
        self.msg_no = msg_no
        self.keyword = keyword
        self.value = value
        self.step = step

    def console_str(self) -> str:
        line_len = terminal_width - 14
        header = f"[bold white]{VERTICAL}[/][white]{self.msg_no:02}[/] [cyan]{self.keyword:<8}[/] "
        value = self.value
        if len(value) == 0:
            value = " "
        lines = value.split("\n")

        rtn = ""
        for line in lines:
            while len(line) > 0:
                print_line = f"{line:<{line_len}}[bold white]{VERTICAL}[/]"
                rtn = f"{rtn}\n{header}[green]{print_line}[/]"
                header = f"[bold white]{VERTICAL}[/]            "
                line = line[line_len:]

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
        step.messages.append({'role': 'assistant', 'content': self.value})


class _Clear(_PromptStatement):

    def execute(self, step: PromtpStep) -> None:
        if step.debug:
            step.print(
                f"[bold white]{VERTICAL}[/][white]{self.msg_no:02}[/] [cyan]{self.keyword:<8}[/] [green]{self.value}[/]")

        try:
            parms = json.loads(self.value)
        except Exception as e:
            step.print(f"{VERTICAL} [white on red]Error parsing .clear parameters: {str(e)}[/]\n\n")
            step.print_exception()
            sys.exit(9)
            # raise PromptSyntaxError(f"Error parsing .clear parameters: {str(e)}")

        if not isinstance(parms, list):
            step.print(
                f"{VERTICAL} [white on red]Error parsing .clear parameters expected list, but got {type(parms).__name__}: {self.value}")
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
            step.print(self.console_str() + ': ', end='')
        else:
            step.print(self.console_str())

        for arg in args_list:
            name, value = arg.split("=", maxsplit=1)
            function_args[name] = value

        if function_name not in DefinedFunctions:
            step.print(
                f"[bold red]Error executing {function_name}({function_args}): {function_name} is not defined.[/bold red]")
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
            step.print(
                f"{VERTICAL} [white on red]Error parsing .debug parameters expected list, but got {type(parms).__name__}: {self.value}")
            sys.exit(9)

        step.debug_print(elements=parms)



class DotThread(threading.Thread):
    def __init__(self):
        super(DotThread, self).__init__()
        self.stop_event = threading.Event()
        self.count = 0
        self.is_running = False

    def run(self):
        self.is_running = True
        self.stop_event.clear()
        self.count = 0
        while not self.stop_event.is_set():
            console.print('.', end='')
            self.count += 1
            sleep(1)
        self.is_running = False

    def start(self):
        if not self.is_running:
            super(DotThread, self).start()

    def stop(self):
        if self.is_running:
            self.stop_event.set()



class _Exec(_PromptStatement):

    def execute(self, step: PromtpStep) -> None:
        """Execute a request to an LLM"""

        first_time = True
        step.print(f"[bold white]{VERTICAL}[/][white]{self.msg_no:02}[/] [cyan]{self.keyword:<8}[/] ", end='')

        continue_conversation: bool = True
        header = f"[bold white]{VERTICAL}[/]            "
        while continue_conversation:
            continue_conversation = False
            step.make_data()

            if first_time:
                first_time = False
                step.print(f"[bold blue]requesting {step.company}::{step.model_name}", end='')
            else:
                step.print(f"{header}[bold blue]requesting {step.company}::{step.model_name}", end='')

            # Create a thread to run the print_dot function in the background
            stop_event.clear()  # Clear Signal to stop the thread
            dot_thread = DotThread()
            start_time = time.time()
            elapsed_time = 0
            try:
                dot_thread.start()  # Start the thread
                # print(f"data={json.dumps(step.messages, indent=4)}")
                response = requests.post(step.llm['url'], json=step.data, headers=step.header)
            except Exception as err:
                step.print(f"{VERTICAL} [white on red]Error during request: {str(err)}[/]\n\n")
                step.print_exception()
                sys.exit(9)

            finally:
                elapsed_time = time.time() - start_time
                dot_thread.stop()# Signal the thread to stop
                dot_thread.join()   # Wait for the thread to finish

            # if the response.status is not 200 then the contents are more or less undefined.
            if response.status_code != 200:
                step.print(
                    f"[bold red]Error calling {step.llm['company']}::{step.llm['model']} API: {response.status_code} {response.reason}[/bold red]")
                step.print(f"url: {step.llm['url']}")
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


            try:
                # Got a good response from LLM
                usage = response_obj['usage']
                toks_in = usage[step.llm['usage_keys'][0]]
                cost_in = toks_in * step.model['input']
                toks_out = usage[step.llm['usage_keys'][1]]
                cost_out = toks_out * step.model['output']
                total = cost_in + cost_out

                no_bytes_remaining = terminal_width - 33 - len(step.company) - len(step.model) - dot_thread.count
                pline = f" {elapsed_time:.2f} secs output tokens {toks_out} at {toks_out / elapsed_time:.2f} tps"
                step.print(f"{pline:<{no_bytes_remaining}}[bold white]{VERTICAL}[/]")


                continue_conversation = step.do_conversation(response_obj, header)

            except Exception as e:
                step.print(f"[white on red]error while handling response:[/]")
                step.print(json.dumps(response_obj,indent=4))
                step.print_exception()
                exit(9)

        if step.debug:
            step.print(f"[bold blue]Response from {step.llm['company']} API:[/bold blue]")
            step.print(response_obj)

        pline = f"Tokens In={toks_in}(${cost_in:06.4f}), Out={toks_out}(${cost_out:06.4f}) Total=${total:06.4f}"
        step.print(f"{header}{pline:<{terminal_width - 14}}[bold white]{VERTICAL}[/]")


class _Include(_PromptStatement):
    # Read a file and add its content to last_msg

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
                raise (PromptSyntaxError(
                    f".llm syntax: parameters expected dict, but got {type(parms).__name__}: {self.value}"))

            if 'model' not in parms:
                raise (PromptSyntaxError(f".llm syntax:  'model' parameter is required but missing {self.value}"))

            step.load_llm(parms)

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

        if len(step.messages) and step.messages[-1]['role'] == 'user':
            step.messages[-1]['content'] += f"\n{self.value}"
        else:
            step.messages.append({'role': 'user', 'content': self.value})


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


def make_statement(step: PromtpStep, msg_no: int, keyword: str, value: str) -> _PromptStatement:
    my_class = StatementTypes[keyword]
    return my_class(step, msg_no, keyword, value)
