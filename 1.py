import streamlit as st
import os
import re
from playwright.sync_api import sync_playwright

# --- STREAMLIT CLOUD INSTALLATION WORKAROUND ---
@st.cache_resource
def install_playwright():
    # We only install the browser binary here. 
    # packages.txt handles the system dependencies!
    os.system("playwright install chromium")

install_playwright()
# -----------------------------------------------
# --------------------------------------------------------------

# ... (the rest of your workflow code starts here) ...
def log_step(message):
    print(f"🤖 LOG: {message}")
    st.toast(message)


def run_automation(account_name, location_name, job_id):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)

        if os.path.exists("state.json"):
            context = browser.new_context(storage_state="state.json")
            log_step("Loaded saved session state.")
        else:
            context = browser.new_context()
            log_step("Starting fresh session.")

        try:
            # =============================================================
            # STEP 1: SERVICE FUSION LOGIN & INITIAL NAVIGATION
            # =============================================================
            log_step("Opening Service Fusion...")
            sf_page = context.new_page()
            sf_page.goto("https://auth.servicefusion.com/auth/login")

            if sf_page.get_by_role("textbox", name="Company ID").is_visible():
                log_step("Logging in to Service Fusion...")
                sf_page.get_by_role("textbox", name="Company ID").click()
                sf_page.get_by_role("textbox", name="Company ID").fill("jagfield")
                sf_page.get_by_role("textbox", name="Username").click()
                sf_page.get_by_role("textbox", name="Username").fill("Syed")
                sf_page.get_by_role("textbox", name="Password").click()
                sf_page.get_by_role("textbox", name="Password").fill("Welcome110@")
                sf_page.get_by_role("button", name="Sign In").click()

                sf_page.wait_for_url("**/jobs", timeout=15000)
                context.storage_state(path="state.json")
            else:
                log_step("Already logged in to Service Fusion.")

            sf_page.goto("https://admin.servicefusion.com/jobs")
            # sf_page.get_by_role("link", name="Jobs Dashboard").click()
            # log_step("Done0")

            sf_page.locator("div.section").filter(has=sf_page.locator("h4", has_text="Closed")).locator(
                "a.jobStatus").filter(has_text="IQR").click()
            sf_page.wait_for_timeout(3000)
            log_step("Done")

            # =============================================================
            # STEP 2: INSPECTALL LOGIN - SOURCE TAB
            # =============================================================
            log_step("Opening InspectAll...")
            page1 = context.new_page()
            page1.goto("https://app.inspectall.com/v4/")
            page1.wait_for_timeout(5000)

            if page1.get_by_role("textbox", name="Quick Search...").is_visible():
                log_step("Already logged in to InspectAll.")
            elif page1.get_by_role("textbox", name="Email").is_visible():
                log_step("Logging into InspectAll...")
                page1.get_by_role("textbox", name="Email").fill("Echelonai@gmail.com")
                page1.wait_for_timeout(1000)
                page1.locator("input[name=\"password\"]").fill("Fieldservice@8036")
                page1.wait_for_timeout(1000)
                page1.get_by_role("button", name="Login").click()
                page1.wait_for_selector('input[placeholder="Quick Search..."]', state="visible", timeout=30000)
                context.storage_state(path="state.json")
                page1.wait_for_timeout(2000)

            # =============================================================
            # STEP 3: SEARCH JOB IN INSPECTALL
            # =============================================================
            log_step(f"Searching for Job ID: {job_id}")
            search_input = page1.get_by_role("textbox", name="Quick Search...")
            search_input.click()
            search_input.fill(job_id)
            page1.wait_for_timeout(1500)
            search_input.press("Enter")
            page1.wait_for_timeout(3000)

            log_step("Opening 'Annual Inspection' folder...")
            page1.locator("#search-folders-region").get_by_text("Annual Inspection").click()
            page1.wait_for_timeout(3000)

            source_folder_url = page1.url

            # =============================================================
            # STEP 4: IDENTIFY FORMS WITH RED/ORANGE DOTS
            # =============================================================
            log_step("Scanning forms for Red/Orange priorities...")
            form_items = page1.locator("ul.forms-list li").all()
            qualifying_forms = []

            for i, form_item in enumerate(form_items):
                has_red = form_item.locator('path[fill="#C74545"]').count() > 0
                has_orange = form_item.locator('path[fill="#EB7E35"]').count() > 0

                if has_red or has_orange:
                    full_text = form_item.inner_text()
                    asset_ids = []

                    tag_match = re.findall(r'(?:🏷|◆)\s*([A-Za-z0-9,\-\s/]+?)(?:\n|$)', full_text)
                    if tag_match:
                        raw = tag_match[0].strip()
                        asset_ids = [aid.strip() for aid in raw.split(",") if aid.strip()]

                    if not asset_ids:
                        links = form_item.locator("a")
                        for li_idx in range(links.count()):
                            link_text = links.nth(li_idx).inner_text().strip()
                            if re.search(r'[A-Z0-9]', link_text,
                                         re.IGNORECASE) and "Inspection" not in link_text and "note" not in link_text.lower():
                                asset_ids = [aid.strip() for aid in link_text.split(",") if aid.strip()]
                                if asset_ids:
                                    break

                    qualifying_forms.append({
                        "index": i,
                        "asset_ids": asset_ids
                    })
                    log_step(f"Form {i + 1} targeted. Extracted search IDs: {asset_ids}")

            if not qualifying_forms:
                return False, "No forms with red/orange deficiencies found."

            log_step(f"Total forms to process: {len(qualifying_forms)}")
            page1.wait_for_timeout(2000)

            # =============================================================
            # STEP 5: CREATE INSPECTION REPAIRS FOLDER
            # =============================================================
            log_step("Creating new 'Inspection Repairs' folder...")
            page2 = context.new_page()
            page2.goto("https://app.inspectall.com/v4/#folders/2876902")
            page2.wait_for_timeout(3000)

            page2.get_by_role("link", name=" Folders").click()
            page2.wait_for_timeout(2000)

            page2.locator("button").filter(has_text="Add Folder").first.click()
            page2.wait_for_timeout(1000)

            page2.get_by_text("Create New").click()
            page2.locator("button").filter(has_text="Choose a Folder Type").first.click()
            page2.wait_for_timeout(1000)

            page2.locator("#treeview").get_by_text("Inspection Repairs", exact=True).click()
            page2.locator("button").filter(has_text="I'm done").first.click()
            page2.wait_for_timeout(1000)

            search_box = page2.locator("input[name=\"kendoAccountSearch\"]")
            search_box.click()
            search_box.press_sequentially(account_name, delay=100)
            page2.wait_for_timeout(1500)
            search_box.press("Enter")
            page2.wait_for_timeout(1000)

            if location_name and location_name.strip():
                page2.get_by_role("combobox", name="Pick a Location...").locator("b").click()
                page2.wait_for_timeout(1000)
                page2.locator("input[type=\"search\"]").fill(location_name)
                page2.wait_for_timeout(1500)
                page2.get_by_role("treeitem", name=location_name).click()

            desc_area = page2.locator("textarea[name=\"description\"]")
            desc_area.click()

            page1.bring_to_front()
            page1.locator(".fa.fa-pencil").first.click()
            page1.wait_for_timeout(1000)

            page1.get_by_role("textbox", name="ID").click()
            copied_id = page1.get_by_role("textbox", name="ID").input_value()
            log_step(f"Copied System ID for description: {copied_id}")

            page2.bring_to_front()
            desc_area.click()
            desc_area.fill(f"Annual Inspection: {copied_id}")
            page2.wait_for_timeout(500)

            page2.locator(".fa.fa-minus-circle").click()
            page2.wait_for_timeout(500)

            page2.locator("button").filter(has_text="Create Folder").first.click()
            page2.wait_for_timeout(3000)

            repairs_folder_url = page2.url
            log_step("Folder created successfully.")

            page1.bring_to_front()
            page1.locator("button").filter(has_text="Cancel").first.click()
            page1.wait_for_timeout(1000)

            # =============================================================
            # STEP 6: PROCESS EACH QUALIFYING FORM
            # =============================================================
            for form_data in qualifying_forms:
                form_index = form_data["index"]
                asset_ids = form_data["asset_ids"]

                log_step(f"--- STARTING FORM {form_index + 1} ---")

                # ---------------------------------------------------------
                # PHASE 1: CREATE DESTINATION FORM FIRST
                # ---------------------------------------------------------
                log_step("Phase 1: Adding new form in destination folder...")
                page2.bring_to_front()
                page2.wait_for_timeout(1500)
                page2.goto(repairs_folder_url)
                page2.wait_for_timeout(2500)

                page2.locator("button").filter(has_text="Add Form").first.click()
                page2.wait_for_timeout(1500)

                page2.get_by_text("Pick Forms for Assets Choose").click()
                page2.wait_for_timeout(2000)

                asset_found = False
                for asset_id in asset_ids:
                    log_step(f"Searching for Asset ID: '{asset_id}'...")
                    page2.locator("button").filter(has_text="Search: Assets").first.click()
                    page2.wait_for_timeout(1500)

                    page2.get_by_role("textbox", name="ID").fill(asset_id)
                    page2.wait_for_timeout(1500)

                    page2.get_by_role("button", name="Search", exact=True).click()
                    page2.wait_for_timeout(2500)

                    result_item = page2.locator("li").filter(has_text=asset_id).first

                    if result_item.is_visible():
                        log_step(f"✅ Asset found on screen: '{asset_id}'!")
                        asset_found = True
                        result_item.click()
                        page2.wait_for_timeout(2000)
                        break
                    else:
                        log_step(f"❌ Asset '{asset_id}' not found. Clearing search...")
                        page2.locator("button").filter(has_text="clear search").first.click()
                        page2.wait_for_timeout(1500)

                if not asset_found:
                    log_step(f"⚠️ Exhausted all IDs for Form {form_index + 1}. Skipping to next form.")
                    close_btn = page2.locator("button:has-text('Cancel'), .close").first
                    if close_btn.is_visible():
                        close_btn.click()
                    page2.wait_for_timeout(1500)
                    continue

                page2.locator("button").filter(has_text="Next").first.click()
                page2.wait_for_timeout(3000)

                log_step("Selecting 'Inspection Repair Report' template...")
                target_template = page2.locator(".class-form-templates-list li").filter(
                    has_text="Inspection Repair Report").first
                if target_template.is_visible():
                    target_template.locator("div > div").first.click()
                else:
                    log_step("⚠️ Template text match failed, falling back to 2nd item.")
                    page2.locator(".class-form-templates-list > li:nth-child(2) > div > div").first.click()

                page2.wait_for_timeout(3000)

                page2.locator("button").filter(has_text="Create Forms").first.click()
                page2.wait_for_timeout(3000)
                log_step("Destination form created successfully.")

                # ---------------------------------------------------------
                # PHASE 2: OPEN SOURCE FORM & EXTRACT DATA
                # ---------------------------------------------------------
                log_step("Phase 2: Opening source form to extract data...")
                page1.bring_to_front()
                page1.wait_for_timeout(1000)
                page1.goto(source_folder_url)

                page1.wait_for_selector("ul.forms-list li", timeout=5000)
                page1.wait_for_timeout(2000)

                log_step(f"Clicking to open Form {form_index + 1}...")
                form_rows = page1.locator("ul.forms-list li")
                form_rows.nth(form_index).locator("a").last.click()
                page1.wait_for_timeout(5000)

                log_step("Extracting Red/Orange category data...")
                collected_texts = []

                try:
                    page1.wait_for_selector("#questions-region li", timeout=5000)
                except Exception:
                    log_step("⚠️ Could not find questions in the sidebar. Moving on.")

                target_pattern = re.compile(r"\b(DEF|REC|Fail|Fault|Mandatory)\b", re.IGNORECASE)

                sidebar_locator = page1.locator("#questions-region li:not(:has(li))").filter(
                    has_text=target_pattern)

                if sidebar_locator.count() == 0:
                    sidebar_locator = page1.locator("li:not(:has(li))").filter(
                        has_text=target_pattern)

                item_count = sidebar_locator.count()
                log_step(f"Found {item_count} valid subcategories to scan...")

                for i in range(item_count):
                    item = sidebar_locator.nth(i)

                    try:
                        raw_name = item.evaluate("""node => {
                            let current = node;
                            while (current && current !== document.body) {
                                let titleNode = current.querySelector('.answers-question-title');
                                if (titleNode) {
                                    return titleNode.innerText.trim();
                                }
                                current = current.parentElement;
                            }
                            return '';
                        }""")
                    except Exception:
                        raw_name = ""

                    if not raw_name:
                        continue

                    # FORMAT FIX: Flawlessly chops off the leading numbers (e.g., "49: Hook Latch" -> "Hook Latch")
                    subcategory_name = re.sub(r'^\d+[:\-]?\s*', '', raw_name).strip()

                    item.click()
                    page1.wait_for_timeout(2000)

                    comment_text = ""
                    comment_box = page1.locator("textarea[placeholder='Enter any additional comments...']")
                    if comment_box.count() > 0 and comment_box.first.is_visible():
                        comment_text = comment_box.first.input_value().strip()

                    # PASTING LOGIC
                    if comment_text:
                        collected_texts.append(f"- {comment_text}")
                    else:
                        collected_texts.append(f"- {subcategory_name}")

                final_text = "\n".join(collected_texts)

                if not final_text:
                    log_step(f"No usable data found in Form {form_index + 1}. Closing and skipping paste.")
                    page1.locator("button").filter(has_text="Done").first.click()
                    page1.wait_for_timeout(2000)
                    continue

                log_step(f"Successfully extracted {len(collected_texts)} data points.")
                page1.locator("button").filter(has_text="Done").first.click()
                page1.wait_for_timeout(2000)

                # ---------------------------------------------------------
                # PHASE 3: PASTE DATA INTO DESTINATION FORM
                # ---------------------------------------------------------
                log_step("Phase 3: Pasting extracted data into new form...")
                page2.bring_to_front()
                page2.wait_for_timeout(1500)

                page2.locator(".grid-go-button > a").last.click()
                page2.wait_for_timeout(4000)

                first_q = page2.locator("#questions-region li").first
                if first_q.is_visible():
                    first_q.click()
                    page2.wait_for_timeout(2000)

                dest_textarea = page2.locator("textarea[placeholder='Enter any additional comments...']")
                if dest_textarea.count() > 0 and dest_textarea.first.is_visible():
                    dest_textarea.first.click()
                    page2.wait_for_timeout(1500)
                    dest_textarea.first.fill(final_text)
                else:
                    fallback = page2.locator("textarea").first
                    if fallback.is_visible():
                        fallback.click()
                        page2.wait_for_timeout(1500)
                        fallback.fill(final_text)

                page2.wait_for_timeout(2500)

                page2.locator("button").filter(has_text="Done").first.click()
                page2.wait_for_timeout(2500)

                log_step(f"✅ Form {form_index + 1} completed!")

            # =============================================================
            # STEP 7: SERVICE FUSION JOB UPDATE
            # =============================================================
            log_step("Updating Service Fusion Job Status...")
            sf_page.bring_to_front()
            #sf_page.goto("https://admin.servicefusion.com/jobs"
            sf_page.get_by_role("textbox", name="Search:").click()
            sf_page.wait_for_timeout(2000)
            sf_page.get_by_role("textbox", name="Search:").press_sequentially(job_id,delay=100)

            # search_box.press_sequentially(account_name, delay=100)
            # FIX: Wait for the table to filter out older jobs before clicking
            sf_page.wait_for_timeout(2000)

            # FIX: Use .first to completely prevent the strict mode crash
            sf_page.get_by_role("button", name="Options").first.click()
            sf_page.wait_for_timeout(2000)
            sf_page.get_by_role("link", name="View details").click()
            log_step("18")

            # # sf_page.get_by_role("link", name="IQR").click()
            # # log_step("19")
            # # sf_page.get_by_role("combobox").select_option("1018847904")
            # # log_step("20")

            sf_page.wait_for_timeout(4000)
            sf_page.get_by_role("link", name="IQR").dblclick()
            sf_page.wait_for_timeout(1000)
            # sf_page.get_by_role("cell", name="IQR").first.click()
            # sf_page.wait_for_timeout(2000)
            sf_page.get_by_role("combobox").select_option("1018847904")
            sf_page.wait_for_timeout(20000)

            # sf_page.get_by_role("button", name="Only This Job").click()
            # log_step("21")
            # sf_page.get_by_role("link", name="Jobs", exact=True).click()
            # log_step("22")

            sf_page.get_by_role("link", name="IQR").click()
            log_step("23")
            sf_page.wait_for_timeout(10000)

            return True, f"✅ Processed {len(qualifying_forms)} form(s) and updated Service Fusion for Job ID: {job_id}"

        except Exception as e:
            log_step(f"❌ CRASH: {str(e)}")
            return False, str(e)

        finally:
            log_step("Automation run complete. Cleaning up browser state.")
            context.close()
            browser.close()


# --- STREAMLIT UI ---
st.set_page_config(page_title="Service Automation", page_icon="⚙️")

st.title("Service Automation Portal")
st.write("Fill in the details below to trigger the automation.")

with st.container():
    col1, col2 = st.columns(2)
    with col1:
        job_id_input = st.text_input("Job ID", placeholder="ID")
        account_input = st.text_input("Account Name", placeholder="Enter Account Name")
    with col2:
        location_input = st.text_input("Location (Optional)", placeholder="Enter location (optional)")
        st.write("")
        st.write("")

if st.button("Start Automation", use_container_width=True):
    if not job_id_input or not account_input:
        st.warning("⚠️ Please fill out Job ID and Account Name before starting.")
    else:
        with st.spinner("Browser automation is running... Please check terminal/toasts for logs."):
            success, message = run_automation(account_input, location_input, job_id_input)

            if success:
                st.success(message)
            else:
                st.error(f"❌ Automation failed: {message}")
