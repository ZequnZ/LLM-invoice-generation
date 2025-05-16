import json
import os
from datetime import datetime

import gradio as gr
import redis
from chat_llm import Thread
from schema import LLMResponse
from utils import extract_reasoning_and_invoice, load_system_prompt

# Initialize the Thread globally
thread = None


def get_data_from_redis(company_id: str) -> dict:
    """Retrieve data from Redis for a given company ID.

    Args:
        company_id (str): The ID of the company.

    Returns:
        dict: Data retrieved from Redis.
    """
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", 6379))
    redis_password = os.getenv("REDIS_PASSWORD", "password")

    try:
        client = redis.StrictRedis(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            decode_responses=True,
        )
        client.ping()
        print("Connected to Redis")

        # Retrieve data from Redis
        company_data = client.hgetall(f"company:{company_id}")
        if not company_data:
            return None

        # Convert JSON strings back to Python objects
        for key, value in company_data.items():
            try:
                company_data[key] = json.loads(value)
            except json.JSONDecodeError:
                pass

        return company_data

    except redis.ConnectionError as e:
        print(f"Failed to connect to Redis: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


def generate_invoice(company_id: str, input_message: str) -> tuple[str, str, Thread]:
    """Generate an invoice using the LLM based on the company ID and input message.

    Args:
        company_id (str): The ID of the company.
        input_message (str): The input message from the user.

    Returns:
        Tuple[str, str, Thread]: The reasoning, generated invoice, and the Thread instance.
    """
    global thread
    # Get data from Redis
    company_data = get_data_from_redis(company_id)
    if not company_data:
        return "Company does not exist", "", None

    # Combine the input message with company info
    current_date = datetime.now().strftime("%Y-%m-%d")

    user_input = f"{input_message}\n\nCurrent Date: {current_date}\n\nCompany Info:\n{json.dumps(company_data, indent=2)}"
    # print(user_input)

    # Load the system prompt from the file
    sys_prompt = load_system_prompt("src/system_prompt.txt")

    # Initialize the Thread with the system prompt
    thread = Thread(sys_prompt=sys_prompt)

    # Call the LLM and get the response
    response = thread.send_message(
        content=user_input,
        save_message=True,
        show_all=False,
        verbose=True,
        response_format=LLMResponse,
    )

    # Extract reasoning and invoice from the response
    reasoning, invoice = extract_reasoning_and_invoice(response["content"])

    return reasoning, invoice, thread


def display_company_info(company_id: str) -> str:
    """Display company information based on the company ID.

    Args:
        company_id (str): The ID of the company.

    Returns:
        str: The company information in JSON format.
    """
    company_data = get_data_from_redis(company_id)
    if not company_data:
        return "Company does not exist"
    return json.dumps(company_data, indent=2, ensure_ascii=False)


def format_reasoning_as_markdown(reasoning: dict, header: str = "") -> str:
    """Format the reasoning dictionary as Markdown with an optional header.

    Args:
        reasoning (dict): The reasoning dictionary.
        header (str): The header to be displayed at the beginning.

    Returns:
        str: The formatted reasoning in Markdown.
    """
    markdown = f"### {header}\n\n" if header else ""
    for key, value in reasoning.items():
        markdown += f"#### {key}\n{value}\n\n"
    return markdown


def update_reasoning_and_invoice(
    company_id: str, input_message: str, header: str = ""
) -> tuple[str, str]:
    """Update the reasoning output first and then the invoice output after a delay.

    Args:
        company_id (str): The ID of the company.
        input_message (str): The input message from the user.
        header (str): The header to be displayed at the beginning of the reasoning.

    Returns:
        Tuple[str, str, bool]: The reasoning, generated invoice, and a flag to make the invoice editable.
    """
    reasoning, invoice, _ = generate_invoice(company_id, input_message)
    reasoning_markdown = format_reasoning_as_markdown(json.loads(reasoning), header)
    return reasoning_markdown, invoice


def send_follow_up_message(company_id: str, follow_up_message: str) -> tuple[str, str]:
    """Send a follow-up message to the LLM and update reasoning and invoice.

    Args:
        company_id (str): The ID of the company.
        follow_up_message (str): The follow-up message from the user.

    Returns:
        Tuple[str, str]: The updated reasoning and generated invoice.
    """
    global thread
    if not thread:
        return (
            "No initial invoice generation found. Please generate an invoice first.",
            "",
        )

    # Get data from Redis
    company_data = get_data_from_redis(company_id)
    if not company_data:
        return "Company does not exist", ""

    # Combine the follow-up message with company info
    # current_date = datetime.now().strftime("%Y-%m-%d")

    # user_input = f"{follow_up_message}\n\nCurrent Date: {current_date}\n\nCompany Info:\n{json.dumps(company_data, indent=2)}"
    user_input = follow_up_message

    # Call the LLM and get the response
    response = thread.send_message(
        content=user_input,
        save_message=True,
        show_all=False,
        verbose=True,
        response_format=LLMResponse,
    )

    # Extract reasoning and invoice from the response
    reasoning, invoice = extract_reasoning_and_invoice(response["content"])
    reasoning_markdown = format_reasoning_as_markdown(json.loads(reasoning))

    return reasoning_markdown, invoice


with gr.Blocks() as demo:
    gr.Markdown("# Invoice Generation App - v 3.0")
    with gr.Row():
        with gr.Column():
            company_id = gr.Textbox(label="Company ID")
            input_message = gr.Textbox(label="Input Message")
            generate_button = gr.Button("Generate Invoice")
            follow_up_message = gr.Textbox(label="Follow-up Message", visible=False)
            follow_up_button = gr.Button("Send Follow-up", visible=False)
        with gr.Column():
            company_info = gr.Textbox(label="Company Info", interactive=False)

    with gr.Row():
        with gr.Column():
            with gr.Blocks(css="footer{display:none !important}"):
                with gr.Accordion("Reasoning:", open=True):
                    reasoning_output = gr.Markdown(label="Reasoning")
        with gr.Column():
            invoice_output = gr.Textbox(label="Generated Invoice", interactive=True)

    company_id.change(fn=display_company_info, inputs=company_id, outputs=company_info)
    generate_button.click(
        fn=lambda company_id, input_message: update_reasoning_and_invoice(
            company_id, input_message
        ),
        inputs=[company_id, input_message],
        outputs=[reasoning_output, invoice_output],
    )
    generate_button.click(
        fn=lambda: (gr.update(visible=True), gr.update(visible=True), ""),
        inputs=[],
        outputs=[follow_up_message, follow_up_button, follow_up_message],
    )
    follow_up_button.click(
        fn=send_follow_up_message,
        inputs=[company_id, follow_up_message],
        outputs=[reasoning_output, invoice_output],
    )

if __name__ == "__main__":
    demo.launch(share=False, debug=True, server_port=8002, server_name="0.0.0.0")
