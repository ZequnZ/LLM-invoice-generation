import json
import logging
import logging.config
import os
import time
import uuid
from datetime import datetime

import gradio as gr
import redis

from chat_llm import Thread
from formats import format_company_info_as_markdown, format_reasoning_as_markdown
from logger_config import base_log_config
from schema import LLMResponse, NewInvoiceItem
from styles import INVOICE_STYLES
from utils import extract_reasoning_and_invoice, get_project_version, load_system_prompt

# Setup logger for this module
logging.config.dictConfig(base_log_config)
logger = logging.getLogger(__name__)

# Initialize global variables
# thread = None
current_invoice_json = None  # Store the current invoice JSON for editing

# Global variables to store available items (from database) and new items (to be added to database) with IDs
available_items_global = []
new_items_global = {}

# Global variables to track saved items to avoid duplicates
saved_items_global = set()  # Track IDs of items already saved to database

# CONFIRM BUTTON VISIBILITY LOGIC:
# The confirm button is shown only when ALL of the following conditions are met:
# 1. is_valid_invoice = True (the request is for a valid invoice)
# 2. The invoice is completed, meaning:
#    - There are no new items, OR
#    - All new items have been filled with valid values (no PLACEHOLDER, empty, or invalid values)
#
# This ensures users can only confirm invoices that are both valid and complete.
#
# NEW ITEM MANAGEMENT LOGIC:
# - Available Items: Items that already exist in company database with known pricing
# - New Items: Items that don't exist in database and need to be added (may have PLACEHOLDER values)
# - Users can edit new items in real-time via DataFrame before confirming the invoice
# - Once confirmed, new items will be saved to the company database for future use
#
# FOLLOW-UP MESSAGE ENHANCEMENT:
# Follow-up messages now include the current state of all items (available and new items)
# including any real-time edits made by users in the DataFrame. This ensures the LLM
# has complete context about the current invoice state when processing follow-up requests.


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
        # logger.info("Connected to Redis")

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


def generate_invoice(
    company_id: str, input_message: str, session_state: dict
) -> tuple[str, str, Thread]:
    """Generate an invoice using the LLM based on the company ID and input message.

    Args:
        company_id (str): The ID of the company.
        input_message (str): The input message from the user.

    Returns:
        Tuple[str, str, Thread]: The reasoning, generated invoice, and the Thread instance.
    """
    thread = session_state["thread"]
    logger.info(f"Current token usage: {thread.total_tokens}")
    # Get data from Redis
    company_data = get_data_from_redis(company_id)
    if not company_data:
        return "Company does not exist", "", None

    # Combine the input message with company info
    current_date = datetime.now().strftime("%Y-%m-%d")

    user_input = f"{input_message}\n\nCurrent Date: {current_date}\n\nCompany Info:\n{json.dumps(company_data, indent=2)}"
    # print(user_input)

    # # Load the system prompt from the file
    # sys_prompt = load_system_prompt("src/system_prompt.txt")

    # # Initialize the Thread with the system prompt
    # thread = Thread(sys_prompt=sys_prompt)

    # Call the LLM and get the response
    response = thread.send_message(
        content=user_input,
        save_message=True,
        show_all=False,
        verbose=True,
        response_format=LLMResponse,
    )
    logger.info(f"Current token usage after user input: {thread.total_tokens}")

    # Extract reasoning and invoice from the response
    reasoning, invoice = extract_reasoning_and_invoice(response["content"])

    return reasoning, invoice, thread


def display_company_info(company_id: str) -> str:
    """Display company information based on the company ID.

    Args:
        company_id (str): The ID of the company.

    Returns:
        str: The company information in Markdown format.
    """
    # logger.info(f"Displaying company info for company ID: {company_id}")
    company_data = get_data_from_redis(company_id)
    # logger.info(f"Company data: {company_data}")
    if not company_data:
        return "### Company does not exist"

    return format_company_info_as_markdown(company_data)


def assign_ids_to_new_items(new_items: list) -> dict:
    """
    Assign unique IDs to new items that need to be added to the database.

    Args:
        new_items: List of new items that don't exist in company database

    Returns:
        dict: Dictionary with unique IDs as keys and item data as values
    """
    result = {}
    for item in new_items:
        id = str(uuid.uuid4())
        result[id] = item
    return result


