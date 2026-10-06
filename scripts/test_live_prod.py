import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import time
from playwright.sync_api import sync_playwright

SCREENSHOT_DIR = r"C:\Users\Praveen\.gemini\antigravity\brain\c469a397-9578-468b-8009-87f180e12475"
LIVE_URL = "https://santasacrm.vercel.app"

def test_live_production():
    print(f"Testing live production site at {LIVE_URL}...")
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page()

        page.goto(LIVE_URL, wait_until="networkidle")
        time.sleep(2)

        # 1. Login modal visible, no demo buttons
        assert page.locator("#loginModal").is_visible(), "Login modal must be visible on live site"
        assert page.locator("#fillExecutiveDemoBtn").count() == 0, "No demo buttons must exist"
        print("✔ Live production login gateway verified (0 demo buttons).")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "live_prod_clean_login.png"))

        # 2. Login as SSM Executive
        page.fill("#loginEmailInput", "ssm@hospital.com")
        page.fill("#loginPasswordInput", "Executive@2026!")
        page.click("#submitLoginBtn")
        page.wait_for_selector("#loginModal", state="hidden", timeout=15000)
        time.sleep(2)

        # Verify SSM branding & isolation
        hosp_text = page.locator("#currentHospitalDisplay").text_content()
        assert "SSM" in hosp_text, f"Expected SSM, got {hosp_text}"
        assert not page.locator("#navAdmin").is_visible(), "Admin button must not be visible"
        print(f"✔ Live SSM Executive verified: {hosp_text.strip()} (Admin strictly hidden).")

        # Open profile dropdown
        page.click("#userMenuToggleBtn")
        time.sleep(0.5)
        assert not page.locator("#adminTenantSwitcherSection").is_visible(), "Tenant switcher hidden for executive"
        print("✔ Live Tenant Switcher strictly hidden in profile dropdown.")
        page.click("body")

        # Check Leads table
        page.click("#navLeads")
        page.wait_for_selector("#leadsView:not(.hidden)", timeout=5000)
        time.sleep(1)
        leads_text = page.locator("#assignedLeadsTableBody").text_content()
        assert "No matching leads found" in leads_text, "Clean leads table verified"
        print("✔ Live Leads Pipeline verified clean (0 dummy data).")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "live_prod_ssm_clean.png"))

        # 3. Logout
        page.click("#userMenuToggleBtn")
        time.sleep(0.5)
        page.click("#logoutBtn")
        page.wait_for_selector("#loginModal", state="visible", timeout=10000)
        time.sleep(1)
        print("✔ Live logout verified.")

        # 4. Super Admin
        page.fill("#loginEmailInput", "admin@santasa.com")
        page.fill("#loginPasswordInput", "Admin@2026!")
        page.click("#submitLoginBtn")
        page.wait_for_selector("#loginModal", state="hidden", timeout=15000)
        time.sleep(2)

        admin_hosp = page.locator("#currentHospitalDisplay").text_content()
        assert "Multi-Hospital" in admin_hosp, f"Expected Multi-Hospital Network, got {admin_hosp}"
        assert page.locator("#navAdmin").is_visible(), "Admin button must be visible for Super Admin"
        print(f"✔ Live Super Admin verified: {admin_hosp.strip()} (Admin crown visible).")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "live_prod_super_admin_clean.png"))

        browser.close()
        print("\n🎉 LIVE PRODUCTION VERCEL SITE 100% VERIFIED!")

if __name__ == "__main__":
    test_live_production()
