from __future__ import annotations

import smtplib
import time
import re
from email.message import EmailMessage
from pathlib import Path
from typing import Any


class EmailSubmitter:
    def __init__(self, host: str, port: int, username: str, password: str, sender: str | None = None) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.sender = sender or username

    def submit(self, job: dict[str, Any], resume: dict[str, Any], materials: dict[str, Any], resume_pdf: str | None = None) -> dict[str, Any]:
        recipient = job.get("application_email")
        if not recipient:
            raise ValueError("Email submission requires application_email on the job")
        message = EmailMessage()
        message["Subject"] = f"Application: {job.get('title', 'Job application')}"
        message["From"] = self.sender
        message["To"] = recipient
        message.set_content(materials.get("cover_letter", ""))
        if resume_pdf:
            path = Path(resume_pdf)
            message.add_attachment(path.read_bytes(), maintype="application", subtype="pdf", filename=path.name)
        server = smtplib.SMTP(self.host, self.port)
        try:
            server.starttls()
            server.login(self.username, self.password)
            server.send_message(message)
        finally:
            server.quit()
        return {"channel": "email", "recipient": recipient}


class PlaywrightSubmitter:
    def __init__(self, browser_factory: Any | None = None) -> None:
        self.browser_factory = browser_factory

    def submit(self, job: dict[str, Any], resume: dict[str, Any], materials: dict[str, Any], resume_pdf: str | None = None) -> dict[str, Any]:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(job["url"], wait_until="domcontentloaded")
                fields = resume.get("contact", {})
                for selector, value in {
                    "input[name='name']": fields.get("name", ""),
                    "input[name='email']": fields.get("email", ""),
                    "textarea[name='cover_letter']": materials.get("cover_letter", ""),
                }.items():
                    if value and page.locator(selector).count():
                        page.locator(selector).first.fill(value)
                if resume_pdf and page.locator("input[type='file']").count():
                    page.locator("input[type='file']").first.set_input_files(resume_pdf)
                page.locator("button[type='submit'], input[type='submit']").first.click()
                return {"channel": "playwright", "url": job["url"]}
            finally:
                browser.close()


