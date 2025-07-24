from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class InvoiceItem(BaseModel):
    """
    Represents an item or service in an invoice.

    Attributes:
        name (str): Description of the item.
        quantity (int): Quantity of the item.
        unit_price (float): Unit price of the item.
        tax_rate (float): Tax rate for the item.
        total_price (float): Total price for the item.
    """

    name: str = Field(..., title="Description of the item", example="Web Development")
    quantity: int = Field(..., title="Quantity of the item", example=50)
    unit_price: float | str = Field(..., title="Unit price of the item", example=50.0)
    tax_rate: float | str = Field(..., title="Tax rate for the item", example=18)
    total_price: float | str = Field(
        ..., title="Total price for the item", example=2500.0
    )

    model_config = ConfigDict(extra="ignore")


PLACEHOLDER = Literal["PLACEHOLDER"]


class NewInvoiceItem(InvoiceItem):
    """
    Represents a new item or service that doesn't exist in the company database yet.
    This item will need to be added to the database after user confirmation.
    Some fields may have PLACEHOLDER values that need to be filled by the user.

    Attributes:
        name (str): Description of the item.
        quantity (int): Quantity of the item.
        unit_price (float | PLACEHOLDER): Unit price of the item (may need user input).
        tax_rate (float | PLACEHOLDER): Tax rate for the item (may need user input).
        total_price (float | PLACEHOLDER): Total price for the item.
        is_new_item (bool): Always True to indicate this is a new item for the database.
    """

    name: str | PLACEHOLDER = Field(
        default="PLACEHOLDER",
        title="Description of the item",
        example="Custom Software Development",
    )
    quantity: int | PLACEHOLDER = Field(
        default="PLACEHOLDER", title="Quantity of the item", example=50
    )
    unit_price: float | PLACEHOLDER = Field(
        default="PLACEHOLDER", title="Unit price of the item", example=50.0
    )
    tax_rate: float | PLACEHOLDER = Field(
        default="PLACEHOLDER", title="Tax rate for the item", example=18
    )
    total_price: float | PLACEHOLDER = Field(
        default="PLACEHOLDER", title="Total price for the item", example=2500.0
    )
    is_new_item: bool = Field(
        default=True,
        title="Indicates this is a new item to be added to database",
        description="Always True for new items that don't exist in company database",
    )


class Invoice(BaseModel):
    """
    Represents an invoice.

    Attributes:
        business_name (str): Name of the business.
        business_address (str): Address of the business.
        business_contact (str): Contact information of the business.
        invoice_number (str): Unique invoice identifier.
        invoice_date (str): Date when the invoice is issued.
        due_date (str): Payment deadline.
        customer_name (str): Name of the customer.
        customer_address (str): Address of the customer.
        customer_contact (str): Contact information of the customer.
        items (List[InvoiceItem]): List of items or services billed.
        subtotal (float): Subtotal amount.
        tax (float): Tax amount.
        total_due (float): Total amount due.
        payment_terms (str): Payment terms and accepted methods.
        notes (Optional[str]): Additional notes or messages.
    """

    business_name: str = Field(
        ..., title="Name of the business", example="ABC Solutions"
    )
    business_address: str = Field(
        ..., title="Address of the business", example="123 Business Street, Cityville"
    )
    business_contact: str = Field(
        ...,
        title="Contact information of the business",
        example="Phone: +1-234-567-890 | Email: contact@abcsolutions.com",
    )
    invoice_number: str = Field(
        ..., title="Unique invoice identifier", example="INV-2025001"
    )
    invoice_date: str = Field(
        ..., title="Date when the invoice is issued", example="2025-02-14"
    )
    due_date: str = Field(..., title="Payment deadline", example="2025-02-28")
    customer_name: str = Field(
        ..., title="Name of the customer", example="XYZ Enterprises"
    )
    customer_address: str = Field(
        ..., title="Address of the customer", example="456 Client Avenue, Townsville"
    )
    customer_contact: str = Field(
        ...,
        title="Contact information of the customer",
        example="Email: billing@xyzenterprises.com",
    )
    items: list[InvoiceItem] = Field(..., title="List of items or services billed")
    subtotal: float | str = Field(..., title="Subtotal amount", example=2740.0)
    tax: float | str = Field(..., title="Tax amount", example=274.0)
    total_due: float | str = Field(..., title="Total amount due", example=3014.0)
    payment_terms: str = Field(
        ...,
        title="Payment terms and methods",
        example="Net 14 days | Accepted methods: Bank Transfer, PayPal",
    )
    notes: str | None = Field(
        None,
        title="Additional notes or messages",
        example="Thank you for your business!",
    )


class NotInvoiced(BaseModel):
    """
    Represents the output when an invoice cannot be generated.

    Attributes:
        reason (str): Reason for not generating the invoice.
    """

    output: str = Field(..., title="output when for not generating the invoice")


class ReasoningAnalysis(BaseModel):
    """
    Represents the analysis output for an invoice generation task.
    Now focuses on identifying available items vs new items that need to be added to database.
    """

    analysis: str = Field(..., title="Analysis of the invoice generation task")
    available_items: list[InvoiceItem] = Field(
        ...,
        title="List of items that already exist in the company database with complete information",
        description="These items have known pricing and details from the database",
    )
    new_items: list[NewInvoiceItem] = Field(
        ...,
        title="List of new items that don't exist in the company database",
        description="These items need to be added to the database and may require user input for missing details",
    )


class Reasoning(BaseModel):
    """
    Represents the reasoning output for an invoice generation task.
    Updated to work with available vs new items concept.
    """

    Analysis: ReasoningAnalysis = Field(
        ..., title="Analysis of the invoice generation task"
    )
    is_valid_invoice: bool = Field(
        ..., title="Boolean indicating if input is valid for creating an invoice"
    )
    has_new_items: bool = Field(
        ...,
        title="Boolean indicating if there are new items that need to be added to database",
        description="True if any items don't exist in company database and need user review",
    )
    decision_analysis: str = Field(
        ..., title="Analysis explaining the decision whether to create the invoice"
    )
    Calculations: str = Field(
        ...,
        title="Calculations performed for the invoice",
        description="Only included when is_valid_invoice is True",
    )


class LLMResponse(BaseModel):
    """
    Represents the response from the LLM.

    Attributes:
        reasoning (Reasoning): The reasoning output.
        invoice (Invoice | NotInvoiced): The generated invoice or reason for not generating the invoice.
    """

    reasoning: Reasoning = Field(..., title="The reasoning output")
    invoice: Invoice | NotInvoiced = Field(
        ..., title="The generated invoice or reason for not generating the invoice"
    )