def get_invoice_html(  # noqa: C901
    invoice_json: str, available_items: list, new_items_dict: dict
) -> str:
    """
    Generate invoice HTML combining available items (from database) and new items (to be added).

    Args:
        invoice_json: Base invoice JSON string
        available_items: List of items that exist in company database
        new_items_dict: Dictionary of new items that need to be added to database

    Returns:
        Tuple of (invoice_data_dict, invoice_html_string)
    """
    # Compose invoice JSON for preview: combine available and new items
    try:
        invoice_data = json.loads(invoice_json)
    except Exception:
        invoice_data = {}
    # Convert new items with proper type handling for user edits
    new_items_list = []
    for item in new_items_dict.values():
        # Ensure proper type conversion for edited values from DataFrame
        processed_item = item.copy()
        logger.info(f"processed_item: {json.dumps(processed_item, indent=2)}")

        # Handle quantity conversion
        if processed_item.get("quantity") not in ["PLACEHOLDER", "", None]:
            try:
                processed_item["quantity"] = int(processed_item["quantity"])
            except (ValueError, TypeError):
                processed_item["quantity"] = "PLACEHOLDER"
        else:
            processed_item["quantity"] = "PLACEHOLDER"

        # Handle unit_price conversion
        if processed_item.get("unit_price") not in ["PLACEHOLDER", "", None]:
            try:
                processed_item["unit_price"] = float(processed_item["unit_price"])
            except (ValueError, TypeError):
                processed_item["unit_price"] = "PLACEHOLDER"
        else:
            processed_item["unit_price"] = "PLACEHOLDER"

        # Handle tax_rate conversion
        if processed_item.get("tax_rate") not in ["PLACEHOLDER", "", None]:
            try:
                processed_item["tax_rate"] = float(processed_item["tax_rate"])
            except (ValueError, TypeError):
                processed_item["tax_rate"] = "PLACEHOLDER"
        else:
            processed_item["tax_rate"] = "PLACEHOLDER"

        # Ensure is_new_item is set
        processed_item["is_new_item"] = True

        try:
            try:
                # Compute total price for new item
                total_price = float(processed_item["quantity"]) * float(
                    processed_item["unit_price"]
                )
                processed_item["total_price"] = total_price
            except Exception as e:
                logger.error(f"Error computing total price for new item: {e}")
                processed_item["total_price"] = "PLACEHOLDER"

            # Create NewInvoiceItem object and convert to dict
            new_item_obj = NewInvoiceItem(**processed_item)
            new_items_list.append(new_item_obj.model_dump())
        except Exception as e:
            logger.error(
                f"Error creating NewInvoiceItem: {e}, using processed_item directly"
            )
            new_items_list.append(processed_item)

    # print("new_items_list:", new_items_list)
    invoice_data["items"] = available_items + new_items_list

    # Recalculate totals
    subtotal = sum([item.get("total_price", 0) for item in available_items])
    tax = sum(
        [
            item.get("total_price", 0) * item.get("tax_rate", 0) / 100
            for item in available_items
        ]
    )
    total_due = subtotal + tax

    for item in invoice_data["items"][len(available_items) :]:
        # Check if any new item still has PLACEHOLDER values
        # If any item has a "PLACEHOLDER" value, set all totals to "PLACEHOLDER"
        # This indicates the invoice is not yet complete (new items need user input)
        # Exclude 'is_new_item' field from PLACEHOLDER check
        item_values_to_check = {k: v for k, v in item.items() if k != "is_new_item"}
        if "PLACEHOLDER" in list(item_values_to_check.values()):
            subtotal = tax = total_due = "PLACEHOLDER"
            break

        # Enhanced type conversion with better error handling
        quantity = item.get("quantity", 0)
        unit_price = item.get("unit_price", 0)
        tax_rate = item.get("tax_rate", 0)

        # Convert quantity to integer
        if isinstance(quantity, str) and quantity.strip():
            try:
                quantity = int(float(quantity))  # Handle cases like "5.0"
                item["quantity"] = quantity
            except (ValueError, TypeError) as e:
                logger.error(f"Error converting quantity '{quantity}' to int: {e}")
                quantity = 0
        elif not isinstance(quantity, int | float):
            quantity = 0

        # Convert unit_price to float
        if isinstance(unit_price, str) and unit_price.strip():
            try:
                unit_price = float(unit_price)
                item["unit_price"] = unit_price
            except (ValueError, TypeError) as e:
                logger.error(
                    f"Error converting unit_price '{unit_price}' to float: {e}"
                )
                unit_price = 0.0
        elif not isinstance(unit_price, int | float):
            unit_price = 0.0

        # Convert tax_rate to float
        if isinstance(tax_rate, str) and tax_rate.strip():
            try:
                tax_rate = float(tax_rate)
                item["tax_rate"] = tax_rate
            except (ValueError, TypeError) as e:
                logger.error(f"Error converting tax_rate '{tax_rate}' to float: {e}")
                tax_rate = 0.0
        elif not isinstance(tax_rate, int | float):
            tax_rate = 0.0

        # Calculate total price for new item
        total_price = float(quantity) * float(unit_price)
        item["total_price"] = total_price

        # Add to running totals
        subtotal += total_price
        tax += total_price * float(tax_rate) / 100.0

        logger.info(
            f"Calculated new item: {item.get('name')} - Qty:{quantity} × €{unit_price} = €{total_price} (Tax: {tax_rate}%)"
        )
    total_due = subtotal + tax if total_due != "PLACEHOLDER" else "PLACEHOLDER"
    invoice_data["subtotal"] = subtotal
    invoice_data["tax"] = tax
    invoice_data["total_due"] = total_due
    # print("invoice_data:", invoice_data)
    invoice_html = format_invoice_as_html(json.dumps(invoice_data))
    return invoice_data, invoice_html


def get_reasoning_and_invoice(
    company_id: str, input_message: str, session_state: dict, header: str = ""
) -> tuple[str, str, gr.update, gr.update, gr.update, gr.update, list | None]:
    """Update the reasoning output first and then the invoice output after a delay.

    Args:
        company_id (str): The ID of the company.
        input_message (str): The input message from the user.
        session_state (dict): The session state.
        header (str): The header to be displayed at the beginning of the reasoning.

    Returns:
        Tuple: The reasoning markdown, formatted invoice HTML, update objects for showing results,
        hiding loading message, showing follow-up group, showing confirmation group,
        and the list of unclear items for the DataFrame if there are any.
    """
    # logger.info(f"User input to generate invoice: {input_message}")
    reasoning, invoice, _ = generate_invoice(company_id, input_message, session_state)
    # logger.info("LLM call completed")
    # logger.info(f"session_state['thread'].total_tokens: {session_state['thread'].total_tokens}")
    reasoning_json = json.loads(reasoning)
    reasoning_markdown = format_reasoning_as_markdown(reasoning_json, header)

    # Extract available items (from database) and new items (to be added to database)
    available_items = reasoning_json.get("Analysis", {}).get("available_items", [])
    new_items = reasoning_json.get("Analysis", {}).get("new_items", [])
    new_items_dict = assign_ids_to_new_items(new_items)

    session_state["available_items"] = available_items
    session_state["new_items_dict"] = new_items_dict

    print("available_items:", available_items)
    logger.info(f"new_items_dict: {json.dumps(new_items_dict, indent=2)}")

    invoice_data, invoice_html = get_invoice_html(
        invoice, available_items, new_items_dict
    )

    # Check if the invoice is valid and completed
    is_valid_invoice = reasoning_json.get("is_valid_invoice", False)
    has_new_items = reasoning_json.get("has_new_items", False)

    # Determine if invoice is completed (no new items or all new items filled)
    invoice_completed = is_invoice_completed(new_items_dict)

    # Show confirm button only if invoice is valid AND completed
    show_confirm_button = is_valid_invoice and invoice_completed

    new_items_df = None
    if has_new_items:
        # Prepare DataFrame data for new items that need to be added to database
        new_items_df = [
            [
                new_items_dict[item].get("name", ""),
                new_items_dict[item].get("quantity", ""),
                new_items_dict[item].get("unit_price", ""),
                new_items_dict[item].get("tax_rate", ""),
            ]
            for item in new_items_dict
        ]

    # Store the original invoice JSON for later use with the DataFrame
    session_state["current_invoice_json"] = json.dumps(invoice_data)

    # Return updates to show results and hide loading
    return (
        reasoning_markdown,
        invoice_html,
        gr.update(visible=True),  # Show results row
        gr.update(visible=False),  # Hide loading message
        gr.update(visible=True),  # Show follow-up group
        gr.update(
            visible=show_confirm_button
        ),  # Show confirmation group only if valid AND completed
        gr.update(
            visible=has_new_items
        ),  # Show new items group if there are new items to be added
        new_items_df,  # Populate the DataFrame with new items
    )


