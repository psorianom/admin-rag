"""
This script automatically generates the .env.json file required by `sam local`
from the existing .env file.
"""

import os
import json
from dotenv import dotenv_values

def create_sam_env_json():
    """
    Reads the .env file from the project root, formats it for SAM,
    and writes it to .env.json.
    """
    project_root = os.path.dirname(os.path.dirname(__file__))
    env_path = os.path.join(project_root, '.env')
    env_json_path = os.path.join(project_root, '.env.json')

    if not os.path.exists(env_path):
        print(f"❌ Error: .env file not found at {env_path}")
        print("Please ensure your .env file is in the project root.")
        return

    print(f"Reading environment variables from {env_path}...")
    
    # Load .env file into a dictionary
    env_vars = dotenv_values(env_path)

    # Hardcode the API_STAGE variable as it might not be in the .env file
    if 'API_STAGE' not in env_vars:
        env_vars['API_STAGE'] = 'prod'

    # Structure the variables for SAM under the function name from template.yaml
    sam_vars = {
        "AdminRagFunction": env_vars
    }

    print(f"Writing SAM-compatible environment variables to {env_json_path}...")
    
    with open(env_json_path, 'w') as f:
        json.dump(sam_vars, f, indent=2)

    print("✅ Success! .env.json file created.")
    print("   You can now run `sam local start-api`.")

if __name__ == "__main__":
    create_sam_env_json()
