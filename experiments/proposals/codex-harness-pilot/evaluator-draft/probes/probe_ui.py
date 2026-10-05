"""Pre-check that the planted UI defects reproduce and normal flows work.

Usage: python probe_ui.py <baselines-dir>. Set PW_CHROMIUM to use a specific
Chromium binary. Not a grader: it prints observations for a human to read.
"""
import os, subprocess, sys, tempfile, json
from playwright.sync_api import sync_playwright
B = sys.argv[1]

def start(project, module, port):
    d = tempfile.mkdtemp()
    proc = subprocess.Popen([sys.executable, "-m", module, "--db", os.path.join(d, "x.db"), "--init", "--port", str(port)],
                            cwd=f"{B}/{project}", stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    proc.stdout.readline()
    return proc

it = start("issue-tracker", "app.server", 8811)
ev = start("event-signup", "app", 8812)
errors = []
try:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=os.environ.get("PW_CHROMIUM") or None)
        page = browser.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: m.type == "error" and errors.append(m.text))

        base = "http://127.0.0.1:8811"
        page.goto(base + "/?project=CORE"); page.wait_for_selector(".issue")
        print("IT list count:", page.locator(".issue").count(), "| header:", page.text_content("#project-name"), "|", page.text_content("#user-name"))
        page.select_option("#status-filter", "open"); page.wait_for_timeout(300)
        print("IT after filter: url =", page.url.split("8811")[1], "| count =", page.locator(".issue").count())
        page.reload(); page.wait_for_selector(".issue"); page.wait_for_timeout(300)
        print("IT after reload: url =", page.url.split("8811")[1], "| control =", repr(page.input_value("#status-filter")), "| count =", page.locator(".issue").count())
        page.click(".issue >> nth=0 >> a"); page.wait_for_selector("#issue:not([hidden])")
        print("IT detail:", page.text_content("#issue-title"))
        page.select_option("#status-select", "open"); page.click("#status-form button"); page.wait_for_timeout(300)
        page.go_back(); page.wait_for_selector(".issue"); page.wait_for_timeout(300)
        print("IT after back: control =", repr(page.input_value("#status-filter")), "| count =", page.locator(".issue").count())

        base = "http://127.0.0.1:8812"
        page.goto(base + "/"); page.wait_for_selector(".event-card")
        print("EV events:", [t.strip() for t in page.locator(".seats").all_text_contents()])
        page.goto(base + "/event.html?slug=design-clinic"); page.wait_for_selector("#signup-form:not([hidden])")
        values = {"#name": "Dana", "#email": "dana@example.com", "#affiliation": "Umbrella", "#note": "Wheelchair access"}
        for sel, v in values.items(): page.fill(sel, v)
        page.route("**/api/events/design-clinic/registrations", lambda route: route.fulfill(status=503, content_type="application/json", body=json.dumps({"detail": "unavailable", "code": "unavailable"})))
        page.click("#submit-button"); page.wait_for_timeout(300)
        print("EV after 503: fields =", {s: page.input_value(s) for s in values}, "| error =", page.text_content("#form-error"), "| button disabled =", page.is_disabled("#submit-button"))
        page.unroute("**/api/events/design-clinic/registrations")
        page.reload(); page.wait_for_selector("#signup-form:not([hidden])")
        for sel, v in values.items(): page.fill(sel, v)
        page.click("#submit-button"); page.wait_for_selector("#confirmation:not([hidden])")
        print("EV success:", page.text_content("#confirmation-title"), "| seats:", page.text_content("#event-seats"), "| button disabled =", page.is_disabled("#submit-button"))
        page.click("#manage-link"); page.wait_for_selector("#registration:not([hidden])")
        page.click("#cancel-button"); page.wait_for_timeout(300)
        print("EV registration after cancel:", page.text_content("#registration-state"))
        browser.close()
finally:
    it.terminate(); ev.terminate()
print("JS errors:", [e for e in errors if "503" not in e])
