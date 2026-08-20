import subprocess
import time
import sys

print("Starting persistent LocalTunnel daemon on port 3000...")
while True:
    try:
        proc = subprocess.run(["npx", "-y", "localtunnel", "--port", "3000", "--subdomain", "santasa-crm-demo"], shell=True)
    except Exception as e:
        print(f"Tunnel restarted: {e}")
    time.sleep(2)
