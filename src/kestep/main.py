import argparse
import configparser
import glob
import os
import platform
import sys

import keyring
import toml
from rich.console import Console
from rich.table import Table

from kestep import call_llm
from kestep.call_llm import print_models, KepfStep

console = Console()

def save_options(options, filename='kestep.ini'):
    conf = configparser.ConfigParser()
    conf['kestep'] = options
    with open(filename, 'w') as configfile:
        conf.write(configfile)


def load_options(filename: str = 'kestep.ini') -> dict[str, str]:
    # get access to ini file...
    if not os.path.exists(filename):
        console.print(f"[bold red]File '{filename}' does not exist.[/bold red]")
        filename = f"../../{filename}"
        console.print(f"[bold red]Trying File '{filename}'.[/bold red]")
        if not os.path.exists(filename):
            console.print(f"[bold red]Trying File '{filename}'.[/bold red]")
            return {}

    config = configparser.ConfigParser()
    config.read(filename)
    return dict(config.items('kestep'))


def get_version():
    """Retrieve version information from the pyproject.toml."""
    pyproject_path = os.path.join(os.path.dirname(__file__), '../../pyproject.toml')
    with open(pyproject_path, "r") as file:
        pyproject_data = toml.load(file)
    return pyproject_data["project"]["version"]


def print_step_msgs(step_files: list[str]) -> None:
    table = Table(title="Execution Messages")
    table.add_column("Step", style="cyan", no_wrap=True)
    table.add_column("Lno", style="blue", no_wrap=True)
    table.add_column("Cmd", style="green", no_wrap=True)
    table.add_column("Message", style="magenta")

    for step_file in step_files:
        # console.print(f"{step_file}")
        try:
            msgs = parse_kepf(step_file)
        except Exception as e:
            console.print(f"[bold red]Error parsing file {step_file} : {str(e)}[/bold red]")
            console.print_exception()
            sys.exit(1)
        title = os.path.basename(step_file)
        if msgs:
            for msgno, msg in enumerate(msgs, start=1):
                table.add_row(title, f"{msgno:03}", msg[0], msg[1])
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


def get_cmd_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Kestep command line tool.")
    parser.add_argument('-v', '--version', action='store_true', help='Show version information and exit')
    parser.add_argument('-l', '--list', action='store_true', help='List company models information and exit')
    parser.add_argument('-m', '--model', help='Name of the model')
    parser.add_argument('-s', '--step', help='List Steps')
    parser.add_argument('-e', '--exec', help='Execute one or more Steps')
    parser.add_argument('-k', '--key', action='store_true', help='Ask for (new) Company Key')
    parser.add_argument('-d', '--debug', action='store_true', help='Print message to LLM, for debugging purposes.')

    return parser.parse_args()



def main():
    args = get_cmd_args()
    model = args.model

    loaded_options = load_options(filename='kestep.ini')
    step_dir = loaded_options['steps']

    if not model:  # if no model given use last one used...
        model = loaded_options['model']


    if args.version:
        # Print the version and exit
        version = get_version()
        console.print(f"[bold cyan]kestep[/] [bold green]version[/] [bold magenta]{version}[/]")
        return

    if args.list:
        # Print the models table and exit
        print_models()
        return

    llm = call_llm.get_llm(model)
    if not llm:
        console.print(f"[bold red]Model {model} is not defined.[/bold red]")
        sys.exit(1)

    try:
        api_key = keyring.get_password('kestep', username=llm['api_key'])
    except keyring.errors.PasswordDeleteError:
        console.print(f"[bold red]Error accessing keyring ('kestep', username={llm['api_key']})[/bold red]")
        api_key = None

    if args.key:
        api_key = None

    if api_key is None:
        api_key = console.input(f"[bold green]Please enter your [/][bold cyan]{llm['company']} API key: [/]")
        keyring.set_password("kestep", username=llm['api_key'], password=api_key)

    if not api_key:
        console.print("[bold red]API key cannot be empty.[/bold red]")
        sys.exit(1)

    llm['API_KEY'] = api_key
    llm['os_system'] = platform.platform(terse=True)
    llm['model'] = model
    llm['debug'] = args.debug

    loaded_options['model'] = model

    if 'steps' not in loaded_options:
        loaded_options["steps"] = "steps"

    if 'log' not in loaded_options:
        loaded_options['logs'] = "logs"

    save_options(loaded_options)

    if args.step:
        step_dir = loaded_options['steps']
        step_pattern = os.path.join(step_dir, f"{args.step}*.kepf")
        step_files = sorted(glob.glob(step_pattern))  # Sort the files

        if step_files:
            if args.debug:
                print_step_msgs(step_files)
            else:
                print_step_names(step_files)
        else:
            console.print("[bold red]No step files found.[/bold red]")
        return

    if args.exec:

        # step_dir = loaded_options['steps']
        step_pattern = os.path.join(step_dir, f"{args.exec}*.kepf")
        step_files = sorted(glob.glob(step_pattern))  # Sort the files
        for step_file in step_files:
            step = KepfStep(step_file, args.debug)
            step.parse_kepf()
            step.execute()

        return


if __name__ == "__main__":
    main()
