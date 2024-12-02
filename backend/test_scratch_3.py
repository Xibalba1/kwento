from google.cloud import storage
from google.oauth2 import service_account

# Constants
SERVICE_ACCOUNT_FILE = "/Users/ik/repos/kwento/secrets/kwento-88cf359a16d5.json"  # Replace with the path to your JSON credential file
BUCKET_NAME = "kwento-books"  # Replace with the name of your bucket


def check_bucket_access():
    """Check if the service account can confirm that the bucket exists. If it fails, list all accessible buckets."""
    try:
        # Create credentials and initialize the storage client
        credentials = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE
        )
        client = storage.Client(credentials=credentials)

        # Try to get the bucket
        bucket = client.get_bucket(BUCKET_NAME)
        print(f"Bucket '{bucket.name}' exists and is accessible.")
        return True
    except Exception as e:
        print(f"Failed to access the bucket '{BUCKET_NAME}': {e}")
        print("Attempting to list all available buckets...")
        try:
            # List all accessible buckets
            buckets = client.list_buckets()
            bucket_names = [bucket.name for bucket in buckets]
            if bucket_names:
                print("Accessible buckets:")
                for name in bucket_names:
                    print(f"- {name}")
            else:
                print("No accessible buckets found.")
        except Exception as list_error:
            print(f"Failed to list buckets: {list_error}")
        return False


def list_bucket_contents(bucket_name, prefix=""):
    """
    Recursively list the contents of a Google Cloud Storage bucket in a tree-like structure.

    Args:
        bucket_name (str): The name of the GCS bucket.
        prefix (str): The prefix to list. Defaults to the root of the bucket.
    """
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE
    )
    client = storage.Client(credentials=credentials)
    bucket = client.get_bucket(bucket_name)

    # Fetch all blobs with the given prefix
    blobs = bucket.list_blobs(prefix=prefix)

    tree = {}

    # Organize blobs into a nested dictionary structure
    for blob in blobs:
        parts = blob.name.split("/")
        node = tree
        for part in parts:
            node = node.setdefault(part, {})

    # Recursive function to display the tree structure
    def display_tree(node, indent=0):
        for key, subnode in sorted(node.items()):
            if subnode:  # If the node has children
                print("    " * indent + f"└── {key}/")
                display_tree(subnode, indent + 1)
            else:
                print("    " * indent + f"└── {key}")

    print(f"(GCS Buckets Root of GCP Project)")
    print(f"└── {bucket_name}/")
    display_tree(tree, indent=1)


import json


def update_metadata_with_book_info(bucket_name):
    """
    Iterate over each directory in the bucket, open the JSON file in each directory,
    extract 'book_id' and 'book_title' values, and update the JSON file in GCS with
    these values as custom metadata.

    Args:
        bucket_name (str): The name of the GCS bucket.
    """
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE
    )
    client = storage.Client(credentials=credentials)
    bucket = client.get_bucket(bucket_name)

    # List all blobs in the bucket
    blobs = bucket.list_blobs()
    print(f"Blobs in target bucket: {blobs}")

    # Filter and process directories containing JSON files
    for blob in blobs:
        if blob.name.endswith(".json"):  # Check for JSON files
            try:
                # Download the JSON file contents
                print(f"Processing file: {blob.name}")
                json_content = blob.download_as_text()
                json_data = json.loads(json_content)

                # Extract 'book_id' and 'book_title'
                book_id = json_data.get("book_id")
                book_title = json_data.get("book_title")

                if not book_id or not book_title:
                    print(
                        f"Skipping {blob.name}: Missing 'book_id' or 'book_title' in the JSON data."
                    )
                    continue

                # Update metadata
                metadata = blob.metadata or {}
                metadata["book_id"] = book_id
                metadata["book_title"] = book_title

                # Save updated metadata to the GCS blob
                blob.metadata = metadata
                blob.patch()

                print(
                    f"Updated metadata for {blob.name}: book_id={book_id}, book_title={book_title}"
                )
            except Exception as e:
                print(f"Failed to process {blob.name}: {e}")


if __name__ == "__main__":
    # Example usage
    list_bucket_contents(BUCKET_NAME)
