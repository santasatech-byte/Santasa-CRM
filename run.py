import os
import sys
import socket
import threading
import time
import webbrowser
import traceback
import uvicorn

root_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(root_dir, "hospital_crm", "backend")

for p in [backend_dir, root_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from app.main import app
except Exception as e:
    print("FATAL STARTUP IMPORT ERROR AT ROOT:")
    traceback.print_exc()
    sys.exit(1)


def get_lan_ip():
    """Finds local network IP for mobile device sync."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def open_browser(port):
    time.sleep(1.8)
    try:
        webbrowser.open(f"http://localhost:{port}")
    except Exception:
        pass


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    lan_ip = get_lan_ip()

    banner = f"""
=======================================================================
   SANTASA IVF & HOSPITAL CRM - LOCAL ENGINE & MOBILE SYNC GATEWAY
=======================================================================
* Local Web CRM:     http://localhost:{port}
* Network URL (LAN): http://{lan_ip}:{port}
* API Documentation: http://localhost:{port}/docs

[MACRODROID MOBILE INTEGRATION SETUP]
For Samsung M17 or Android device on the same Wi-Fi:
1. Call Started Trigger (Outgoing & Incoming):
   URL: http://{lan_ip}:{port}/api/v1/telephony/mobile-sync/call-start?phone=[call_number]&direction=[call_type]
   HTTP Method: GET

2. Call Ended Trigger:
   URL: http://{lan_ip}:{port}/api/v1/telephony/mobile-sync/call-log
   HTTP Method: POST (multipart form)
   Fields:
     phone_number = [call_number]
     duration_seconds = [call_duration_seconds]
     direction = [call_type]
     file = /storage/emulated/0/Recordings/Call/[latest_file]

   * Note: The CRM will display a live pulsating banner during calls,
     allowing executives to enter patient info live without duplicate leads!
=======================================================================
"""
    print(banner)

    # Launch browser automatically
    threading.Thread(target=open_browser, args=(port,), daemon=True).start()

    uvicorn.run(app, host=host, port=port)

