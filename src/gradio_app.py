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

# Add CSS styles for invoice formatting
INVOICE_STYLES = """
<style>
.invoice-container {
    font-family: Arial, sans-serif;
    max-width: 100%;
    margin: 0 auto;
    padding: 20px;
    border: 1px solid #e0e0e0;
    box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
    background-color: #fff;
}
.invoice-header {
    display: flex;
    justify-content: space-between;
    margin-bottom: 20px;
    padding-bottom: 15px;
    border-bottom: 2px solid #3498db;
}
.invoice-details {
    display: flex;
    justify-content: space-between;
    margin-bottom: 30px;
}
.invoice-details-left, .invoice-details-right {
    flex-basis: 48%;
}
.invoice-title {
    font-size: 24px;
    color: #3498db;
    margin-bottom: 5px;
}
.invoice-id {
    font-weight: bold;
    color: #555;
}
.section-title {
    font-size: 18px;
    color: #3498db;
    margin-bottom: 10px;
    border-bottom: 1px solid #e0e0e0;
    padding-bottom: 5px;
}
.invoice-items {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 20px;
}
.invoice-items th, .invoice-items td {
    padding: 12px;
    text-align: left;
    border-bottom: 1px solid #e0e0e0;
}
.invoice-items th {
    background-color: #f8f8f8;
    color: #333;
}
.invoice-items tr:nth-child(even) {
    background-color: #f9f9f9;
}
.invoice-items tr:hover {
    background-color: #f1f1f1;
}
.invoice-total {
    width: 60%;
    margin-left: auto;
    margin-right: 0;
    border-collapse: collapse;
    margin-bottom: 20px;
}
.invoice-total td {
    padding: 8px;
    text-align: right;
}
.invoice-total .total-row {
    font-weight: bold;
    font-size: 1.1em;
    background-color: #f0f7ff;
}
.invoice-notes {
    padding: 10px;
    background-color: #f9f9f9;
    border-left: 4px solid #3498db;
    margin-bottom: 20px;
}
.payment-terms {
    font-style: italic;
    color: #555;
    margin-bottom: 15px;
}
.contact-info {
    color: #666;
    font-size: 0.9em;
}
</style>
"""


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


def format_company_info_as_markdown(company_data: dict) -> str:
    """Format company data as a readable markdown structure.

    Args:
        company_data (dict): The company data dictionary.

    Returns:
        str: Formatted company information in Markdown.
    """
    if not company_data:
        return "### Company does not exist"

    markdown = ""

    # General Company Info
    markdown += "#### Business Details\n"
    markdown += f"**Name**: {company_data.get('business_name', 'N/A')}\n\n"
    markdown += f"**Address**: {company_data.get('business_address', 'N/A')}\n\n"
    markdown += f"**Contact**: {company_data.get('business_contact', 'N/A')}\n\n"

    # Items
    if "item_list" in company_data and company_data["item_list"]:
        markdown += "#### Available Items\n\n"
        markdown += "| Item Name | Unit Price (Tax included)  | Tax Rate |\n"
        markdown += "|----------|------------|----------|\n"

        for item in company_data["item_list"]:
            markdown += f"| {item.get('item_name', 'N/A')} | €{item.get('unit_price', 0):.2f} | {item.get('tax_rate', 0)}% |\n"
        markdown += "\n"

    # Customers
    if "customer_list" in company_data and company_data["customer_list"]:
        markdown += "#### Customers\n\n"
        for i, customer in enumerate(company_data["customer_list"], 1):
            markdown += f"**Customer {i}**: {customer.get('customer_name', 'N/A')}\n\n"
            markdown += f"**Address**: {customer.get('customer_address', 'N/A')}\n\n"
            markdown += f"**Contact**: {customer.get('customer_contact', 'N/A')}\n\n"

    return markdown


