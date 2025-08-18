# CSS styles for invoice formatting and custom button styling
INVOICE_STYLES = """
<style>
/* Simple styling for confirmation button */
#confirm-invoice-button {
    background-color: #28a745 !important;
    border-color: #28a745 !important;
    font-weight: bold !important;
    transition: all 0.2s ease !important;
}

#confirm-invoice-button:hover {
    background-color: #218838 !important;
    border-color: #1e7e34 !important;
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15) !important;
}

/* Invoice container styling */
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
