# nobi-dl

A lightweight command-line tool for searching and downloading movies from publicly available sources.

## Disclaimer / Legal Notice

This tool is provided for educational purposes only. `nobi-dl` scrapes publicly accessible websites to locate and download media content. It does not host, store, or maintain any media files or databases.

Users are solely responsible for ensuring their use of this tool complies with applicable laws and regulations, including copyright laws in their jurisdiction. The developers of `nobi-dl` do not endorse or encourage copyright infringement or any illegal activity.

By using this software, you acknowledge that you are responsible for your actions and any consequences that may arise from using this tool.

## Features

- Search for movies across multiple public sources
- Download movies in various formats and qualities
- Resume interrupted downloads
- List available video and audio formats
- Extract metadata in JSON format
- Verbose and quiet output modes
- Network debugging capabilities
- Browser impersonation for enhanced compatibility
- Modular extractor architecture

## Installation

Install `nobi-dl` from PyPI using pip:

```bash
pip install nobi-dl
```

Verify the installation:

```bash
nobi-dl --version
```

## Development Installation

Clone the repository:

```bash
git clone https://github.com/0xvd/nobi-dl.git
cd nobi-dl
```

Create and activate a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

Install in editable mode:

```bash
pip install -e .
```

Install with optional development dependencies:

```bash
pip install -e ".[dev]"
```

## Usage

Basic usage:

```bash
nobi-dl [OPTIONS] QUERY
```

Search for movies without downloading:

```bash
nobi-dl --search "movie title"
```

## Examples

Search for a movie:

```bash
nobi-dl --search "Inception"
```

Download a movie:

```bash
nobi-dl "Inception 2010"
```

List available formats before downloading:

```bash
nobi-dl -F "The Matrix"
```

Resume an interrupted download:

```bash
nobi-dl -c "Interstellar"
```

Dump metadata to JSON:

```bash
nobi-dl -j "The Godfather" > movie.json
```

## Command-line Options

| Option | Description |
|--------|-------------|
| `--search` | Search for movies without downloading |
| `-F, --list-formats` | List all available formats for a movie |
| `-c, --continue` | Resume an interrupted download |
| `-j, --dump-json` | Output metadata in JSON format |
| `-v, --verbose` | Enable verbose output for debugging |
| `-q, --quiet` | Suppress all output except errors |
| `--parse-network` | Parse and display network requests |
| `--print-traffic` | Print all network traffic for debugging |
| `--impersonate` | Impersonate a specific browser |
| `--list-impersonate-targets` | List available browser impersonation targets |
| `--list-extractors` | Display all available extractors |
| `--extractor` | Use a specific extractor |

## Supported Platforms

- Linux
- Windows

## Contributing

Contributions are welcome. Please follow these guidelines:

**Issues**: Report bugs or request features by opening an issue on the project repository. Provide detailed information about the problem or suggestion.

**Pull Requests**: Fork the repository, create a feature branch, and submit a pull request with a clear description of your changes. Ensure all tests pass before submitting.

## License

This project is licensed under the MIT License. See the LICENSE file for details.
