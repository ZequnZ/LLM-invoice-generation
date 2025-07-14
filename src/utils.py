import json

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