def save_item_to_database(company_id: str, item_data: dict) -> bool:
    """
    Save a single new item to the company's database in Redis.

    Args:
        company_id (str): The ID of the company
        item_data (dict): The item data to save

    Returns:
        bool: True if saved successfully, False otherwise
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

        # Get current company data
        company_data = client.hgetall(f"company:{company_id}")
        if not company_data:
            print(f"Company {company_id} not found")
            return False

        # Parse existing item_list
        current_items = []
        if "item_list" in company_data:
            try:
                current_items = json.loads(company_data["item_list"])
            except json.JSONDecodeError:
                current_items = []

        print("current_items:", current_items)
        print("item_data:", item_data)
        # Create new item for database (remove is_new_item field and ensure proper types)
        new_item = {
            "item_name": item_data.get("name", ""),
            "unit_price": float(item_data.get("unit_price", 0)),
            "tax_rate": float(item_data.get("tax_rate", 0)),
        }
        print("new_item:", new_item)
        # Check if item already exists (by name)
        item_exists = any(
            existing_item.get("item_name", "").lower().strip()
            == new_item["item_name"].lower().strip()
            for existing_item in current_items
        )

        if item_exists:
            print(f"Item '{new_item['item_name']}' already exists in database")
            return False

        # Add new item to the list
        current_items.append(new_item)

        # Save updated item_list back to Redis
        client.hset(f"company:{company_id}", "item_list", json.dumps(current_items))

        print(
            f"Successfully saved item '{new_item['item_name']}' to company {company_id} database"
        )
        return True

    except Exception as e:
        print(f"Error saving item to database: {e}")
        return False


def save_multiple_items_to_database(company_id: str, items_data: dict) -> dict:
    """
    Save multiple new items to the company's database in Redis.

    Args:
        company_id (str): The ID of the company
        items_data (dict): Dictionary of item IDs to item data

    Returns:
        dict: Results of save operations {item_id: success_status}
    """
    results = {}
    for item_id, item_data in items_data.items():
        # Skip if already saved
        if item_id in saved_items_global:
            results[item_id] = "already_saved"
            continue

        success = save_item_to_database(company_id, item_data)
        results[item_id] = "success" if success else "failed"

        if success:
            saved_items_global.add(item_id)

    return results


def create_new_items_interface(session_state: dict):
    """
    Create individual item cards with save buttons for the new items management.
    This is called when new items are detected.
    """
    new_items_dict = session_state.get("new_items_dict", {})
    saved_items = session_state.get("saved_items", set())

    # Clear any existing content and create new item cards
    items_html = ""

    for i, (item_id, item) in enumerate(new_items_dict.items(), 1):
        status_icon = "🔄" if item_id not in saved_items else "✅"
        status_text = "Not Saved" if item_id not in saved_items else "Saved"

        items_html += f"""
<div style="border: 1px solid #ddd; border-radius: 8px; padding: 15px; margin: 10px 0; background: #f9f9f9;">
    <div style="display: flex; align-items: center; justify-content: space-between;">
        <h4 style="margin: 0; color: #333;">Item {i}: {item.get("name", "Unnamed Item")}</h4>
        <div style="display: flex; align-items: center;">
            <span style="margin-right: 10px; font-weight: bold;">{status_icon} {status_text}</span>
        </div>
    </div>
    <div style="margin-top: 10px; display: grid; grid-template-columns: 2fr 1fr 1fr; gap: 10px; align-items: center;">
        <div><strong>Item Name:</strong> {item.get("name", "")}</div>
        <div><strong>Unit Price:</strong> €{item.get("unit_price", 0)}</div>
        <div><strong>Tax Rate:</strong> {item.get("tax_rate", 0)}%</div>
    </div>
</div>
"""

    return items_html


def schedule_reset_with_status(session_state: dict, status_message: str):
    """
    Unified function to schedule app reset and show status message.

    Args:
        session_state (dict): The current session state
        status_message (str): The message to show to the user

    Returns:
        gr.update: Update for confirmation_status component
    """
    # Schedule reset
    session_state["reset_scheduled"] = True

    # Return status update
    return gr.update(value=status_message, visible=True)


def handle_invoice_confirmation(session_state: dict):
    """
    Enhanced invoice confirmation that shows individual item cards for easy management.
    """
    new_items_dict = session_state["new_items_dict"]
    # Reset saved items tracking for new confirmation
    session_state["saved_items"] = set()

    # Check if there are new items to manage
    if new_items_dict:
        confirmation_html = f"""
## 🆕 New Items Detected!

    This invoice contains **{len(new_items_dict)} new items** that need to be added to your company database.

{create_new_items_interface(session_state)}

**💡 Tip:** Use the "Save All Items" button below to save all items at once, or contact support if you need to edit individual item values.

*Click "Save All Items" to save everything and automatically reset the form.*
"""

        # Create dropdown choices for individual item saving
        item_choices = []
        for i, (item_id, item) in enumerate(new_items_dict.items(), 1):
            item_name = item.get("name", f"Item {i}")
            item_choices.append(
                (
                    f"{i}. {item_name} (€{item.get('unit_price', 0)}, {item.get('tax_rate', 0)}%)",
                    item_id,
                )
            )

        return [
            gr.update(
                value=confirmation_html, visible=True
            ),  # Show confirmation status
            gr.update(visible=True),  # Show new items modal
            gr.update(visible=False),  # Hide the old table
            gr.update(choices=item_choices, value=None),  # Update dropdown choices
        ]
    else:
        # No new items, just confirm the invoice - schedule reset and show status
        status_message = """## ✅ Invoice Confirmed!