def display_company_info(company_id: str) -> str:
    """Display company information based on the company ID.

    Args:
        company_id (str): The ID of the company.

    Returns:
        str: The company information in Markdown format.
    """
    company_data = get_data_from_redis(company_id)
    if not company_data:
        return "### Company does not exist"

    return format_company_info_as_markdown(company_data)


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
) -> tuple[str, str, gr.update, gr.update]:
    """Update the reasoning output first and then the invoice output after a delay.

    Args:
        company_id (str): The ID of the company.
        input_message (str): The input message from the user.
        header (str): The header to be displayed at the beginning of the reasoning.

    Returns:
        Tuple[str, str, gr.update, gr.update]: The reasoning markdown, formatted invoice HTML,
        and update objects for showing results and hiding loading message.
    """
    reasoning, invoice, _ = generate_invoice(company_id, input_message)
    reasoning_markdown = format_reasoning_as_markdown(json.loads(reasoning), header)
    invoice_html = format_invoice_as_html(invoice)
    # Return updates to show results and hide loading
    return (
        reasoning_markdown,
        invoice_html,
        gr.update(visible=True),
        gr.update(visible=False),
    )


def send_follow_up_message(
    company_id: str, follow_up_message: str
) -> tuple[str, str, gr.update, gr.update]:
    """Send a follow-up message to the LLM and update reasoning and invoice.

    Args:
        company_id (str): The ID of the company.
        follow_up_message (str): The follow-up message from the user.

    Returns:
        Tuple[str, str, gr.update, gr.update]: The updated reasoning, generated invoice,
        and update objects for showing results and hiding loading message.
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

    # Format invoice as HTML for better display
    invoice_html = format_invoice_as_html(invoice)

    # Return updates to show results and hide loading
    return (
        reasoning_markdown,
        invoice_html,
        gr.update(visible=True),
        gr.update(visible=False),
    )


def format_invoice_as_html(invoice_json: str) -> str:
    """Format the invoice JSON as HTML for better visualization.

    Args:
        invoice_json (str): The invoice JSON string.

    Returns:
        str: The formatted invoice as HTML.
    """
    try:
        # Parse the invoice JSON
        invoice_data = json.loads(invoice_json)

        # Check if it's a not-invoice response
        if (
            "output" in invoice_data
            and invoice_data["output"] == "INPUT IS NOT FOR A INVOICE"
        ):
            return "<p>The input does not appear to be for an invoice generation request.</p>"

        # Start building HTML with styles
        html = INVOICE_STYLES
        html += '<div class="invoice-container">'

        # Header section
        html += '<div class="invoice-header">'
        html += f'<div><h1 class="invoice-title">{invoice_data.get("business_name", "")}</h1>'
        html += f"<p>{invoice_data.get('business_address', '')}</p>"
        html += f'<p class="contact-info">{invoice_data.get("business_contact", "")}</p></div>'
        html += f'<div><h2>INVOICE</h2><p class="invoice-id">#{invoice_data.get("invoice_number", "")}</p>'
        html += f"<p>Date: {invoice_data.get('invoice_date', '')}</p>"
        html += f"<p>Due: {invoice_data.get('due_date', '')}</p></div>"
        html += "</div>"

        # Customer and invoice details
        html += '<div class="invoice-details">'
        html += '<div class="invoice-details-left">'
        html += '<h3 class="section-title">Bill To:</h3>'
        html += f"<p><strong>{invoice_data.get('customer_name', '')}</strong></p>"
        html += f"<p>{invoice_data.get('customer_address', '')}</p>"
        html += f"<p>{invoice_data.get('customer_contact', '')}</p>"
        html += "</div>"
        html += "</div>"

        # Items table
        html += '<h3 class="section-title">Items</h3>'
        html += '<table class="invoice-items">'
        html += "<thead><tr><th>Item Name</th><th>Quantity</th><th>Unit Price</th><th>Tax Rate</th><th>Total</th></tr></thead>"
        html += "<tbody>"

        # Add each item
        for item in invoice_data.get("items", []):
            html += "<tr>"
            html += f"<td>{item.get('name', '')}</td>"
            html += f"<td>{item.get('quantity', '')}</td>"
            html += f"<td>€{item.get('unit_price', 0):.2f}</td>"
            html += f"<td>{item.get('tax_rate', 0)}%</td>"
            html += f"<td>€{item.get('total_price', 0):.2f}</td>"
            html += "</tr>"
        html += "</tbody></table>"

        # Totals
        html += '<table class="invoice-total">'
        html += f"<tr><td>Subtotal:</td><td>€{invoice_data.get('subtotal', 0):.2f}</td></tr>"
        html += f"<tr><td>Tax:</td><td>€{invoice_data.get('tax', 0):.2f}</td></tr>"
        html += f'<tr class="total-row"><td>Total:</td><td>€{invoice_data.get("total_due", 0):.2f}</td></tr>'
        html += "</table>"

        # Payment terms and notes
        html += f'<div class="payment-terms"><strong>Payment Terms:</strong> {invoice_data.get("payment_terms", "")}</div>'

        if invoice_data.get("notes"):
            html += f'<div class="invoice-notes">{invoice_data.get("notes", "")}</div>'

        # Close the container
        html += "</div>"

        return html
    except Exception as e:
        print(f"Error formatting invoice: {e}")
        # If there's an error, return the raw JSON with line breaks for readability
        return f"<pre>{invoice_json}</pre>"


with gr.Blocks(theme=gr.themes.Default(primary_hue="blue")) as demo:
    gr.Markdown("# Invoice Generation App - v 3.0")
    # First row: Input data and company information
    with gr.Row():
        with gr.Column(scale=1):
            with gr.Group():
                gr.Markdown("### Input Data")
                company_id = gr.Textbox(
                    label="Company ID", placeholder="Enter company ID..."
                )
                company_status = gr.Markdown("", elem_id="company-status")
                input_message = gr.Textbox(
                    label="Invoice Request",
                    placeholder="Example: Create an invoice for Global Corp for 2 AI Software Licenses and 1 Cloud Storage Subscription",
                    lines=3,
                )
                generate_button = gr.Button("Generate Invoice", variant="primary")
                follow_up_message = gr.Textbox(
                    label="Follow-up Message",
                    placeholder="Need changes? Describe them here...",
                    visible=False,
                    lines=2,
                )
                follow_up_button = gr.Button(
                    "Send Follow-up", visible=False, variant="secondary"
                )

        with gr.Column(scale=1):
            gr.Markdown("### Company Information")
            company_info = gr.Markdown(label="")

    with gr.Row():
        gr.Markdown("---")

    # Loading message
    with gr.Row() as loading_message:
        gr.Markdown("### Calling LLM now... Please wait.", elem_id="loading-message")
    loading_message.visible = False

    # Results row: Invoice preview and reasoning (initially hidden)
    with gr.Row(equal_height=True, visible=False) as results_row:
        with gr.Column(scale=1):
            gr.Markdown("### Invoice Preview")
            invoice_output = gr.HTML()  # Using HTML component for rich invoice display
        with gr.Column(scale=1):
            gr.Markdown("### Reasoning")
            reasoning_output = gr.Markdown(label="")

    company_id.change(fn=display_company_info, inputs=company_id, outputs=company_info)

    # First click handler - show loading message, hide results
    generate_button.click(
        fn=lambda: (gr.update(visible=True), gr.update(visible=False)),
        inputs=[],
        outputs=[loading_message, results_row],
    )

    # Second click handler - process invoice and update UI
    generate_button.click(
        fn=lambda company_id, input_message: update_reasoning_and_invoice(
            company_id, input_message
        ),
        inputs=[company_id, input_message],
        outputs=[reasoning_output, invoice_output, results_row, loading_message],
    )

    # Third click handler - show follow-up controls
    generate_button.click(
        fn=lambda: (gr.update(visible=True), gr.update(visible=True), ""),
        inputs=[],
        outputs=[follow_up_message, follow_up_button, follow_up_message],
    )

    # Follow-up button - first show loading message, hide results
    follow_up_button.click(
        fn=lambda: (gr.update(visible=True), gr.update(visible=False)),
        inputs=[],
        outputs=[loading_message, results_row],
    )

    # Follow-up button - process update and show results
    follow_up_button.click(
        fn=send_follow_up_message,
        inputs=[company_id, follow_up_message],
        outputs=[reasoning_output, invoice_output, results_row, loading_message],
    )

if __name__ == "__main__":
    demo.launch(share=False, debug=True, server_port=8002, server_name="0.0.0.0")
