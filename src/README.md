# AI-Powered Invoice Generation

## 1. Overview

This project is a smart assistant designed to automate and streamline the invoice creation process. It leverages a Large Language Model (LLM) to understand user requests in natural language and generate professional, accurate invoices. The application is built with a user-friendly interface that allows for easy interaction, real-time previews, and management of company data like customers and products.

## 2. Key Features

*   **Natural Language Processing:** Users can request invoices using simple, everyday language (e.g., "Send an invoice to Customer X for 5 hours of consulting").
*   **Automatic Data Retrieval:** The system automatically fetches customer information and item prices from a Redis database, ensuring accuracy and consistency.
*   **Smart Item Handling:** It can distinguish between existing items in the database and new items. For new items, it prompts the user for necessary details and saves them for future use.
*   **Interactive User Interface:** A web-based UI built with Gradio allows users to generate invoices, see a real-time preview, and make corrections.
*   **Follow-up Questions:** Users can ask follow-up questions or request changes to the generated invoice in a conversational manner.
*   **Confirmation and Data Persistence:** Before finalizing, users can review and confirm the invoice. New items are saved back to the database, making the system smarter over time.

## 3. Tech Stack

*   **Backend:** Python
*   **AI/LLM:** Azure OpenAI Service (GPT-4)
*   **Web UI:** Gradio
*   **Database:** Redis (for storing company, customer, and product data)
*   **Containerization:** Docker & Docker Compose

## 4. High-Level Architecture

The application follows a simple, yet effective architecture:

```
+-----------------+      +-------------------+      +-----------------+
|                 |      |                   |      |                 |
|   Gradio Web    |----->|    Python Backend   |----->|   Azure OpenAI  |
|      UI         |      |   (LLM Logic)     |      |   Service (LLM) |
|                 |      |                   |      |                 |
+-----------------+      +---------+---------+      +-----------------+
                                   |
                                   |
                                   v
                         +---------+---------+
                         |                   |
                         |   Redis Database  |
                         | (Company Data)    |
                         |                   |
                         +-------------------+
```

1.  The **Gradio UI** provides the user interface for interacting with the system.
2.  The **Python Backend** contains the core application logic. It receives user input, communicates with the LLM, and processes the data.
3.  The **Azure OpenAI Service** interprets the user's natural language request and generates the invoice structure.
4.  The **Redis Database** stores all persistent data, such as company details, customer lists, and product information.

## 5. How to Run for a Live Demonstration

For the presentation, the easiest and most reliable way to run the application is by using Docker. This ensures that the application and its database run in a consistent, isolated environment.

### Prerequisites

*   You must have **Docker** and **Docker Compose** installed on your machine.

### Step 1: Create the Environment File

The application requires API keys and other configuration details to be stored in an environment file.

1.  In the root directory of the project (`LLM-invoice-generation`), create a file named `.env`.
2.  Add the following content to the `.env` file, replacing the placeholder values with your actual credentials:

```env
# Azure OpenAI Credentials
AZURE_OPENAI_API_KEY="YOUR_AZURE_OPENAI_API_KEY"
AZURE_OPENAI_ENDPOINT="YOUR_AZURE_OPENAI_ENDPOINT"
AZURE_OPENAI_API_VERSION="YOUR_API_VERSION"

# Redis Configuration
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=password

# Path to Mock Data (for Docker)
DATA_FILE_PATH=/app/src/redis_importer/mock_data.json
```

### Step 2: Run with Docker Compose

1.  Open a terminal in the root directory of the project (`LLM-invoice-generation`).
2.  Run the following command:

    ```bash
    docker-compose up --build
    ```

3.  This command will:
    *   Build the Docker images for the application and the data importer.
    *   Start the Gradio web application.
    *   Start a Redis database instance.
    *   Run a one-time script to import the mock company data into the Redis database.

4.  Once the build is complete and the containers are running, you will see log output in your terminal. Open your web browser and navigate to:

    **http://localhost:8002**

You can now proceed with the live demonstration as outlined in the presentation.

### Step 3: Shutting Down

To stop the application and the database, press `Ctrl + C` in the terminal where `docker-compose` is running.

## 6. Project Structure (`src_state`)

The `src_state` directory contains the core logic for the application:

```
src_state/
├── chat_llm.py             # Handles communication with the OpenAI LLM.
├── gradio_app.py           # Defines the Gradio user interface and event handlers.
├── schema.py               # Defines the data structures (Pydantic models) for invoices and LLM responses.
├── formats.py              # Contains functions for formatting data into Markdown or HTML.
├── utils.py                # Utility functions, such as loading prompts.
├── system_prompt.txt       # The main instruction prompt for the LLM.
├── redis_importer/         # Contains scripts and data for populating the Redis database.
│   ├── import_data.py      # Script to import mock data.
│   └── mock_data.json      # Mock company, customer, and product data.
└── ...
```