The invoice has been successfully processed and saved to the system.
**Thank you for using the invoice generation system!**

*The form will automatically reset in 5 seconds...*"""

        schedule_reset_with_status(session_state, status_message)

        return [
            gr.update(value=status_message, visible=True),  # Show confirmation status
            gr.update(visible=False),  # Hide new items modal
            gr.update(visible=False),  # Hide the old table
            gr.update(choices=[], value=None),  # Clear dropdown choices
        ]


def reset_app_state(session_state: dict):
    """
    Reset application state and clear input fields after a successful invoice confirmation.

    Args:
        session_state (dict): The current session state

    Returns:
        tuple: Updates for various UI components
    """
    global \
        current_invoice_json, \
        available_items_global, \
        new_items_global, \
        saved_items_global

    # Reset the thread to a new thread with the system prompt
    session_state["thread"] = Thread(
        sys_prompt=load_system_prompt("src/system_prompt.txt")
    )

    # Reset all state variables completely
    session_state["available_items"] = []
    session_state["new_items_dict"] = {}
    session_state["current_invoice_json"] = None
    session_state["saved_items"] = set()
    session_state["reset_scheduled"] = False

    # Also reset global variables for safety (even though they should not be used)
    current_invoice_json = None
    available_items_global = []
    new_items_global = {}
    saved_items_global = set()

    # Clear any other session state keys that might exist
    keys_to_remove = []
    for key in session_state.keys():
        if key not in [
            "thread",
            "available_items",
            "new_items_dict",
            "current_invoice_json",
            "saved_items",
            "reset_scheduled",
        ]:
            keys_to_remove.append(key)

    for key in keys_to_remove:
        del session_state[key]

    # Return updates for UI components
    return (
        gr.update(value=""),  # Clear input message
        gr.update(value=""),  # Clear follow-up message
        gr.update(visible=False),  # Hide results row
        gr.update(visible=False),  # Hide follow-up group
        gr.update(visible=False),  # Hide confirmation group
        gr.update(visible=False),  # Hide new items group
        gr.update(value=""),  # Clear reasoning output
        gr.update(value=""),  # Clear invoice output
        gr.update(value=[]),  # Clear new items DataFrame
        gr.update(value="", visible=False),  # Clear and hide confirmation status
        gr.update(visible=False),  # Hide confirm button
        gr.update(visible=False),  # Hide new items modal
    )


def check_for_reset(session_state: dict):
    """
    Check if a reset has been scheduled and execute it if needed.
    This function is called periodically by the interval component to implement the delayed reset.

    Args:
        session_state (dict): The current session state

    Returns:
        tuple: Updates for various UI components or no-op updates if no reset is scheduled
    """
    if session_state.get("reset_scheduled", False):
        logger.info("Executing scheduled app reset...")
        time.sleep(5)  # Wait for 5 seconds before resetting
        return reset_app_state(session_state)

    # Return no-op updates for all outputs if no reset is scheduled
    # This prevents the UI from changing when no reset is needed
    return (
        gr.update(),
        gr.update(),
        gr.update(),
        gr.update(),
        gr.update(),
        gr.update(),
        gr.update(),
        gr.update(),
        gr.update(),
        gr.update(),
        gr.update(),
        gr.update(),
    )


def save_item_by_id(company_id: str, item_id: str, session_state: dict):
    """
    Save a specific item by its ID and return status updates.

    Args:
        company_id (str): The company ID
        item_id (str): The ID of the item to save

    Returns:
        tuple: Status message, company info update, and updated confirmation status
    """
    new_items_dict = session_state["new_items_dict"]
    saved_items = session_state["saved_items"]

    try:
        # Check if item_id is provided
        if not item_id:
            return "❌ Please select an item to save", gr.update(), gr.update()

        # Check if already saved
        if item_id in saved_items:
            return "ℹ️ Item already saved to database", gr.update(), gr.update()

        # Get item data directly from global state
        if item_id not in new_items_dict:
            return "❌ Item not found", gr.update(), gr.update()

        item_data = new_items_dict[item_id].copy()

        # Save to database using the actual item data
        success = save_item_to_database(company_id, item_data)

        if success:
            # Mark as saved
            saved_items.add(item_id)

            # Check if all items are now saved
            all_items_saved = len(saved_items) == len(new_items_dict)

            # Schedule reset if all items have been saved
            if all_items_saved:
                # Use unified reset approach
                status_message = """## ✅ All items saved successfully!

All new items have been added to your company database.
**Thank you for using the invoice generation system!**

*The form will automatically reset in 5 seconds...*"""

                schedule_reset_with_status(session_state, status_message)

                return (
                    "✅ All items saved successfully!",
                    gr.update(value=display_company_info(company_id)),
                    gr.update(
                        value=status_message, visible=True
                    ),  # Show unified status
                    gr.update(visible=False),  # Hide modal
                )
            else:
                # Not all items saved yet, keep modal open
                # Refresh company info automatically
                company_info_updated = display_company_info(company_id)

                # Update the confirmation status to show current state
                updated_confirmation_html = f"""
## 🆕 New Items Management

This invoice contains **{len(new_items_dict)} new items** that need to be added to your company database.

{create_new_items_interface(session_state)}