class GreenhouseSubmitter:
    def __init__(self, profile_dir: str = "runtime/greenhouse-browser", headless: bool = False, login_url: str = "https://my.greenhouse.io/dashboard", login_wait_seconds: int = 120, post_submit_hold_seconds: int = 0) -> None:
        self.profile_dir = profile_dir
        self.headless = headless
        self.login_url = login_url
        self.login_wait_seconds = login_wait_seconds
        self.post_submit_hold_seconds = post_submit_hold_seconds

    @staticmethod
    def _value(profile: dict[str, Any], key: str) -> str:
        value = profile.get(key, "")
        return str(value) if value is not None else ""

    def _ensure_login(self, page: Any) -> None:
        print(f"[greenhouse] opening candidate session: {self.login_url}", flush=True)
        page.goto(self.login_url, wait_until="domcontentloaded")
        if "login" not in page.url.lower() and "sign" not in page.url.lower():
            print(f"[greenhouse] session ready: {page.url}", flush=True)
            return
        print("[greenhouse] login/MFA required; complete it in the visible browser", flush=True)
        deadline = time.monotonic() + self.login_wait_seconds
        while time.monotonic() < deadline:
            if "login" not in page.url.lower() and "sign" not in page.url.lower():
                print(f"[greenhouse] login completed: {page.url}", flush=True)
                return
            page.wait_for_timeout(1000)
        raise TimeoutError("Greenhouse login was not completed within the configured wait time")

    @staticmethod
    def _fill(page: Any, labels: tuple[str, ...], value: str) -> bool:
        if not value:
            return False
        for label in labels:
            locator = page.get_by_label(label, exact=True)
            candidates = [locator, locator.locator("input, textarea, select, [contenteditable='true']")]
            for candidate in candidates:
                if candidate.count() and candidate.first.is_editable():
                    candidate.first.fill(value)
                    return True
        return False

    def _fill_application(self, page: Any, profile: dict[str, Any], materials: dict[str, Any], resume_pdf: str | None) -> list[str]:
        print(f"[greenhouse] application form: {page.url}", flush=True)
        contact = profile.get("contact", {})
        self._fill_selector(page, "#first_name", self._value(contact, "first_name"))
        self._fill_selector(page, "#last_name", self._value(contact, "last_name"))
        self._fill_selector(page, "#email", self._value(contact, "email"))
        self._fill_selector(page, "#phone", self._value(contact, "phone"))
        self._fill_selector(page, "#question_67488743", self._value(profile, "linkedin_url"))
        self._fill_selector(page, "#company-name-0", self._value((profile.get("employment_history") or [{}])[0], "company"))
        self._fill_selector(page, "#title-0", self._value((profile.get("employment_history") or [{}])[0], "title"))
        self._fill_selector(page, "#start-date-year-0", self._value((profile.get("employment_history") or [{}])[0], "start_year"))
        self._fill_selector(page, "#end-date-year-0", self._value((profile.get("employment_history") or [{}])[0], "end_year"))
        self._choose_option(page, "#start-date-month-0", self._value((profile.get("employment_history") or [{}])[0], "start_month"))
        self._choose_option(page, "#end-date-month-0", self._value((profile.get("employment_history") or [{}])[0], "end_month"))
        self._fill_selector(page, "#candidate-location", self._value(profile, "location"))
        self._choose_option(page, "#country", self._value(profile, "country"))
        education = (profile.get("education_history") or [{}])[0]
        self._fill_selector(page, "#school--0", self._value(education, "school"))
        self._fill_selector(page, "#degree--0", self._value(education, "degree"))
        self._fill_selector(page, "#discipline--0", self._value(education, "discipline"))
        answers = profile.get("answers", {})
        question_answers = {
            "#question_67488744": answers.get("age_18_or_older"),
            "#question_67488745": answers.get("previously_employed_by_company"),
            "#question_67488746": answers.get("how_heard_about_job"),
            "#question_67488747": answers.get("privacy_notice_and_arbitration_acknowledged"),
            "#question_67488748": answers.get("ai_tools_in_application_process_acknowledged"),
            "#question_67488749": answers.get("ai_tools_usage"),
            "#question_67488750": answers.get("legally_authorized_to_work"),
            "#question_67488751": answers.get("requires_sponsorship_now_or_future"),
            "#question_67488752": answers.get("government_official_or_recently"),
            "#question_67488753": answers.get("relative_is_government_official"),
            "#question_67488754": answers.get("conflict_of_interest"),
            "#question_67488755": answers.get("referred_by_client_or_partner"),
        }
        for selector, answer in question_answers.items():
            self._choose_option(page, selector, self._value({"value": answer}, "value"))
            self._choose_first_unknown_options(page)
        values = {
            ("name", "full name"): self._value(contact, "name"),
            ("email", "email address"): self._value(contact, "email"),
            ("phone", "phone number"): self._value(contact, "phone"),
            ("city", "location"): self._value(profile, "location"),
            ("linkedin", "linkedin profile"): self._value(profile, "linkedin_url"),
            ("website", "portfolio"): self._value(profile, "website_url"),
            ("cover letter",): self._value(materials, "cover_letter"),
        }
        missing = ["resume"]
        for labels, value in values.items():
            self._fill(page, labels, value)
        file_input = page.locator("input[type='file']")
        print(f"[greenhouse] resume inputs found: {file_input.count()}", flush=True)
        if resume_pdf and file_input.count():
            file_input.first.set_input_files(resume_pdf)
            missing = []
            print(f"[greenhouse] resume uploaded: {resume_pdf}", flush=True)
        elif resume_pdf:
            print(f"[greenhouse] resume upload control not found: {resume_pdf}", flush=True)
        required_empty = page.locator("input[required]:not([aria-hidden='true']), textarea[required]:not([aria-hidden='true']), select[required]:not([aria-hidden='true'])")
        for index in range(required_empty.count()):
            field = required_empty.nth(index)
            if not field.input_value().strip():
                missing.append(field.get_attribute("name") or field.get_attribute("aria-label") or f"required_field_{index}")
        missing_fields = sorted(set(missing))
        print(f"[greenhouse] missing visible required fields: {missing_fields or 'none'}", flush=True)
        return missing_fields

    @staticmethod
    def _fill_selector(page: Any, selector: str, value: str) -> bool:
        if not value:
            return False
        locator = page.locator(selector).first
        if not locator.count() or not locator.is_editable():
            return False
        locator.fill(value)
        locator.press("Tab")
        return True

    @staticmethod
    def _choose_option(page: Any, selector: str, value: str) -> bool:
        if not value:
            return False
        control = page.locator(selector).first
        if not control.count():
            return False
        parent_text = " ".join(control.locator("xpath=..").inner_text().split())
        if value.lower() in parent_text.lower() and "select" not in parent_text.lower():
            return True
        try:
            control.click()
        except Exception:
            try:
                control.locator("xpath=..").click()
            except Exception:
                return False
        page.wait_for_timeout(250)
        def normalize(text: str) -> str:
            return re.sub(r"[^a-z0-9]", "", text.lower())

        options = page.locator("[role='option']:visible")
        for index in range(options.count()):
            option = options.nth(index)
            if normalize(option.inner_text()) == normalize(value):
                try:
                    option.click(timeout=5000)
                    return True
                except Exception:
                    return False
        first_option = page.locator("[role='option']:visible").first
        if first_option.count():
            try:
                print(f"[greenhouse] configured option not found for {selector}; choosing first visible option", flush=True)
                first_option.click(timeout=5000)
                return True
            except Exception:
                return False
        page.keyboard.press("Escape")
        return False

    @staticmethod
    def _choose_first_unknown_options(page: Any) -> None:
        controls = page.locator("input[role='combobox'][aria-required='true']:visible")
        for index in range(controls.count()):
            control = controls.nth(index)
            container_text = " ".join(control.locator("xpath=../..").inner_text().split())
            if "select..." not in container_text.lower():
                continue
            try:
                control.click()
                page.wait_for_timeout(150)
                option = page.locator("[role='option']:visible").first
                if option.count():
                    print(f"[greenhouse] unknown dropdown {control.get_attribute('id')}; choosing first option: {option.inner_text().strip()}", flush=True)
                    option.click(timeout=5000)
                else:
                    page.keyboard.press("Escape")
            except Exception as error:
                print(f"[greenhouse] could not choose fallback for {control.get_attribute('id')}: {type(error).__name__}", flush=True)

    @staticmethod
    @staticmethod
    def _application_url(job: dict[str, Any]) -> str | None:
        board_token = job.get("greenhouse_board_token")
        job_id = job.get("greenhouse_job_id")
        if board_token and job_id:
            return f"https://job-boards.greenhouse.io/embed/job_app?token={job_id}&for={board_token}&gh_jid={job_id}"
        return None

    def _open_application_form(self, page: Any, job: dict[str, Any]) -> None:
        if page.locator("input[type='file'], form").count():
            print(f"[greenhouse] application form already present: {page.url}", flush=True)
            return
        direct_url = self._application_url(job)
        if direct_url:
            print(f"[greenhouse] opening direct embedded form: {direct_url}", flush=True)
            page.goto(direct_url, wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(1500)
            print(f"[greenhouse] direct form ready: {page.url}", flush=True)
            return
        embedded_link = page.locator("a[href*='/embed/job_app']").first
        if embedded_link.count():
            application_url = embedded_link.get_attribute("href")
            if application_url:
                page.goto(application_url, wait_until="domcontentloaded")
                page.wait_for_timeout(1500)
                print(f"[greenhouse] opened embedded application form: {page.url}", flush=True)
                return
        candidates = [
            page.get_by_role("button", name="Apply now", exact=True),
            page.get_by_role("link", name="Apply now", exact=True),
            page.get_by_text("Apply now", exact=True),
        ]
        for candidate in candidates:
            if candidate.count():
                candidate.first.click()
                page.wait_for_timeout(1500)
                print(f"[greenhouse] clicked Apply now; current page: {page.url}", flush=True)
                return
        raise ValueError("Could not find the Greenhouse Apply now control")

    def _open(self) -> tuple[Any, Any, Any]:
        from playwright.sync_api import sync_playwright

        playwright = sync_playwright().start()
        context = playwright.chromium.launch_persistent_context(self.profile_dir, headless=self.headless)
        page = context.pages[0] if context.pages else context.new_page()
        self._ensure_login(page)
        return playwright, context, page

    @staticmethod
    def _save_evidence(page: Any, name: str) -> dict[str, str]:
        directory = Path("runtime")
        directory.mkdir(parents=True, exist_ok=True)
        screenshot = directory / f"greenhouse-{name}.png"
        html = directory / f"greenhouse-{name}.html"
        page.screenshot(path=str(screenshot), full_page=True)
        html.write_text(page.content(), encoding="utf-8")
        print(f"[greenhouse] evidence screenshot: {screenshot}", flush=True)
        print(f"[greenhouse] evidence HTML: {html}", flush=True)
        return {"screenshot": str(screenshot), "html": str(html)}

    @staticmethod
    def _page_text(page: Any) -> str:
        return " ".join(page.locator("body").inner_text(timeout=5000).split()).lower()

    def _manual_post_submit_hold(self, page: Any) -> None:
        if self.post_submit_hold_seconds <= 0:
            return
        print(f"[greenhouse] browser held open for {self.post_submit_hold_seconds}s; complete any OTP or human verification now", flush=True)
        deadline = time.monotonic() + self.post_submit_hold_seconds
        while time.monotonic() < deadline:
            remaining = max(0, int(deadline - time.monotonic()))
            print(f"[greenhouse] manual verification window: {remaining}s; current text: {self._page_text(page)[:500]}", flush=True)
            page.wait_for_timeout(2000)

    @staticmethod
    def _validation_messages(page: Any) -> list[str]:
        messages: list[str] = []
        for locator in page.locator("[aria-invalid='true']").all():
            if not locator.is_visible():
                continue
            error_id = locator.get_attribute("aria-errormessage")
            if error_id:
                error = page.locator(f"#{error_id}")
                if error.count() and error.first.is_visible():
                    messages.append(" ".join(error.first.inner_text().split()))
        for locator in page.locator("[role='alert'], [id$='-error']").all():
            if locator.is_visible():
                text = " ".join(locator.inner_text().split())
                if text:
                    messages.append(text)
        return list(dict.fromkeys(messages))

    def prepare(self, job: dict[str, Any], profile: dict[str, Any], materials: dict[str, Any], resume_pdf: str | None = None) -> dict[str, Any]:
        playwright, context, page = self._open()
        try:
            try:
                page.goto(job["url"], wait_until="domcontentloaded", timeout=15000)
            except Exception as error:
                print(f"[greenhouse] public job navigation failed, using direct form: {type(error).__name__}", flush=True)
            self._open_application_form(page, job)
            missing = self._fill_application(page, profile, materials, resume_pdf)
            screenshot = str(Path("runtime") / f"greenhouse-review-{job.get('greenhouse_job_id', 'job')}.png")
            Path(screenshot).parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=screenshot, full_page=True)
            return {"channel": "greenhouse", "status": "awaiting_final_review" if not missing else "needs_manual_fields", "missing_fields": missing, "screenshot": screenshot, "url": job["url"]}
        finally:
            context.close()
            playwright.stop()

    def submit(self, job: dict[str, Any], profile: dict[str, Any], materials: dict[str, Any], resume_pdf: str | None = None) -> dict[str, Any]:
        playwright, context, page = self._open()
        try:
            try:
                page.goto(job["url"], wait_until="domcontentloaded", timeout=15000)
            except Exception as error:
                print(f"[greenhouse] public job navigation failed, using direct form: {type(error).__name__}", flush=True)
            self._open_application_form(page, job)
            missing = self._fill_application(page, profile, materials, resume_pdf)
            if missing:
                evidence = self._save_evidence(page, f"failed-{job.get('greenhouse_job_id', 'job')}")
                raise ValueError(f"Required Greenhouse fields are incomplete: {', '.join(missing)}")
            submit = page.locator("button[type='submit'], input[type='submit']").first
            if not submit.count():
                raise ValueError("Could not find the Greenhouse final submit control")
            print("[greenhouse] clicking final submit", flush=True)
            submit.click()
            page.wait_for_timeout(2000)
            self._manual_post_submit_hold(page)
            page.wait_for_timeout(1000)
            body_text = self._page_text(page)
            validation_messages = self._validation_messages(page)
            evidence = self._save_evidence(page, f"after-submit-{job.get('greenhouse_job_id', 'job')}")
            print(f"[greenhouse] post-submit URL: {page.url}", flush=True)
            print(f"[greenhouse] post-submit text: {body_text[:1000]}", flush=True)
            print(f"[greenhouse] validation messages: {validation_messages or 'none'}", flush=True)
            success_markers = (
                "thanks for applying",
                "application has been submitted",
                "application submitted",
                "thank you for applying",
            )
            error_markers = ("there was an error", "please correct", "required field", "captcha")
            if not any(marker in body_text for marker in success_markers):
                reason = "Greenhouse confirmation was not detected after submit"
                if any(marker in body_text for marker in error_markers):
                    reason += "; the form still shows a validation or submission error"
                if validation_messages:
                    reason += f"; fields: {' | '.join(validation_messages[:20])}"
                raise RuntimeError(f"{reason}. Evidence: {evidence['screenshot']}")
            print("[greenhouse] confirmed: application submitted by Greenhouse", flush=True)
            return {"channel": "greenhouse", "status": "submitted", "url": page.url, **evidence}
        finally:
            context.close()
            playwright.stop()