import json
import tomllib
from pathlib import Path

from schema import LLMResponse


def extract_reasoning_and_invoice(response_content: str) -> tuple[dict, dict]:
    """Extract reasoning and invoice from the LLM response content.

    Args:
        response_content (str): The response content from the LLM.

    Returns:
        Tuple[dict, dict]: The reasoning and the invoice as a dictionary.
    """
    # Parse the response content using the LLMResponse model
    response = LLMResponse.model_validate_json(response_content)

    # Extract reasoning and invoice
    reasoning = json.dumps(
        response.reasoning.model_dump(), indent=2, ensure_ascii=False
    )
    invoice = json.dumps(response.invoice.model_dump(), indent=2, ensure_ascii=False)

    return reasoning, invoice


def load_system_prompt(file_path: str) -> str:
    """Load the system prompt from a text file.

    Args:
        file_path (str): Path to the text file containing the system prompt.

    Returns:
        str: The system prompt.
    """
    with open(file_path) as file:
        return file.read().strip()


def get_package_root() -> Path:
    """Get the absolute path to the package root directory."""
    return Path(__file__).parent.parent


def get_project_version() -> str:
    """Get the project version from pyproject.toml.

    Returns:
        str: The version string from pyproject.toml, or "0.1.0" as fallback if version cannot be read.
    """
    try:
        # Get the project root directory
        project_root = get_package_root()
        pyproject_path = project_root / "pyproject.toml"

        with open(pyproject_path, "rb") as f:
            pyproject_data = tomllib.load(f)
        version = pyproject_data.get("project", {}).get("version", "0.0.0-dev")
        return version
    except Exception as e:
        print(f"Error reading version from pyproject.toml: {e}")
        return "0.0.0-dev"  # Default fallback version