**💡 Tip:** Select individual items from the dropdown to save them one by one, or use "Save All Items" to save everything at once.
"""

                status_message = (
                    f"✅ Successfully saved '{item_data.get('name')}' to database!"
                )

                return (
                    status_message,
                    gr.update(value=company_info_updated),
                    gr.update(value=updated_confirmation_html),
                    gr.update(),  # Keep modal visibility unchanged
                )
        else:
            return (
                f"❌ Failed to save '{item_data.get('name')}'",
                gr.update(),
                gr.update(),
            )

    except Exception as e:
        print(f"Error saving item {item_id}: {e}")
        return f"❌ Error: {str(e)}", gr.update(), gr.update()


def save_all_items(company_id: str, session_state: dict, new_items_table: list = None):
    """
    Save all unsaved items directly from new_items_global to the database.

    Args:
        company_id (str): The company ID
        new_items_table (list): Not used, kept for compatibility

    Returns:
        tuple: Status message, company info update, and updated confirmation status
    """
    new_items_dict = session_state["new_items_dict"]
    saved_items = session_state["saved_items"]

    try:
        print("new_items_dict:", new_items_dict)
        saved_count = 0
        failed_count = 0
        already_saved_count = 0

        # Work directly with new_items_global (source of truth)
        for item_id, item_data in new_items_dict.items():
            print("Processing item_id:", item_id, "item_data:", item_data)

            # Skip if already saved
            if item_id in saved_items:
                already_saved_count += 1
                continue

            # Save to database using actual item data
            success = save_item_to_database(company_id, item_data.copy())

            if success:
                saved_items.add(item_id)
                saved_count += 1
            else:
                failed_count += 1

        # Create status message
        status_parts = []
        if saved_count > 0:
            status_parts.append(f"✅ {saved_count} items saved")
        if already_saved_count > 0:
            status_parts.append(f"ℹ️ {already_saved_count} already saved")
        if failed_count > 0:
            status_parts.append(f"❌ {failed_count} failed")

        status_message = (
            " | ".join(status_parts) if status_parts else "No items to save"
        )

        # Check if all items are saved
        all_items_saved = (saved_count + already_saved_count) == len(
            new_items_dict
        ) and failed_count == 0

        # Schedule reset if all items were saved successfully
        if all_items_saved:
            # Use unified reset approach
            status_message = """## ✅ All items saved successfully!

All new items have been added to your company database.
**Thank you for using the invoice generation system!**

*The form will automatically reset in 5 seconds...*"""

            schedule_reset_with_status(session_state, status_message)

            return (
                "✅ All items saved successfully!",
                gr.update(value=display_company_info(company_id))
                if saved_count > 0
                else gr.update(),
                gr.update(value=status_message, visible=True),  # Show unified status
                gr.update(visible=False),  # Hide modal
            )
        else:
            # Not all items saved yet, keep modal open
            # Refresh company info automatically if any items were saved
            company_info_updated = gr.update()
            if saved_count > 0:
                company_info_updated = gr.update(value=display_company_info(company_id))

            # Update the confirmation status to show current state
            updated_confirmation_html = f"""
## 🆕 New Items Management

This invoice contains **{len(new_items_dict)} new items** that need to be added to your company database.

{create_new_items_interface(session_state)}

