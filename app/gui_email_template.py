"""
EmailTemplateMixin — email template editor and SMTP configuration tab.
"""

import glob
import json
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk

import pandas as pd

from app.app_paths import CONFIG_FILE, _DATA_ROOT

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]


class EmailTemplateMixin:
    """Mixin providing the Email Template tab (editor, SMTP config, preview)."""

    # ------------------------------------------------------------------
    # Tab creation
    # ------------------------------------------------------------------

    def create_email_template_tab(self, parent):
        """Create email template editing tab"""
        # Template editor frame
        editor_frame = ttk.LabelFrame(parent, text="Email Template Editor", padding=10)
        editor_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N), padx=10, pady=10)

        # Subject line
        ttk.Label(editor_frame, text="Subject:").grid(
            row=0, column=0, sticky=tk.W, pady=5
        )
        self.email_subject_var = tk.StringVar(
            value="Your Resilience Scan Report \u2013 {company}"
        )
        ttk.Entry(editor_frame, textvariable=self.email_subject_var, width=60).grid(
            row=0, column=1, sticky=(tk.W, tk.E), padx=10, pady=5
        )

        # Template help
        help_text = "Available placeholders: {name}, {company}, {date}"
        ttk.Label(
            editor_frame, text=help_text, font=("Arial", 8), foreground="gray"
        ).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=5)

        # Body editor
        ttk.Label(editor_frame, text="Email Body:").grid(
            row=2, column=0, sticky=(tk.W, tk.N), pady=5
        )

        body_scroll = ttk.Scrollbar(editor_frame)
        body_scroll.grid(row=2, column=2, sticky=(tk.N, tk.S), pady=5)

        self.email_body_text = scrolledtext.ScrolledText(
            editor_frame,
            wrap=tk.WORD,
            width=70,
            height=12,
            font=("Arial", 10),
            yscrollcommand=body_scroll.set,
        )
        self.email_body_text.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=10, pady=5)
        body_scroll.config(command=self.email_body_text.yview)

        # Default template
        default_body = (
            "Dear {name},\n\n"
            "Please find attached your resilience scan report for {company}.\n\n"
            "If you have any questions, feel free to reach out.\n\n"
            "Best regards,\n\n"
            "[Your Name]\n"
            "[Your Organization]"
        )
        self.email_body_text.insert("1.0", default_body)

        # Buttons
        btn_frame = ttk.Frame(editor_frame)
        btn_frame.grid(row=3, column=0, columnspan=3, pady=10)

        ttk.Button(
            btn_frame,
            text="\U0001f4be Save Template",
            command=self.save_email_template,
            width=15,
        ).grid(row=0, column=0, padx=5)

        ttk.Button(
            btn_frame,
            text="[RESET] Reset to Default",
            command=self.reset_email_template,
            width=18,
        ).grid(row=0, column=1, padx=5)

        ttk.Button(
            btn_frame,
            text="\U0001f441\ufe0f Preview Email",
            command=self.preview_email,
            width=15,
        ).grid(row=0, column=2, padx=5)

        # SMTP Configuration Section
        smtp_frame = ttk.LabelFrame(
            parent, text="SMTP Server Configuration", padding=10
        )
        smtp_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), padx=10, pady=10)

        # SMTP Server
        ttk.Label(smtp_frame, text="SMTP Server:").grid(
            row=0, column=0, sticky=tk.W, pady=5
        )
        self.smtp_server_var = tk.StringVar(value="smtp.office365.com")
        ttk.Entry(smtp_frame, textvariable=self.smtp_server_var, width=40).grid(
            row=0, column=1, sticky=(tk.W, tk.E), padx=10, pady=5
        )

        # SMTP Port
        ttk.Label(smtp_frame, text="SMTP Port:").grid(
            row=1, column=0, sticky=tk.W, pady=5
        )
        self.smtp_port_var = tk.StringVar(value="587")
        ttk.Entry(smtp_frame, textvariable=self.smtp_port_var, width=10).grid(
            row=1, column=1, sticky=tk.W, padx=10, pady=5
        )

        # From Email
        ttk.Label(smtp_frame, text="From Email:").grid(
            row=2, column=0, sticky=tk.W, pady=5
        )
        self.smtp_from_var = tk.StringVar(value="info@resiliencescan.org")
        from_entry = ttk.Entry(
            smtp_frame, textvariable=self.smtp_from_var, width=40, state="readonly"
        )
        from_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=10, pady=5)

        # SMTP Username
        ttk.Label(smtp_frame, text="SMTP Username:").grid(
            row=3, column=0, sticky=tk.W, pady=5
        )
        self.smtp_username_var = tk.StringVar(value="")
        ttk.Entry(smtp_frame, textvariable=self.smtp_username_var, width=40).grid(
            row=3, column=1, sticky=(tk.W, tk.E), padx=10, pady=5
        )

        # SMTP Password
        ttk.Label(smtp_frame, text="SMTP Password:").grid(
            row=4, column=0, sticky=tk.W, pady=5
        )
        self.smtp_password_var = tk.StringVar(value="")
        ttk.Entry(
            smtp_frame, textvariable=self.smtp_password_var, width=40, show="*"
        ).grid(row=4, column=1, sticky=(tk.W, tk.E), padx=10, pady=5)

        # Help text
        help_text = (
            "Gmail: smtp.gmail.com:587 (use app-specific password)\n"
            "Office365: smtp.office365.com:587\n"
            "Outlook.com: smtp-mail.outlook.com:587"
        )
        ttk.Label(
            smtp_frame, text=help_text, font=("Arial", 8), foreground="gray"
        ).grid(row=5, column=0, columnspan=2, sticky=tk.W, pady=5)

        ttk.Button(
            smtp_frame, text="Save Configuration", command=self.save_config
        ).grid(row=6, column=0, columnspan=2, sticky=tk.W, pady=5)

        smtp_frame.columnconfigure(1, weight=1)

        editor_frame.columnconfigure(1, weight=1)

        # Preview frame
        preview_frame = ttk.LabelFrame(parent, text="Email Preview", padding=10)
        preview_frame.grid(
            row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=10
        )

        self.email_preview_text = scrolledtext.ScrolledText(
            preview_frame,
            wrap=tk.WORD,
            width=80,
            height=15,
            font=("Courier", 9),
            state=tk.DISABLED,
        )
        self.email_preview_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)

        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        # Load saved template if exists
        self.load_email_template()

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------

    def save_config(self):
        """Save SMTP settings from GUI fields to config.yml."""
        if yaml is None:
            messagebox.showerror(
                "Error", "PyYAML is not installed — cannot save configuration."
            )
            return
        try:
            port = int(self.smtp_port_var.get() or 587)
        except ValueError:
            messagebox.showerror(
                "Invalid Port", "SMTP port must be a number (e.g. 587)."
            )
            return
        data = {
            "smtp": {
                "server": self.smtp_server_var.get(),
                "port": port,
                "from_address": self.smtp_from_var.get(),
                "username": self.smtp_username_var.get(),
                "password": self.smtp_password_var.get(),
            }
        }
        try:
            CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            CONFIG_FILE.write_text(
                yaml.dump(data, default_flow_style=False, allow_unicode=True),
                encoding="utf-8",
            )
            messagebox.showinfo("Saved", f"Configuration saved to:\n{CONFIG_FILE}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save configuration:\n{e}")

    def load_config(self):
        """Load SMTP settings from config.yml into GUI fields."""
        if yaml is None:
            self.log("[WARNING] PyYAML not installed — cannot load config.yml")
            return
        if not CONFIG_FILE.exists():
            return
        try:
            data = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8")) or {}
            smtp = data.get("smtp", {})
            if smtp.get("server"):
                self.smtp_server_var.set(smtp["server"])
            if smtp.get("port"):
                self.smtp_port_var.set(str(smtp["port"]))
            if smtp.get("from_address"):
                self.smtp_from_var.set(smtp["from_address"])
            if smtp.get("username"):
                self.smtp_username_var.set(smtp["username"])
            if smtp.get("password"):
                self.smtp_password_var.set(smtp["password"])
            # Load Outlook account priority list (empty list = use default account)
            self.outlook_accounts = data.get("outlook_accounts", [])
        except Exception as e:
            self.log(f"[WARNING] Could not load config.yml: {e}")

    # ------------------------------------------------------------------
    # Email template methods
    # ------------------------------------------------------------------

    def save_email_template(self):
        """Save email template to file"""
        try:
            template_data = {
                "subject": self.email_subject_var.get(),
                "body": self.email_body_text.get("1.0", tk.END).strip(),
            }

            template_file = _DATA_ROOT / "email_template.json"
            with open(template_file, "w", encoding="utf-8") as f:
                json.dump(template_data, f, indent=2)

            self.log("[OK] Email template saved")
            messagebox.showinfo("Success", "Email template saved successfully!")

        except Exception as e:
            self.log(f"[ERROR] Error saving template: {e}")
            messagebox.showerror("Error", f"Failed to save template:\n{e}")

    def load_email_template(self):
        """Load email template from file"""
        try:
            template_file = _DATA_ROOT / "email_template.json"
            if template_file.exists():
                with open(template_file, encoding="utf-8") as f:
                    template_data = json.load(f)

                self.email_subject_var.set(
                    template_data.get(
                        "subject", "Your Resilience Scan Report \u2013 {company}"
                    )
                )
                self.email_body_text.delete("1.0", tk.END)
                self.email_body_text.insert("1.0", template_data.get("body", ""))

                self.log("[OK] Email template loaded")
        except Exception as e:
            self.log(f"[WARNING] Could not load template: {e}")

    def reset_email_template(self):
        """Reset to default template"""
        default_subject = "Your Resilience Scan Report \u2013 {company}"
        default_body = (
            "Dear {name},\n\n"
            "Please find attached your resilience scan report for {company}.\n\n"
            "If you have any questions, feel free to reach out.\n\n"
            "Best regards,\n\n"
            "[Your Name]\n"
            "[Your Organization]"
        )

        self.email_subject_var.set(default_subject)
        self.email_body_text.delete("1.0", tk.END)
        self.email_body_text.insert("1.0", default_body)

        self.log("[RESET] Email template reset to default")
        messagebox.showinfo("Reset", "Template reset to default!")

    def preview_email(self):
        """Preview email with sample data"""
        if self.df is None or len(self.df) == 0:
            messagebox.showwarning(
                "No Data", "Please load data first to preview emails."
            )
            return

        # Get first row as sample
        sample_row = self.df.iloc[0]
        sample_company = sample_row.get("company_name", "Example Company")
        sample_name = sample_row.get("name", "John Doe")
        sample_email = sample_row.get("email_address", "john.doe@example.com")

        # Get template
        subject_template = self.email_subject_var.get()
        body_template = self.email_body_text.get("1.0", tk.END).strip()

        # Replace placeholders
        sample_date = datetime.now().strftime("%Y-%m-%d")

        subject = subject_template.format(
            company=sample_company, name=sample_name, date=sample_date
        )

        body = body_template.format(
            company=sample_company, name=sample_name, date=sample_date
        )

        # Find report file
        def safe_display_name(name):
            if pd.isna(name) or name == "":
                return "Unknown"
            name_str = str(name).strip()
            name_str = name_str.replace("/", "-")
            name_str = name_str.replace("\\", "-")
            name_str = name_str.replace(":", "-")
            return name_str

        display_company = safe_display_name(sample_company)
        display_person = safe_display_name(sample_name)

        # Look for report file - try both formats
        pattern_new = (
            f"*ResilienceScanReport ({display_company} - {display_person}).pdf"
        )
        pattern_legacy = f"*ResilienceReport ({display_company} - {display_person}).pdf"
        _out_dir = Path(self.output_folder_var.get())
        matches = glob.glob(str(_out_dir / pattern_new))
        if not matches:
            matches = glob.glob(str(_out_dir / pattern_legacy))

        attachment_info = ""
        if matches:
            attachment_file = Path(matches[0])
            file_size = attachment_file.stat().st_size / (1024 * 1024)  # MB
            attachment_info = (
                f"\n[ATTACH] Attachment: {attachment_file.name} ({file_size:.2f} MB)"
            )
        else:
            attachment_info = (
                f"\n[WARNING] No report found for {display_company} - {display_person}"
            )

        # Build preview
        preview = "=" * 70 + "\n"
        preview += "EMAIL PREVIEW\n"
        preview += "=" * 70 + "\n\n"
        preview += f"To: {sample_email}\n"
        preview += f"Subject: {subject}\n"
        preview += attachment_info + "\n"
        preview += "\n" + "-" * 70 + "\n"
        preview += "MESSAGE BODY:\n"
        preview += "-" * 70 + "\n\n"
        preview += body
        preview += "\n\n" + "=" * 70 + "\n"
        preview += "This is a preview using the first record from your data.\n"
        preview += f"Sample: {sample_company} - {sample_name}\n"
        preview += "=" * 70

        # Display preview
        self.email_preview_text.config(state=tk.NORMAL)
        self.email_preview_text.delete("1.0", tk.END)
        self.email_preview_text.insert("1.0", preview)
        self.email_preview_text.config(state=tk.DISABLED)

        self.log("[PREVIEW] Email preview generated")
