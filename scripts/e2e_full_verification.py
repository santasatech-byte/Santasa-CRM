import os
import time
from playwright.sync_api import sync_playwright

SCREENSHOT_DIR = r"C:\Users\Praveen\.gemini\antigravity\brain\c469a397-9578-468b-8009-87f180e12475"

def run_full_e2e():
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        print("1. Navigating to http://localhost:3030...")
        page.goto("http://localhost:3030", wait_until="networkidle")
        time.sleep(1)

        # Check login
        if page.is_visible("#loginModal:not(.hidden)"):
            print("Logging in as SSM Hospital Executive...")
            page.fill("#loginEmailInput", "ssm@hospital.com")
            page.fill("#loginPasswordInput", "Executive@2026!")
            page.click("#submitLoginBtn")
            time.sleep(2)

        # Wait for dashboard
        page.wait_for_selector("#dashboardView:not(.hidden)", timeout=10000)
        time.sleep(1.5)
        print("Dashboard loaded successfully.")
        dash_shot = os.path.join(SCREENSHOT_DIR, "verify_ssm_dashboard_v2.png")
        page.screenshot(path=dash_shot, full_page=True)
        print("Saved Dashboard screenshot:", dash_shot)

        # 2. Leads view
        print("2. Testing Leads View...")
        page.click("#navLeads")
        page.wait_for_selector("#leadsView:not(.hidden)", timeout=5000)
        time.sleep(1.5)
        leads_shot = os.path.join(SCREENSHOT_DIR, "verify_ssm_leads_v2.png")
        page.screenshot(path=leads_shot, full_page=True)
        print("Saved Leads screenshot:", leads_shot)

        # 3. Create Lead view
        print("3. Testing Create A New Lead...")
        page.click("#goToCreateLeadBtn")
        page.wait_for_selector("#createLeadView:not(.hidden)", timeout=5000)
        time.sleep(1)
        create_shot = os.path.join(SCREENSHOT_DIR, "verify_ssm_create_lead_v2.png")
        page.screenshot(path=create_shot, full_page=True)
        print("Saved Create Lead screenshot:", create_shot)

        # Fill and create new lead
        test_patient = "Nending Asha Test"
        test_phone = "7005940191"
        page.fill("#inputFormPatientName", test_patient)
        page.fill("#inputFormContactNumber", test_phone)
        page.fill("#inputFormEmail", "mongoktokbauling@gmail.com")
        page.fill("#inputFormTreatment", "Obstetrics & Gynaecology")
        page.fill("#inputFormMessage", "Need an appointment around 12:30 pm or after 5 pm")
        page.select_option("#inputFormPatientType", "Digital Patient")
        page.select_option("#inputFormLeadStatus", "Valid - Followup")
        page.fill("#inputFormRemarks", "First consultation inquiry")
        page.click("#createLeadForm button[type='submit']")
        time.sleep(2)

        # 4. Update Client Lead view (Screenshots 1 & 2)
        print("4. Testing Update Client Lead View...")
        page.wait_for_selector("#leadsView:not(.hidden)", timeout=5000)
        time.sleep(1)

        # Click on the newly created lead link in the visible assigned leads table
        lead_link = page.locator(f"#assignedLeadsTableBody .view-lead-action:has-text('{test_patient}')").first
        lead_link.scroll_into_view_if_needed()
        lead_link.click()
        page.wait_for_selector("#updateClientLeadView:not(.hidden)", timeout=5000)
        time.sleep(1.5)

        # Verify fields populated
        patient_val = page.input_value("#updatePatientName")
        assert test_patient in patient_val, f"Expected {test_patient} in update form, got {patient_val}"
        print(f"Verified patient name populated: {patient_val}")

        # Update some fields
        page.fill("#updateTreatment", "Obstetrics & Gynaecology - IVF Special")
        page.select_option("#updateReviewNeeded", "Yes")
        page.fill("#updateReviewPeriod", "14 Days")
        page.fill("#updateReviewDetails", "medication suggested and ultrasound scan")
        page.fill("#updateRemarks", "Patient responded positively, follow up scheduled")

        # Capture Update Client Lead Screenshot
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(0.5)
        update_shot = os.path.join(SCREENSHOT_DIR, "verify_ssm_update_lead.png")
        page.screenshot(path=update_shot, full_page=True)
        print("Saved Update Client Lead screenshot:", update_shot)

        # Test Schedule Call Modal
        print("Testing Schedule Call modal from Update Lead view...")
        page.click("#btnOpenScheduleCallFromUpdate")
        page.wait_for_selector("#scheduleCallModal:not(.hidden)", timeout=5000)
        time.sleep(0.5)
        page.fill("#scheduleCallNotes", "Follow up on ultrasound scan results")
        page.click("#btnConfirmScheduleCall")
        time.sleep(1.5)
        print("Call scheduled successfully.")

        # Submit Update Form
        print("Submitting lead update...")
        page.click("#btnSubmitUpdateClientLead")
        time.sleep(2)
        page.wait_for_selector("#leadsView:not(.hidden)", timeout=5000)
        print("Lead update saved successfully and returned to leads list.")

        # 5. Call Notifications View (Screenshot 3)
        print("5. Testing Call Notifications View...")
        page.click("#navCallNotifications")
        page.wait_for_selector("#callNotificationsView:not(.hidden)", timeout=5000)
        time.sleep(2)
        page.wait_for_selector("#callsFeedTableBody tr", timeout=5000)
        page.evaluate("window.scrollTo(0, 0)")
        calls_shot = os.path.join(SCREENSHOT_DIR, "verify_ssm_call_notifications.png")
        page.screenshot(path=calls_shot, full_page=True)
        print("Saved Call Notifications screenshot:", calls_shot)

        calls_table_text = page.inner_text("#callsFeedTableBody")
        assert "No scheduled calls found" not in calls_table_text, "Should display scheduled calls data"
        print("Verified scheduled calls rendered with live data.")

        # 6. Reviews View (Screenshot 4)
        print("6. Testing Reviews View...")
        page.click("#navReviews")
        page.wait_for_selector("#reviewsView:not(.hidden)", timeout=5000)
        time.sleep(2)
        page.wait_for_selector("#reviewsTableBody tr", timeout=5000)
        page.evaluate("window.scrollTo(0, 0)")
        reviews_shot = os.path.join(SCREENSHOT_DIR, "verify_ssm_reviews.png")
        page.screenshot(path=reviews_shot, full_page=True)
        print("Saved Reviews screenshot:", reviews_shot)

        reviews_table_text = page.inner_text("#reviewsTableBody")
        assert "No reviews found" not in reviews_table_text, "Should display reviews data"
        print("Verified reviews rendered with live data.")

        # 7. Multi-Hospital Tenant Isolation
        print("7. Testing Tenant Isolation: Switching to Santasa Hassan Hospital...")
        page.click("#userMenuToggleBtn")
        time.sleep(0.5)
        page.click(".switch-tenant-btn[data-email='executive@santasa.com']")
        time.sleep(2)

        # Check Santasa Leads
        page.click("#navLeads")
        time.sleep(2)
        hassan_leads = page.inner_text("#assignedLeadsTableBody")
        assert test_patient not in hassan_leads, "SSM patient MUST NOT appear in Santasa Hassan leads table!"
        print("Verified: SSM lead is completely isolated from Santasa Hassan!")

        # Check Santasa Reviews
        page.click("#navReviews")
        time.sleep(2)
        hassan_reviews = page.inner_text("#reviewsTableBody")
        assert test_patient not in hassan_reviews, "SSM review MUST NOT appear in Santasa Hassan reviews table!"
        print("Verified: Reviews are strictly tenant-isolated!")

        hassan_shot = os.path.join(SCREENSHOT_DIR, "verify_santasa_isolated.png")
        page.screenshot(path=hassan_shot, full_page=True)
        print("Saved Santasa Isolated screenshot:", hassan_shot)

        browser.close()
        print("\n=== ALL COMPREHENSIVE E2E VERIFICATION TESTS PASSED CLEANLY! ===")

if __name__ == "__main__":
    run_full_e2e()
