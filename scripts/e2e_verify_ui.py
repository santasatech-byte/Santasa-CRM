import os
import time
from playwright.sync_api import sync_playwright

SCREENSHOT_DIR = r"C:\Users\Praveen\.gemini\antigravity\brain\c469a397-9578-468b-8009-87f180e12475"

def run_e2e():
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        print("Navigating to http://localhost:3030...")
        page.goto("http://localhost:3030", wait_until="networkidle")
        time.sleep(1)

        # Check if login modal is present
        if page.is_visible("#loginModal:not(.hidden)"):
            print("Logging in as ssm@hospital.com...")
            page.fill("#loginEmailInput", "ssm@hospital.com")
            page.fill("#loginPasswordInput", "Executive@2026!")
            page.click("#submitLoginBtn")
            time.sleep(2)
        else:
            print("Auto-logged in or session exists.")

        # Wait for dashboard view to be visible
        page.wait_for_selector("#dashboardView:not(.hidden)", timeout=10000)
        time.sleep(2)
        print("Dashboard loaded successfully.")

        # Capture Dashboard Screenshot
        dash_path = os.path.join(SCREENSHOT_DIR, "verify_ssm_dashboard.png")
        page.screenshot(path=dash_path, full_page=True)
        print("Saved dashboard screenshot:", dash_path)

        # 2. Navigate to Leads View
        print("Navigating to Leads view...")
        page.click("#navLeads")
        page.wait_for_selector("#leadsView:not(.hidden)", timeout=5000)
        time.sleep(2)
        leads_path = os.path.join(SCREENSHOT_DIR, "verify_ssm_leads.png")
        page.screenshot(path=leads_path, full_page=True)
        print("Saved leads screenshot:", leads_path)

        # 3. Navigate to Create Lead View
        print("Navigating to Create Lead view...")
        page.click("#goToCreateLeadBtn")
        page.wait_for_selector("#createLeadView:not(.hidden)", timeout=5000)
        time.sleep(1)
        create_path = os.path.join(SCREENSHOT_DIR, "verify_ssm_create_lead.png")
        page.screenshot(path=create_path, full_page=True)
        print("Saved create lead screenshot:", create_path)

        # 4. Fill and submit a test lead for SSM
        print("Filling Create Lead form for SSM Hospital...")
        page.fill("#inputFormPatientName", "Pooja Hegde Test")
        page.fill("#inputFormContactNumber", "9845012345")
        page.fill("#inputFormEmail", "pooja.test@example.com")
        page.select_option("#inputFormPatientType", "New Patient Enquiry")
        page.select_option("#inputFormLeadSource", "Website - Home")
        page.select_option("#inputFormLeadStatus", "New")
        page.click("#createLeadForm button[type='submit']")
        time.sleep(2)
        print("Submitted create lead form.")

        # Wait for redirection to Leads view and verify new lead appears
        page.wait_for_selector("#leadsView:not(.hidden)", timeout=5000)
        time.sleep(2)
        content = page.content()
        assert "Pooja Hegde Test" in content, "New lead should appear in SSM leads list"
        print("Verified new lead 'Pooja Hegde Test' appears in SSM leads list!")

        # 5. Switch to Santasa Hassan Executive
        print("Testing Hospital Switcher to Santasa Hassan...")
        page.click("#userMenuToggleBtn")
        time.sleep(0.5)
        page.click(".switch-tenant-btn[data-email='executive@santasa.com']")
        time.sleep(2)

        # Verify Santasa Hassan context
        page.click("#navLeads")
        time.sleep(2)
        shh_table_text = page.inner_text("#assignedLeadsTableBody")
        assert "Pooja Hegde Test" not in shh_table_text, "SSM lead MUST NOT appear in Santasa Hassan leads table!"
        print("Verified strict data isolation: SSM lead is completely hidden from Santasa Hassan leads table!")

        shh_path = os.path.join(SCREENSHOT_DIR, "verify_santasa_leads.png")
        page.screenshot(path=shh_path, full_page=True)
        print("Saved Santasa leads screenshot:", shh_path)

        browser.close()
        print("\nALL E2E UI VERIFICATIONS SUCCEEDED CLEANLY!")

if __name__ == "__main__":
    run_e2e()
