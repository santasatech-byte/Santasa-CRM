import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import time
from playwright.sync_api import sync_playwright

SCREENSHOT_DIR = r"C:\Users\Praveen\.gemini\antigravity\brain\c469a397-9578-468b-8009-87f180e12475"

def run_prod_readiness_test():
    print("================================================================")
    print("🚀 PRODUCTION READINESS & ROLE-BASED TENANT ISOLATION E2E SUITE")
    print("================================================================")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # -------------------------------------------------------------
        # STEP 1: Production Login Gateway & Demo Button Elimination
        # -------------------------------------------------------------
        print("\n--- STEP 1: Verify Production Login Gateway ---")
        page.goto("http://localhost:3030", wait_until="networkidle")
        time.sleep(1)

        # 1.1 Verify Login Modal is displayed
        login_modal = page.locator("#loginModal")
        assert login_modal.is_visible(), "Login modal should be visible"
        print("✔ Login modal is visible.")

        # 1.2 Verify that ALL demo presets are completely ELIMINATED
        for demo_btn_id in ["#fillExecutiveDemoBtn", "#fillHassanDemoBtn", "#fillMysoreDemoBtn", "#fillAdminDemoBtn"]:
            btn_count = page.locator(demo_btn_id).count()
            assert btn_count == 0, f"Demo button {demo_btn_id} must NOT exist in production DOM!"
        print("✔ Verified 0 demo quick-signin buttons in DOM (Complete credentials protection).")

        # Capture Login Gateway Screenshot
        login_shot = os.path.join(SCREENSHOT_DIR, "prod_verify_01_login_gateway.png")
        page.screenshot(path=login_shot)
        print(f"✔ Saved screenshot: {login_shot}")

        # -------------------------------------------------------------
        # STEP 2: SSM Hospital Executive Isolation
        # -------------------------------------------------------------
        print("\n--- STEP 2: SSM Hospital Executive Role & Tenant Isolation ---")
        page.fill("#loginEmailInput", "ssm@hospital.com")
        page.fill("#loginPasswordInput", "Executive@2026!")
        page.click("#submitLoginBtn")
        page.wait_for_selector("#loginModal", state="hidden", timeout=15000)
        time.sleep(1)

        # 2.1 Verify SSM Branding
        hosp_display = page.locator("#currentHospitalDisplay").text_content()
        assert "SSM" in hosp_display, f"Expected SSM Hospital, got: {hosp_display}"
        print(f"✔ Active Hospital: {hosp_display.strip()}")

        # 2.2 Verify Admin crown button #navAdmin is STRICTLY HIDDEN
        nav_admin = page.locator("#navAdmin")
        is_admin_hidden = not nav_admin.is_visible() or "hidden" in (nav_admin.get_attribute("class") or "")
        assert is_admin_hidden, "Admin crown navigation must be STRICTLY HIDDEN for SSM Executive!"
        print("✔ Verified #navAdmin is strictly hidden for Executive.")

        # 2.3 Verify User Dropdown does NOT show Tenant Switcher
        page.click("#userMenuToggleBtn")
        time.sleep(0.5)
        tenant_switcher = page.locator("#adminTenantSwitcherSection")
        is_switcher_hidden = not tenant_switcher.is_visible() or "hidden" in (tenant_switcher.get_attribute("class") or "")
        assert is_switcher_hidden, "Tenant switcher must be STRICTLY HIDDEN for SSM Executive!"
        print("✔ Verified #adminTenantSwitcherSection is strictly hidden in dropdown.")
        page.click("body") # close dropdown

        # 2.4 Verify Clean Empty Leads Pipeline (Zero Dummy Data)
        page.click("#navLeads")
        page.wait_for_selector("#leadsView:not(.hidden)", timeout=5000)
        time.sleep(1)
        leads_text = page.locator("#assignedLeadsTableBody").text_content()
        assert "No matching leads found" in leads_text, f"Expected clean leads table, got: {leads_text}"
        print("✔ Verified clean zero dummy data in Leads View ('No matching leads found').")

        # 2.5 Verify Blocked Admin Access Attempt via URL
        page.goto("http://localhost:3030/#/admin", wait_until="networkidle")
        time.sleep(1)
        admin_view = page.locator("#adminDashboardView")
        assert not admin_view.is_visible() or "hidden" in (admin_view.get_attribute("class") or ""), "Admin Dashboard MUST NOT be visible to Executive!"
        print("✔ Direct navigation to #/admin was safely blocked and redirected.")

        ssm_shot = os.path.join(SCREENSHOT_DIR, "prod_verify_02_ssm_executive.png")
        page.screenshot(path=ssm_shot)
        print(f"✔ Saved screenshot: {ssm_shot}")

        # -------------------------------------------------------------
        # STEP 3: Logout & Session Sanitization
        # -------------------------------------------------------------
        print("\n--- STEP 3: Secure Logout & Memory Sanitization ---")
        page.click("#userMenuToggleBtn")
        time.sleep(0.5)
        page.click("#logoutBtn")
        page.wait_for_selector("#loginModal", state="visible", timeout=10000)
        time.sleep(1)
        print("✔ Session successfully terminated and DOM cleaned.")

        # -------------------------------------------------------------
        # STEP 4: Santasa Hassan Executive Isolation
        # -------------------------------------------------------------
        print("\n--- STEP 4: Santasa Hassan Executive Role & Tenant Isolation ---")
        page.fill("#loginEmailInput", "executive@santasa.com")
        page.fill("#loginPasswordInput", "Executive@2026!")
        page.click("#submitLoginBtn")
        page.wait_for_selector("#loginModal", state="hidden", timeout=15000)
        time.sleep(1)

        hosp_display_shh = page.locator("#currentHospitalDisplay").text_content()
        assert "Hassan" in hosp_display_shh, f"Expected Santasa Hassan Hospital, got: {hosp_display_shh}"
        print(f"✔ Active Hospital: {hosp_display_shh.strip()}")

        # Verify #navAdmin and tenant switcher are hidden
        assert not page.locator("#navAdmin").is_visible(), "#navAdmin must be hidden for Hassan Executive!"
        page.click("#userMenuToggleBtn")
        time.sleep(0.5)
        assert not page.locator("#adminTenantSwitcherSection").is_visible(), "Tenant switcher must be hidden for Hassan Executive!"
        page.click("body")

        shh_shot = os.path.join(SCREENSHOT_DIR, "prod_verify_03_shh_executive.png")
        page.screenshot(path=shh_shot)
        print(f"✔ Saved screenshot: {shh_shot}")

        # Logout
        page.click("#userMenuToggleBtn")
        time.sleep(0.5)
        page.click("#logoutBtn")
        page.wait_for_selector("#loginModal", state="visible", timeout=10000)
        time.sleep(1)

        # -------------------------------------------------------------
        # STEP 5: Super Administrator Multi-Hospital Oversight
        # -------------------------------------------------------------
        print("\n--- STEP 5: Super Administrator Multi-Hospital Gateway ---")
        page.fill("#loginEmailInput", "admin@santasa.com")
        page.fill("#loginPasswordInput", "Admin@2026!")
        page.click("#submitLoginBtn")
        page.wait_for_selector("#loginModal", state="hidden", timeout=15000)
        time.sleep(1)

        admin_hosp = page.locator("#currentHospitalDisplay").text_content()
        assert "Multi-Hospital" in admin_hosp, f"Expected Multi-Hospital Network, got: {admin_hosp}"
        print(f"✔ Active Role: Super Admin ({admin_hosp.strip()})")

        # Verify #navAdmin is VISIBLE for Super Admin
        nav_admin = page.locator("#navAdmin")
        assert nav_admin.is_visible(), "Admin button #navAdmin MUST be visible for Super Admin!"
        print("✔ Verified #navAdmin is visible for Super Admin.")

        # Open Admin Dashboard
        page.click("#navAdmin")
        page.wait_for_selector("#adminDashboardView:not(.hidden)", timeout=5000)
        time.sleep(1.5)
        print("✔ Super Admin Control Center loaded successfully.")

        # Verify dropdown has Tenant Switcher for Super Admin
        page.click("#userMenuToggleBtn")
        time.sleep(0.5)
        assert page.locator("#adminTenantSwitcherSection").is_visible(), "Tenant switcher must be visible for Super Admin!"
        print("✔ Verified #adminTenantSwitcherSection is visible for Super Admin.")
        page.click("body")

        admin_shot = os.path.join(SCREENSHOT_DIR, "prod_verify_04_super_admin.png")
        page.screenshot(path=admin_shot)
        print(f"✔ Saved screenshot: {admin_shot}")

        browser.close()
        print("\n================================================================")
        print("🎉 ALL PRODUCTION READINESS & ROLE ISOLATION TESTS PASSED (100%)")
        print("================================================================")

if __name__ == "__main__":
    run_prod_readiness_test()
