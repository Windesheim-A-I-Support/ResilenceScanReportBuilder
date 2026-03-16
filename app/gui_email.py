"""
EmailMixin — email template editor, email sending tab, and all email methods.
"""

import glob
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import pandas as pd

from app.app_paths import DATA_FILE
from app.gui_email_send import EmailSendMixin
from app.gui_email_template import EmailTemplateMixin


class EmailMixin(EmailTemplateMixin, EmailSendMixin):
    """Mixin providing the Email tabs: combines EmailTemplateMixin, EmailSendMixin, and tracker/status display."""

    # ------------------------------------------------------------------
    # Tab creation
    # ------------------------------------------------------------------

    def create_email_tab(self):
        """Create email distribution tab"""
        email_tab = ttk.Frame(self.notebook)
        self.notebook.add(email_tab, text="\U0001f4e7 Email")

        # Create notebook for email tab sections
        email_notebook = ttk.Notebook(email_tab)
        email_notebook.grid(
            row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5
        )

        # Email Template Tab
        template_tab = ttk.Frame(email_notebook)
        email_notebook.add(template_tab, text="\u2709\ufe0f Template")

        # Email Sending Tab
        sending_tab = ttk.Frame(email_notebook)
        email_notebook.add(sending_tab, text="\U0001f4e4 Send Emails")

        email_tab.columnconfigure(0, weight=1)
        email_tab.rowconfigure(0, weight=1)

        # Build template tab
        self.create_email_template_tab(template_tab)

        # Build sending tab (move existing content here)
        self.create_email_sending_tab(sending_tab)

    # ------------------------------------------------------------------
    # Email status display
    # ------------------------------------------------------------------

    def update_email_status_display(self):
        """Update email status treeview - ONLY shows companies with generated PDF reports"""
        # Load CSV data if not already loaded
        if self.df is None and DATA_FILE.exists():
            try:
                self.df = pd.read_csv(DATA_FILE, encoding="utf-8")
                self.df.columns = self.df.columns.str.lower().str.strip()
                self.log_email("[LOAD] Loaded CSV data for email display")
            except Exception as e:
                self.log_email(f"[WARNING] Could not load CSV: {e}")

        # Clear existing items
        for item in self.email_status_tree.get_children():
            self.email_status_tree.delete(item)

        # Scan output folder for PDF files
        _out_dir = Path(self.output_folder_var.get())
        report_files = glob.glob(str(_out_dir / "*.pdf"))

        if not report_files:
            self.log_email(f"[INFO] No PDF reports found in {_out_dir}")
            self.email_stats_label.config(
                text="No PDF reports found - generate reports first"
            )
            return

        # Parse PDF filenames to extract company and person info
        # Format: YYYYMMDD ResilienceScanReport (COMPANY - PERSON).pdf
        reports_ready = []

        for pdf_path in report_files:
            filename = Path(pdf_path).name

            # Extract company and person from filename
            # Format: YYYYMMDD ResilienceScanReport (COMPANY NAME - Firstname Lastname).pdf
            # Also support legacy format: YYYYMMDD ResilienceReport (COMPANY NAME - Firstname Lastname).pdf
            try:
                content = None
                # Try new format first
                if "ResilienceScanReport (" in filename and ").pdf" in filename:
                    content = filename.split("ResilienceScanReport (")[1].split(
                        ").pdf"
                    )[0]
                # Fallback to legacy format
                elif "ResilienceReport (" in filename and ").pdf" in filename:
                    content = filename.split("ResilienceReport (")[1].split(").pdf")[0]

                if content and " - " in content:
                    # Split by " - " to get company and person
                    company, person = content.rsplit(" - ", 1)

                    # Look up email address from CSV data
                    email = ""
                    if self.df is not None:
                        # Find matching record
                        matches = self.df[
                            (self.df["company_name"].str.strip() == company.strip())
                            & (self.df["name"].str.strip() == person.strip())
                        ]
                        if not matches.empty:
                            email = matches.iloc[0].get("email_address", "")

                    # Check status: prefer email_tracker (updated by send thread,
                    # reflects test-mode sends) then fall back to CSV reportsent.
                    tracker_key = f"{company.strip()}|{person.strip()}"
                    tracker_entry = self.email_tracker._recipients.get(tracker_key)
                    if tracker_entry:
                        sent_status = tracker_entry["status"]  # pending/sent/failed
                    else:
                        sent_status = "pending"
                        if self.df is not None:
                            matches = self.df[
                                (self.df["company_name"].str.strip() == company.strip())
                                & (self.df["name"].str.strip() == person.strip())
                            ]
                            if not matches.empty and "reportsent" in self.df.columns:
                                is_sent = matches.iloc[0].get("reportsent", False)
                                if is_sent:
                                    sent_status = "sent"

                    reports_ready.append(
                        {
                            "company": company,
                            "person": person,
                            "email": email,
                            "status": sent_status,
                            "pdf_path": pdf_path,
                        }
                    )
            except Exception as e:
                self.log_email(f"[WARNING] Could not parse filename: {filename} - {e}")
                continue

        # Update statistics
        total = len(reports_ready)
        pending = sum(1 for r in reports_ready if r["status"] == "pending")
        sent = sum(1 for r in reports_ready if r["status"] == "sent")
        failed = sum(1 for r in reports_ready if r["status"] == "failed")

        self.email_stats_label.config(
            text=f"Reports Ready: {total} | Pending: {pending} | Sent: {sent} | Failed: {failed}"
        )

        # Get filter value
        filter_status = self.email_filter_var.get()

        # Display reports
        for report in reports_ready:
            # Apply filter
            if filter_status != "all" and report["status"] != filter_status:
                continue

            # Insert into tree with tag for color coding
            values = (
                report["company"],
                report["person"],
                report["email"] if report["email"] else "NO EMAIL",
                report["status"].upper(),
                "",  # No date for pending
                "",  # No mode needed
            )

            item = self.email_status_tree.insert("", tk.END, values=values)

            # Color code by status
            if report["status"] == "sent":
                self.email_status_tree.item(item, tags=("sent",))
            else:
                self.email_status_tree.item(item, tags=("pending",))

        # Configure tag colors
        self.email_status_tree.tag_configure("sent", foreground="green")
        self.email_status_tree.tag_configure("pending", foreground="orange")

    # ------------------------------------------------------------------
    # Mark sent / pending
    # ------------------------------------------------------------------

    def mark_as_sent_in_csv(self, company, person):
        """Mark a report as sent in the CSV file"""
        try:
            # Update in-memory dataframe
            if self.df is not None and "reportsent" in self.df.columns:
                mask = (self.df["company_name"].str.strip() == company.strip()) & (
                    self.df["name"].str.strip() == person.strip()
                )
                self.df.loc[mask, "reportsent"] = True

                # Save back to CSV file
                self.df.to_csv(DATA_FILE, index=False, encoding="utf-8")

                # Reload the CSV to ensure we have the latest data
                self.df = pd.read_csv(DATA_FILE, encoding="utf-8")
                self.df.columns = self.df.columns.str.lower().str.strip()

                self.log_email(
                    f"  [UPDATE] Updated CSV: {company} - {person} marked as sent"
                )
        except Exception as e:
            self.log_email(f"  [WARNING] Could not update CSV: {e}")

    def mark_selected_as_sent(self):
        """Mark selected email as sent"""
        selection = self.email_status_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an email record first")
            return

        for item in selection:
            values = self.email_status_tree.item(item)["values"]
            company, person = values[0], values[1]

            # Update in CSV
            self.mark_as_sent_in_csv(company, person)

        self.update_email_status_display()
        self.log_email(f"[OK] Marked {len(selection)} record(s) as sent")

    def mark_selected_as_pending(self):
        """Reset selected email to pending"""
        selection = self.email_status_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an email record first")
            return

        for item in selection:
            values = self.email_status_tree.item(item)["values"]
            company, person = values[0], values[1]

            # Reset in CSV by setting reportsent to False
            try:
                if self.df is not None and "reportsent" in self.df.columns:
                    mask = (self.df["company_name"].str.strip() == company.strip()) & (
                        self.df["name"].str.strip() == person.strip()
                    )
                    self.df.loc[mask, "reportsent"] = False

                    # Save back to CSV file
                    self.df.to_csv(DATA_FILE, index=False, encoding="utf-8")
            except Exception as e:
                self.log_email(f"[WARNING] Could not update CSV: {e}")

        self.update_email_status_display()
        self.log_email(f"[RESET] Reset {len(selection)} record(s) to pending")
