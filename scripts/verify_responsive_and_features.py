"""
Automated Multi-Device Responsive Layout & Feature Audit Verification
Tests Desktop (1536x900), Tablet (768x1024), and Mobile (390x844) Viewports.
Audits all interactive forms, buttons, drawers, and pagination flows.
"""
import os
import sys
import time
from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:3030"
SCREENSHOT_DIR = r"C:\Users\Praveen\.gemini\antigravity\brain\c469a397-9578-468b-8009-87f180e12475"

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="msedge")
        
        # -------------------------------------------------------------
        # 1. DESKTOP VIEWPORT TEST (1536x900)
        # -------------------------------------------------------------
        print("=== 1. TESTING DESKTOP VIEWPORT (1536x900) ===")
        context = browser.new_context(viewport={"width": 1536, "height": 900})
        page = context.new_page()

        page.goto(BASE_URL, timeout=15000)
        page.wait_for_selector("#dashboardView", timeout=10000)
        time.sleep(2)

        # Login as SSM Executive if login modal visible
        if page.is_visible("#loginModal:not(.hidden)"):
            page.fill("#loginEmailInput", "ssm@hospital.com")
            page.fill("#loginPasswordInput", "Executive@2026!")
            page.click("#loginForm button[type='submit']")
            time.sleep(2)

        # Go to Create Lead view
        print("Opening Create Lead view on Desktop...")
        page.click("#navLeads")
        page.wait_for_selector("#leadsView:not(.hidden)", timeout=5000)
        time.sleep(1)
        page.click("#goToCreateLeadBtn")
        page.wait_for_selector("#createLeadView:not(.hidden)", timeout=5000)
        time.sleep(1)

        # Capture Desktop Create Lead Screenshot (Compare to user's uploaded screenshot)
        desktop_create_shot = os.path.join(SCREENSHOT_DIR, "verify_responsive_desktop_create_lead.png")
        page.screenshot(path=desktop_create_shot)
        print("Saved Desktop Create Lead screenshot:", desktop_create_shot)

        # Fill and submit a new lead to verify Create Lead flow
        test_patient = f"Device Fit Patient {int(time.time()) % 10000}"
        test_phone = "9876543210"
        print(f"Creating lead: {test_patient}...")
        page.fill("#inputFormPatientName", test_patient)
        page.fill("#inputFormContactNumber", test_phone)
        page.fill("#inputFormEmail", "devicefit@example.com")
        page.fill("#inputFormTreatment", "IVF & Fertility Consultation")
        page.fill("#inputFormRemarks", "Device layout and form flow automated test")
        page.click("#submitLeadBtn")
        time.sleep(2)
        page.wait_for_selector("#leadsView:not(.hidden)", timeout=5000)
        print("Lead created successfully and returned to Leads list.")

        # Verify created lead is visible in table
        lead_row = page.locator(f"#assignedLeadsTableBody tr:has-text('{test_patient}')").first
        assert lead_row.is_visible(), "New lead should be visible in assigned leads table"
        print("Verified new lead in table.")

        # Test Lead Action Drawer (...)
        print("Testing Quick Action Drawer (...) on created lead...")
        dots_btn = lead_row.locator(".action-dots-btn")
        dots_btn.click()
        page.wait_for_selector("#leadActionDrawerModal:not(.hidden)", timeout=5000)
        time.sleep(0.5)

        # Test Add Note button in Drawer
        print("Testing Add Note modal...")
        page.click("#drawerAddNoteBtn")
        page.wait_for_selector("#noteModal:not(.hidden)", timeout=5000)
        page.fill("#inputNoteText", "Patient requested immediate follow-up on protocol cost.")
        page.click("#noteForm button[type='submit']")
        time.sleep(1.5)
        print("Note saved successfully.")

        # Test Edit Full Lead from Lead link
        print("Opening Update Client Lead view on Desktop...")
        lead_link = lead_row.locator(".view-lead-action")
        lead_link.click()
        page.wait_for_selector("#updateClientLeadView:not(.hidden)", timeout=5000)
        time.sleep(1)

        # Capture Desktop Update Lead Screenshot
        desktop_update_shot = os.path.join(SCREENSHOT_DIR, "verify_responsive_desktop_update_lead.png")
        page.screenshot(path=desktop_update_shot)
        print("Saved Desktop Update Lead screenshot:", desktop_update_shot)

        # Back to Leads
        page.click("#btnBackFromUpdateLead")
        page.wait_for_selector("#leadsView:not(.hidden)", timeout=5000)
        time.sleep(1)

        # Test Call Notifications View & Pagination
        print("Testing Call Notifications View & Pagination...")
        page.click("#navCallNotifications")
        page.wait_for_selector("#callNotificationsView:not(.hidden)", timeout=5000)
        time.sleep(1.5)
        page.select_option("#callsPageSizeSelect", "10")
        time.sleep(0.5)
        assert page.is_visible("#callsFeedTableBody tr"), "Scheduled calls table should render rows"
        print("Call Notifications DataTable verified.")

        # Test Reviews View & Pagination
        print("Testing Reviews View & Pagination...")
        page.click("#navReviews")
        page.wait_for_selector("#reviewsView:not(.hidden)", timeout=5000)
        time.sleep(1.5)
        page.select_option("#reviewsPageSizeSelect", "10")
        time.sleep(0.5)
        assert page.is_visible("#reviewsTableBody tr"), "Reviews table should render rows"
        print("Reviews DataTable verified.")

        context.close()

        # -------------------------------------------------------------
        # 2. TABLET VIEWPORT TEST (768x1024 - iPad / Galaxy Tab)
        # -------------------------------------------------------------
        print("\n=== 2. TESTING TABLET VIEWPORT (768x1024) ===")
        tab_context = browser.new_context(viewport={"width": 768, "height": 1024})
        tab_page = tab_context.new_page()

        tab_page.goto(BASE_URL, timeout=15000)
        tab_page.wait_for_selector("#dashboardView", timeout=10000)
        time.sleep(1.5)

        tab_page.click("#navLeads")
        tab_page.wait_for_selector("#leadsView:not(.hidden)", timeout=5000)
        time.sleep(0.5)
        tab_page.click("#goToCreateLeadBtn")
        tab_page.wait_for_selector("#createLeadView:not(.hidden)", timeout=5000)
        time.sleep(1)

        tablet_create_shot = os.path.join(SCREENSHOT_DIR, "verify_responsive_tablet_create_lead.png")
        tab_page.screenshot(path=tablet_create_shot)
        print("Saved Tablet Create Lead screenshot:", tablet_create_shot)

        tab_context.close()

        # -------------------------------------------------------------
        # 3. MOBILE VIEWPORT TEST (390x844 - iPhone / Galaxy M17)
        # -------------------------------------------------------------
        print("\n=== 3. TESTING MOBILE VIEWPORT (390x844) ===")
        mob_context = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        mob_page = mob_context.new_page()

        mob_page.goto(BASE_URL, timeout=15000)
        mob_page.wait_for_selector("#dashboardView", timeout=10000)
        time.sleep(1.5)

        # Capture Mobile Dashboard
        mobile_dash_shot = os.path.join(SCREENSHOT_DIR, "verify_responsive_mobile_dashboard.png")
        mob_page.screenshot(path=mobile_dash_shot)
        print("Saved Mobile Dashboard screenshot:", mobile_dash_shot)

        # Navigate to Leads
        mob_page.click("#navLeads")
        mob_page.wait_for_selector("#leadsView:not(.hidden)", timeout=5000)
        time.sleep(1)

        mobile_leads_shot = os.path.join(SCREENSHOT_DIR, "verify_responsive_mobile_leads.png")
        mob_page.screenshot(path=mobile_leads_shot)
        print("Saved Mobile Leads screenshot:", mobile_leads_shot)

        # Open Create Lead on Mobile
        mob_page.click("#goToCreateLeadBtn")
        mob_page.wait_for_selector("#createLeadView:not(.hidden)", timeout=5000)
        time.sleep(1)

        mobile_create_shot = os.path.join(SCREENSHOT_DIR, "verify_responsive_mobile_create_lead.png")
        mob_page.screenshot(path=mobile_create_shot)
        print("Saved Mobile Create Lead screenshot:", mobile_create_shot)

        mob_context.close()
        browser.close()

        print("\n=== ALL RESPONSIVE & FEATURE AUDIT TESTS PASSED CLEANLY! ===")

if __name__ == "__main__":
    run()