**💡 Tip:** Items are automatically saved to your company database. Company information will be refreshed automatically after saving.
"""

            return (
                status_message,
                company_info_updated,
                gr.update(value=updated_confirmation_html),
                gr.update(),  # Keep modal visibility unchanged
            )

    except Exception as e:
        print(f"Error saving all items: {e}")
        return f"❌ Error: {str(e)}", gr.update(), gr.update()


def send_follow_up_message(  # noqa: C901
    company_id: str, follow_up_message: str, session_state: dict
) -> tuple[str, str, gr.update, gr.update, gr.update]:
    """Send a follow-up message to the LLM and update reasoning and invoice.

    This function now includes the current state of items (both clear and unclear items
    with any user edits) to ensure the LLM has up-to-date context when processing
    the follow-up request.

    Args:
        company_id (str): The ID of the company.
        follow_up_message (str): The follow-up message from the user.

    Returns:
        Tuple[str, str, gr.update, gr.update, bool]: The updated reasoning, generated invoice,
        update objects for showing results and hiding loading message, and boolean indicating if invoice is valid.
    """
    thread = session_state["thread"]
    if not thread:
        return (
            "No initial invoice generation found. Please generate an invoice first.",
            "",
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=False),
        )

    # Get data from Redis
    company_data = get_data_from_redis(company_id)
    if not company_data:
        return (
            "Company does not exist",
            "",
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=False),
        )

    # ENHANCED FOLLOW-UP CONTEXT:
    # Include current state of items to ensure LLM has up-to-date information
    # This includes any edits the user made to unclear items via the DataFrame
    current_items_context = format_current_items_for_followup(session_state)

    # Combine the follow-up message with current invoice state
    user_input = f"{follow_up_message}\n{current_items_context}"

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
    reasoning_json = json.loads(reasoning)
    reasoning_markdown = format_reasoning_as_markdown(reasoning_json)

    # Check if the invoice is valid and update global variables
    is_valid_invoice = reasoning_json.get("is_valid_invoice")

    # PRESERVE USER EDITS: Handle global state updates carefully to maintain user edits
    # global available_items_global, new_items_global

    # Get new items from LLM response
    refreshed_available_items = reasoning_json.get("Analysis", {}).get(
        "available_items", []
    )
    refreshed_new_items = reasoning_json.get("Analysis", {}).get("new_items", [])

    # If LLM provides new analysis, update accordingly
    # But preserve any user edits to existing new items when possible
    if refreshed_available_items is not None:
        session_state["available_items"] = refreshed_available_items

    if refreshed_new_items is not None:
        # PRESERVE USER EDITS: Properly merge new items while preserving user edits
        refreshed_new_items_dict = assign_ids_to_new_items(refreshed_new_items)

        # If there are existing user edits, try to preserve them
        if session_state["new_items_dict"]:
            preserved_items = {}

            # For each new item from LLM response
            for new_id, new_item in refreshed_new_items_dict.items():
                # Check if there's a similar item in existing edits (match by name)
                matching_existing = None
                for existing_id, existing_item in session_state[
                    "new_items_dict"
                ].items():
                    if (
                        existing_item.get("name", "").lower().strip()
                        == new_item.get("name", "").lower().strip()
                        and existing_item.get("name") != "PLACEHOLDER"
                    ):
                        matching_existing = (existing_id, existing_item)
                        break

                if matching_existing:
                    # Preserve user edits, only update if field was PLACEHOLDER
                    existing_id, existing_item = matching_existing
                    merged_item = new_item.copy()
                    for field in ["name", "quantity", "unit_price", "tax_rate"]:
                        if existing_item.get(field) not in [
                            "PLACEHOLDER",
                            "",
                            None,
                        ] and existing_item.get(field) != new_item.get(field):
                            # User has edited this field, preserve their edit
                            merged_item[field] = existing_item[field]
                    preserved_items[new_id] = merged_item
                else:
                    # New item not found in existing edits, use as-is
                    preserved_items[new_id] = new_item

            session_state["new_items_dict"] = preserved_items
        else:
            # No existing edits to preserve
            session_state["new_items_dict"] = refreshed_new_items_dict
    else:
        # If no new items provided, keep existing ones (preserving user edits)
        pass

    # Generate updated invoice HTML with preserved user edits and recalculated totals
    # We need to regenerate with current global state (including preserved edits)
    invoice_data, invoice_html = get_invoice_html(
        invoice, session_state["available_items"], session_state["new_items_dict"]
    )

    # Update the current invoice JSON with recalculated values
    session_state["current_invoice_json"] = json.dumps(invoice_data)

    has_new_items = reasoning_json.get("has_new_items", False)

    # Determine if invoice is completed (no new items or all new items filled)
    # Use the current global new items state (which includes any user edits)
    invoice_completed = is_invoice_completed(session_state["new_items_dict"])

    # Show confirm button only if invoice is valid AND completed
    show_confirm_button = is_valid_invoice and invoice_completed

    new_items_df = None
    if has_new_items:
        # Extract new items for the DataFrame
        new_items_df = extract_new_items_for_df(reasoning_json)

    # Return updates to show results and hide loading
    # The function now maintains global state consistency and includes user edits from DataFrame
    return (
        reasoning_markdown,  # Updated reasoning output
        invoice_html,  # Updated invoice HTML with current state
        gr.update(visible=True),  # Show results row
        gr.update(visible=False),  # Hide loading message
        gr.update(
            visible=show_confirm_button
        ),  # Show confirmation group only if valid AND completed
        gr.update(visible=has_new_items),  # Show new items group if there are new items
        new_items_df,  # Populate the DataFrame with new items
    )


def format_current_items_for_followup(session_state: dict) -> str:
    """
    Format the current state of available and new items for follow-up messages.

    This ensures that when users send follow-up messages, the LLM has access to:
    1. All available items from the company database
    2. Current state of new items (including any user edits made in the DataFrame)

    Returns:
        str: Formatted string containing current item states for LLM context
    """
    available_items = session_state["available_items"]
    new_items_dict = session_state["new_items_dict"]

    context = "\n=== CURRENT INVOICE STATE ===\n"

    # Add available items that exist in company database
    if available_items:
        context += "\nAVAILABLE ITEMS (From company database):\n"
        for idx, item in enumerate(available_items, 1):
            context += f"{idx}. {item.get('name', 'N/A')} - Qty: {item.get('quantity', 'N/A')}, "
            context += f"Unit Price: €{item.get('unit_price', 0):.2f}, "
            context += f"Tax Rate: {item.get('tax_rate', 0)}%, "
            context += f"Total: €{item.get('total_price', 0):.2f}\n"

    # Add new items with their current state (including user edits)
    if new_items_dict:
        context += (
            "\nNEW ITEMS TO BE ADDED TO DATABASE (Current state after user edits):\n"
        )
        for idx, (item_id, item) in enumerate(new_items_dict.items(), 1):
            context += f"{idx}. {item.get('name', 'PLACEHOLDER')} - "
            context += f"Qty: {item.get('quantity', 'PLACEHOLDER')}, "
            context += f"Unit Price: {item.get('unit_price', 'PLACEHOLDER')}, "
            context += f"Tax Rate: {item.get('tax_rate', 'PLACEHOLDER')}\n"

            # Indicate which fields still need user input
            placeholder_fields = []
            for field in ["name", "quantity", "unit_price", "tax_rate"]:
                if item.get(field) in ["PLACEHOLDER", "", None]:
                    placeholder_fields.append(field)

            if placeholder_fields:
                context += f"   → Still needs: {', '.join(placeholder_fields)}\n"
            else:
                context += (
                    "   → All fields completed by user (ready to add to database)\n"
                )

    if not available_items and not new_items_dict:
        context += "\nNo items currently in the invoice.\n"

    context += "\n=== END CURRENT STATE ===\n"

    return context


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
            # print("item:", item)
            html += "<tr>"
            html += f"<td>{item.get('name', '')}</td>"
            html += f"<td>{item.get('quantity', '')}</td>"
            unit_price = (
                f"€{item.get('unit_price', 0):.2f}"
                if isinstance(item.get("unit_price"), float)
                else item.get("unit_price")
            )
            html += f"<td>{unit_price}</td>"
            tax_rate = (
                f"{item.get('tax_rate', 0):.2f}"
                if isinstance(item.get("tax_rate"), float)
                else item.get("tax_rate")
            )
            total = (
                f"€{item.get('total_price', 0):.2f}"
                if isinstance(item.get("total_price"), float)
                else item.get("total_price")
            )
            html += f"<td>{tax_rate}</td>"
            html += f"<td>{total}</td>"
            html += "</tr>"
        html += "</tbody></table>"

        # Totals
        html += '<table class="invoice-total">'
        subtotal = (
            f"€{invoice_data.get('subtotal', 0):.2f}"
            if isinstance(invoice_data.get("subtotal"), float)
            else invoice_data.get("subtotal")
        )
        tax = (
            f"€{invoice_data.get('tax', 0):.2f}"
            if isinstance(invoice_data.get("tax"), float)
            else invoice_data.get("tax")
        )
        total_due = (
            f"€{invoice_data.get('total_due', 0):.2f}"
            if isinstance(invoice_data.get("total_due"), float)
            else invoice_data.get("total_due")
        )
        html += f"<tr><td>Subtotal:</td><td>{subtotal}</td></tr>"
        html += f"<tr><td>Tax:</td><td>{tax}</td></tr>"
        html += f'<tr class="total-row"><td>Total:</td><td>{total_due}</td></tr>'
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


def extract_new_items_for_df(reasoning_json: dict) -> list:
    """Extract new items from the reasoning JSON and format them for the DataFrame.

    Args:
        reasoning_json (dict): The parsed reasoning JSON.

    Returns:
        list: List of new items formatted for the DataFrame for user editing.
    """

    new_items = reasoning_json.get("Analysis").get("new_items", [])
    new_items = [
        [
            item.get("name", ""),
            item.get("quantity", ""),
            item.get("unit_price", ""),
            item.get("tax_rate", ""),
        ]
        for item in new_items
    ]
    # print("new_items:", new_items)
    return new_items


def update_invoice_with_edited_items(
    new_items_df: list, session_state: dict
) -> tuple[str, gr.update]:
    """Update the invoice with the edited new items and return completion status.

    Args:
        new_items_df (list): The edited new items from the DataFrame.
        invoice_json_str (str): The current invoice JSON string.

    Returns:
        tuple[str, gr.update]: The updated invoice HTML and confirmation group visibility update.
    """
    try:
        # global current_invoice_json, available_items_global, new_items_global
        invoice_json_str = session_state["current_invoice_json"]
        available_items = session_state["available_items"]
        new_items_dict = session_state["new_items_dict"]

        # Map DataFrame rows back to IDs using the order of new_items_global keys
        keys = list(new_items_dict.keys())
        for idx, row in new_items_df.iterrows():
            # print(row)
            id = keys[idx]
            name, quantity, unit_price, tax_rate = row
            new_items_dict[id].update(
                {
                    "name": name,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "tax_rate": tax_rate,
                }
            )
        print("new_items_dict:", new_items_dict)
        invoice_data, invoice_html = get_invoice_html(
            invoice_json_str, available_items, new_items_dict
        )
        session_state["current_invoice_json"] = json.dumps(invoice_data)

        # Check if invoice is now completed and should show confirm button
        invoice_completed = is_invoice_completed(new_items_dict)
        # Assume invoice is valid since we're editing existing new items
        show_confirm_button = invoice_completed

        return invoice_html, gr.update(visible=show_confirm_button)
    except Exception as e:
        print(f"Error updating invoice: {e}")
        return f"<p>Error updating invoice: {str(e)}</p>", gr.update(visible=False)


def is_invoice_completed(new_items_dict: dict) -> bool:
    """
    Determine if an invoice is completed (has no new items or all new items are filled).

    An invoice is considered completed when:
    1. There are no new items, OR
    2. All new items have been filled with valid values (no PLACEHOLDER values)

    Args:
        new_items_dict (dict): Dictionary of new items with their IDs as keys

    Returns:
        bool: True if invoice is completed, False otherwise
    """
    # If there are no new items, the invoice is completed
    if not new_items_dict:
        return True

    # Check if all new items have valid values (no PLACEHOLDER)
    for item in new_items_dict.values():
        # Check if any required field contains PLACEHOLDER or is empty
        required_fields = ["name", "quantity", "unit_price", "tax_rate"]
        for field in required_fields:
            value = item.get(field, "")
            if value == "PLACEHOLDER" or value == "" or value is None:
                return False
            # Additional validation for numeric fields
            if field in ["quantity", "unit_price", "tax_rate"]:
                try:
                    float(value) if field != "quantity" else int(value)
                except (ValueError, TypeError):
                    return False

    return True


def handle_modal_close(session_state: dict):
    """
    Close the modal, keep confirm button visible, show status message, and schedule reset

    Args:
        session_state (dict): The current session state

    Returns:
        list: Updates for visibility of modal, table, item selector, and confirmation status
    """
    status_message = """## ✅ Invoice process completed!

