import json
import os
from typing import Any

import redis


def load_data(file_path: str) -> dict[str, Any]:
    """Load data from a JSON file.

    Args:
        file_path (str): Path to the JSON file.

    Returns:
        dict: Data loaded from the JSON file.
    """
    with open(file_path) as file:
        return json.load(file)


def main():
    """Main function to import data into Redis using Pipeline."""
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", 6379))
    redis_password = os.getenv("REDIS_PASSWORD", "")
    data_file_path = os.getenv("DATA_FILE_PATH", "/src/redis_importer/mock_data.json")

    try:
        client = redis.StrictRedis(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            decode_responses=True,
        )
        client.ping()
        print("Connected to Redis")

        # Load data from JSON file
        data = load_data(data_file_path)

        # Use pipeline to import data into Redis
        pipeline = client.pipeline()
        for company_id, company_data in data.items():
            for key, value in company_data.items():
                if isinstance(value, list):
                    value = json.dumps(value)  # Convert lists to JSON strings
                pipeline.hset(f"company:{company_id}", key, value)
            print(f"Prepared import for company {company_id}: {company_data}")

        # Execute pipeline
        pipeline.execute()
        print("Data import completed.")

    except redis.ConnectionError as e:
        print(f"Failed to connect to Redis: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
