

# README.md

## Forward

This is a total rewrite of the first version which used the different LLM python libraries.
This rewrite will use httpx calls and build the json structures internally.
This will greatly reduce the complexity of the application.

Additionally, I plan support for anthropic MCP protocol...



# Knowledge Engineer (kestep)

A command-line tool for knowledge engineering tasks (steps).

## Installation

```bash
pip install kestep
```

## Usage

```bash
kestep [options]
```

## Development

1. Clone the repository
2. Create virtual environment: `python -m venv venv`
3. Activate: `source venv/bin/activate` (Linux/Mac) or `venv\Scripts\activate` (Windows)
4. Install: `pip install -e .`

## License
MIT