New items management closed. The invoice has been processed.
**Thank you for using the invoice generation system!**

*The form will automatically reset in 5 seconds...*"""

    # Schedule reset and get status update
    schedule_reset_with_status(session_state, status_message)

    # Close modal components and show status
    return [
        gr.update(visible=False),  # Hide modal
        gr.update(visible=False),  # Hide table
        gr.update(choices=[], value=None),  # Clear selector
        gr.update(value=status_message, visible=True),  # Show status message
    ]


with gr.Blocks(theme=gr.themes.Default(primary_hue="blue")) as demo:
    # Initialize session state
    session_state = gr.State(
        {"thread": Thread(sys_prompt=load_system_prompt("src/system_prompt.txt"))}
    )
    logger.info(f"Session state: {session_state}")

    gr.Markdown(f"# Invoice Generation App - v {get_project_version()}")

    # Create a timer for periodic reset checking (every 5 seconds)
    reset_timer = gr.Timer(5)

    # First row: Input data and company information
    with gr.Row():
        # Left column: Input controls
        with gr.Column(scale=1):
            with gr.Group():
                gr.Markdown("### Input Data")
                company_id = gr.Textbox(
                    label="Company ID", placeholder="Enter company ID...", value="2"
                )
                company_status = gr.Markdown("", elem_id="company-status")
                input_message = gr.Textbox(
                    label="Invoice Request",
                    placeholder="Example: Create an invoice for Global Corp for 2 AI Software Licenses and 1 Cloud Storage Subscription",
                    lines=3,
                    value="sell 2 watches and 3 phones to chic",
                )
                generate_button = gr.Button("Generate Invoice", variant="primary")

                with gr.Group(visible=False) as follow_up_group:
                    follow_up_message = gr.Textbox(
                        label="Follow-up Message",
                        placeholder="Need changes? Describe them here...",
                        lines=2,
                    )
                    follow_up_button = gr.Button(
                        "Send Follow-up", variant="secondary", size="lg"
                    )

                # Group for confirmation button and status
                with gr.Group(visible=False) as confirmation_group:
                    confirm_button = gr.Button(
                        "✓ Confirm & Save Invoice",
                        variant="primary",
                        size="lg",
                        elem_id="confirm-invoice-button",
                    )
                    confirmation_status = gr.Markdown(visible=False)

        # Right column: Company information
        with gr.Column(scale=1):
            gr.Markdown("### Company Information")
            company_info = gr.Markdown(label="")

    # New Items Management Section with individual item cards
    with gr.Group(visible=False) as new_items_modal:
        gr.Markdown("### 📦 New Items Management")
        gr.Markdown(
            "The following items don't exist in your company database. Edit the values and click the save button for each item:"
        )

        # Container for individual item cards - will be populated dynamically
        new_items_container = gr.Column()

        # Keep the old table hidden for compatibility (not used in new interface)
        new_items_management_table = gr.DataFrame(
            headers=["Item Name", "Unit Price", "Tax Rate", "Status"],
            datatype=["str", "number", "number", "str"],
            col_count=(4, "fixed"),
            interactive=True,
            visible=False,
        )

        gr.Markdown("---")

        # Individual item save section
        with gr.Row():
            with gr.Column(scale=2):
                gr.Markdown("**💾 Save Individual Item:**")
                with gr.Row():
                    item_selector = gr.Dropdown(
                        label="Select Item to Save",
                        choices=[],
                        interactive=True,
                        scale=2,
                    )
                    save_individual_button = gr.Button(
                        "Save Selected", variant="secondary", size="sm", scale=1
                    )
            with gr.Column(scale=1):
                gr.Markdown("**💾 Save All:**")
                save_all_button = gr.Button(
                    "Save All Items", variant="primary", size="lg"
                )

        with gr.Row():
            close_modal_button = gr.Button("Close", variant="secondary", size="lg")

        # Status message for save operations
        save_status = gr.Markdown(value="", visible=True)

    with gr.Row():
        gr.Markdown("---")

    # Loading message
    with gr.Row() as loading_message:
        gr.Markdown("### Calling LLM now... Please wait.", elem_id="loading-message")
    loading_message.visible = False

    # Results row: Invoice preview and reasoning (initially hidden)
    with gr.Row(equal_height=True, visible=False) as results_row:
        with gr.Column(scale=1):
            # Add editable dataframe for new items that need to be added to database (initially hidden)
            with gr.Group(visible=False) as new_items_group:
                gr.Markdown("### Edit New Items (To Be Added to Database)")
                new_items_df = gr.DataFrame(
                    headers=[
                        "Item Name",
                        "Quantity",
                        "Unit Price(Tax included)",
                        "Tax Rate",
                    ],
                    datatype=["str", "number", "number", "number"],
                    col_count=(4, "fixed"),
                    interactive=True,
                )
                apply_edits_button = gr.Button(
                    "Apply Changes & Preview", variant="secondary", size="sm"
                )

            gr.Markdown("### Invoice Preview")
            invoice_output = gr.HTML()  # Using HTML component for rich invoice display
        with gr.Column(scale=1):
            gr.Markdown("### Reasoning")
            reasoning_output = gr.Markdown(label="")

    # Connect the timer to check for scheduled resets every 5 seconds
    reset_timer.tick(
        fn=check_for_reset,
        inputs=[session_state],
        outputs=[
            input_message,  # Clear input message
            follow_up_message,  # Clear follow-up message
            results_row,  # Hide results row
            follow_up_group,  # Hide follow-up group
            confirmation_group,  # Hide confirmation group
            new_items_group,  # Hide new items group
            reasoning_output,  # Clear reasoning output
            invoice_output,  # Clear invoice output
            new_items_df,  # Clear new items DataFrame
            confirmation_status,  # Hide confirmation status
            confirm_button,  # Hide confirm button
            new_items_modal,  # Hide new items modal
        ],
        show_progress=False,
    )

    company_id.change(fn=display_company_info, inputs=company_id, outputs=company_info)

    # First click handler - show loading message, hide results
    generate_button.click(
        fn=lambda: (
            gr.update(visible=True),
            gr.update(visible=False),
            gr.update(visible=False),
        ),
        inputs=[],
        outputs=[loading_message, results_row, follow_up_group],
    )

    # Second click handler - process invoice and update UI
    generate_button.click(
        fn=lambda company_id, input_message, session_state: get_reasoning_and_invoice(
            company_id, input_message, session_state
        ),
        inputs=[company_id, input_message, session_state],
        outputs=[
            reasoning_output,
            invoice_output,
            results_row,
            loading_message,
            follow_up_group,
            confirmation_group,
            new_items_group,
            new_items_df,
        ],
    )

    # Follow-up button - first show loading message, hide results and confirmation
    follow_up_button.click(
        fn=lambda: (
            gr.update(visible=True),
            gr.update(visible=False),
            gr.update(visible=False),
        ),
        inputs=[],
        outputs=[loading_message, results_row, confirmation_group],
    )

    # Follow-up button - process update and show results
    follow_up_button.click(
        fn=send_follow_up_message,
        inputs=[company_id, follow_up_message, session_state],
        outputs=[
            reasoning_output,
            invoice_output,
            results_row,
            loading_message,
            confirmation_group,
            new_items_group,
            new_items_df,
        ],
    )

    # Apply edits button - update invoice with edited new items
    apply_edits_button.click(
        fn=lambda df, session_state: update_invoice_with_edited_items(
            df, session_state
        ),
        inputs=[new_items_df, session_state],
        outputs=[
            invoice_output,
            confirmation_group,
        ],  # Now returns both invoice HTML and confirmation visibility
    )

    # Real-time update: whenever the DataFrame changes, update the invoice preview and confirm button visibility
    new_items_df.change(
        fn=lambda df, session_state: update_invoice_with_edited_items(
            df, session_state
        ),
        inputs=[new_items_df, session_state],
        outputs=[
            invoice_output,
            confirmation_group,
        ],  # Now returns both invoice HTML and confirmation visibility
        show_progress=True,
    )

    # Enhanced confirmation button handler with modal support
    confirm_button.click(
        fn=handle_invoice_confirmation,
        inputs=[session_state],
        outputs=[
            confirmation_status,
            new_items_modal,
            new_items_management_table,
            item_selector,
        ],
    )

    # New items management event handlers

    # Individual item save handler (with automatic company info refresh)
    save_individual_button.click(
        fn=save_item_by_id,
        inputs=[company_id, item_selector, session_state],
        outputs=[save_status, company_info, confirmation_status, new_items_modal],
    )

    # Save all items handler (with automatic company info refresh and status update)
    save_all_button.click(
        fn=save_all_items,
        inputs=[company_id, session_state],
        outputs=[save_status, company_info, confirmation_status, new_items_modal],
    )

    # Close new items management section handler
    close_modal_button.click(
        fn=handle_modal_close,
        inputs=[session_state],
        outputs=[
            new_items_modal,
            new_items_management_table,
            item_selector,
            confirmation_status,
        ],
    )

if __name__ == "__main__":
    demo.launch(share=False, debug=True, server_port=8002, server_name="0.0.0.0")
