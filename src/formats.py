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


def format_items_as_markdown_table(items: list) -> str:
    """Format a list of invoice items as a markdown table.

    Args:
        items (list): List of invoice items with name, quantity, unit_price, etc.

    Returns:
        str: Formatted markdown table of items.
    """
    if not items:
        return "No relevant items found."

    # Create table header
    table = "| Item Name | Quantity | Unit Price | Tax Rate | Total |\n"
    table += "|----------|----------|------------|----------|-------|\n"

    # Add each item as a row
    for item in items:
        name = item.get("name", "")
        quantity = item.get("quantity", "")
        unit_price = (
            f"€{item.get('unit_price', 0):.2f}"
            if isinstance(item.get("unit_price"), float)
            else item.get("unit_price")
        )
        tax_rate = (
            f"€{item.get('tax_rate', 0):.2f}"
            if isinstance(item.get("tax_rate"), float)
            else item.get("tax_rate")
        )
        total = (
            f"€{item.get('total_price', 0):.2f}"
            if isinstance(item.get("total_price"), float)
            else item.get("total_price")
        )
        table += f"| {name} | {quantity} | {unit_price} | {tax_rate} | {total} |\n"

    return table


def format_reasoning_as_markdown(reasoning: dict, header: str = "") -> str:  # noqa: C901
    """Format the reasoning dictionary as Markdown with an optional header.
    Handles nested structure with Analysis containing analysis text and relevant_items.
    Also handles the refactored decision structure with is_valid_invoice and decision_analysis.

    Args:
        reasoning (dict): The reasoning dictionary.
        header (str): The header to be displayed at the beginning.

    Returns:
        str: The formatted reasoning in Markdown.
    """
    markdown = f"### {header}\n\n" if header else ""

    # Process each key in the reasoning dictionary
    for key, value in reasoning.items():
        # Special handling for Analysis if it has the nested structure
        if key == "Analysis" and isinstance(value, dict):
            markdown += "#### Analysis\n"

            # Add the analysis text
            if "analysis" in value:
                markdown += value["analysis"] + "\n\n"

            # Add available items table (items from company database)
            if "available_items" in value and value["available_items"]:
                markdown += "**Available Items (From Company Database):**\n\n"
                markdown += (
                    format_items_as_markdown_table(value["available_items"]) + "\n\n"
                )

            # Add new items table (items to be added to database)
            if "new_items" in value and value["new_items"]:
                markdown += "**New Items (To Be Added to Database):**\n\n"
                markdown += format_items_as_markdown_table(value["new_items"]) + "\n\n"

        # Special handling for is_valid_invoice (boolean)
        elif key == "is_valid_invoice":
            valid_status = "✅ Valid" if value else "❌ Invalid"
            markdown += f"#### Invoice Request Status\n{valid_status}\n\n"

        # Special handling for has_new_items (boolean)
        elif key == "has_new_items":
            items_status = (
                "🆕 Has New Items" if value else "✅ All Items Available in Database"
            )
            markdown += f"#### Item Status\n{items_status}\n\n"

        # Special handling for decision_analysis
        elif key == "decision_analysis":
            markdown += f"#### Decision Explanation\n{value}\n\n"

        # Special handling for Calculations (only shown if is_valid_invoice is true)
        elif key == "Calculations":
            if reasoning.get("is_valid_invoice", False):
                markdown += f"#### Calculations\n{value}\n\n"

        # Standard handling for any other fields
        else:
            markdown += f"#### {key}\n{value}\n\n"

    return markdown
