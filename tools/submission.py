from __future__ import annotations

import smtplib
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