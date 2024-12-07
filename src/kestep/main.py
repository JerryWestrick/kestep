import argparse
import glob
import os
import toml
from rich.console import Console
from kestep.kestep import print_models, KepfStep, get_new_api_key, print_step_names, print_step_msgs

console = Console()

def get_version():
    """Retrieve version information from the pyproject.toml."""
    pyproject_path = os.path.join(os.path.dirname(__file__), '../../pyproject.toml')
    with open(pyproject_path, "r") as file:
        pyproject_data = toml.load(file)
    return pyproject_data["project"]["version"]

def get_cmd_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Kestep command line tool.")
    parser.add_argument('-v', '--version', action='store_true', help='Show version information and exit')
    parser.add_argument('-m', '--models', action='store_true', help='List company models information and exit')
    parser.add_argument('-l', '--list', help='List Steps')
    parser.add_argument('-s', '--step', help='List code in Steps')
    parser.add_argument('-e', '--execute', help='Execute one or more Steps')
    parser.add_argument('-k', '--key', action='store_true', help='Ask for (new) Company Key')
    parser.add_argument('-d', '--debug', action='store_true', help='Print message to LLM, for debugging purposes.')

    return parser.parse_args()

def glob_step(step_name) -> list[str] :
    step_pattern = os.path.join('steps/', f"{step_name}*.kepf")
    return sorted(glob.glob(step_pattern))  # Sort the files


def main():
    args = get_cmd_args()

    if args.version:
        # Print the version and exit
        version = get_version()
        console.print(f"[bold cyan]kestep[/] [bold green]version[/] [bold magenta]{version}[/]")
        return

    if args.models:
        # Print the models table and exit
        print_models()
        return

    if args.key:
        get_new_api_key()

    if args.list:
        step_files = glob_step(args.list)
        console.print(f"Found {step_files}")
        if step_files:
            print_step_names(step_files)
        else:
            console.print("[bold red]No step files found.[/bold red]")
        return

    if args.step:
        step_files = glob_step(args.step)
        console.print(f"Found {step_files}")
        if step_files:
            print_step_msgs(step_files)
        else:
            console.print("[bold red]No step files found.[/bold red]")
        return

    if args.execute:
        step_files = glob_step(args.execute)
        console.print(f"Found {step_files}")
        for step_file in step_files:
            step = KepfStep(step_file, args.debug)
            step.parse_kepf()
            step.execute()
        return


if __name__ == "__main__":
    main()
