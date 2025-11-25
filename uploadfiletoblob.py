from azure.storage.blob import BlobServiceClient
import os

# 1. Replace with your Azure Storage connection string
connection_string = "[BLOB-CONNECTION-STRING]"


# 2. Define container name and blob (file) name
container_name = "pdf-documents"
blob_name = "jb.pdf"

# 3. Local path to the PDF file you want to upload
local_file_path = "e:\\jb.pdf"

# 4. Create BlobServiceClient
blob_service_client = BlobServiceClient.from_connection_string(connection_string)

# 5. Get container client (creates container if not exists)
container_client = blob_service_client.get_container_client(container_name)
try:
    container_client.create_container()

    print(f"Container '{container_name}' created.")
except Exception:
    print(f"Container '{container_name}' already exists.")

# 6. Upload PDF file
with open(local_file_path, "rb") as data:
    container_client.upload_blob(name=blob_name, data=data, overwrite=True)

print(f"File '{blob_name}' uploaded successfully to container '{container_name}'.")
