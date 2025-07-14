from typing import Literal

from pydantic import BaseModel, Field


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


PLACEHOLDER = Literal["PLACEHOLDER"]


class UnclearInvoiceItem(InvoiceItem):
    """
    Represents an unclear item or service in an invoice, with extra attribute as placeholder.

    Attributes:
        name (str): Description of the item.
        quantity (int): Quantity of the item.
        unit_price (float): Unit price of the item.
        tax_rate (float): Tax rate for the item.
        total_price (float): Total price for the item.
    """

    # PLACEHOLDER = "PLACEHOLDER"

    name: str | PLACEHOLDER = Field(
        default="PLACEHOLDER",
        title="Description of the item",
        example="Web Development",
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
    """

    analysis: str = Field(..., title="Analysis of the invoice generation task")
    clear_items: list[InvoiceItem] = Field(
        ..., title="List of items with clear and complete information for the invoice"
    )
    unclear_items: list[UnclearInvoiceItem] = Field(
        ..., title="List of items with incomplete or unclear information"
    )


class Reasoning(BaseModel):
    """
    Represents the reasoning output for an invoice generation task.
    """

    Analysis: ReasoningAnalysis = Field(
        ..., title="Analysis of the invoice generation task"
    )
    is_valid_invoice: bool = Field(
        ..., title="Boolean indicating if input is valid for creating an invoice"
    )
    is_completed_items: bool = Field(
        ..., title="Boolean indicating if all item information is clear and complete"
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
