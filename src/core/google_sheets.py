import os
import json
import datetime
import gspread
from google.oauth2.service_account import Credentials

SPREADSHEET_ID = "1XRoW39Y44FlpK0uFJr2lpeU3O2vXzgxoDR7o9omKyb0"

HEADERS = [
    "Job Title",
    "Company Name",
    "Match Score (%)",
    "Interview Prep Topics",
    "Acceptance Chance (%)",
    "Application Status",
    "Application Date"
]

class GoogleSheetManager:
    """Manages appending and updating job application rows in Google Sheets."""

    def __init__(self, spreadsheet_id: str = SPREADSHEET_ID):
        self.spreadsheet_id = spreadsheet_id
        self.client = None
        self._init_client()

    def _init_client(self):
        """Initializes the gspread client using available service account or OAuth credentials."""
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]

        # Method 1: Environment variable containing raw JSON string
        env_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON") or os.getenv("GOOGLE_CREDENTIALS_JSON")
        if env_json:
            try:
                info = json.loads(env_json)
                if info.get("type") == "service_account":
                    creds = Credentials.from_service_account_info(info, scopes=scopes)
                    self.client = gspread.authorize(creds)
                    print("✅ Authenticated via GOOGLE_SERVICE_ACCOUNT_JSON env var.")
                    return
            except Exception as e:
                print(f"⚠️ Failed to authenticate via GOOGLE_SERVICE_ACCOUNT_JSON: {e}")

        # Method 2: Check workspace files for Service Account or OAuth Client Credentials
        import glob
        possible_files = [
            os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
            os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE"),
            "service_account.json",
            "credentials.json",
            os.path.expanduser("~/.config/gspread/service_account.json")
        ]
        possible_files.extend(glob.glob("client_secret_*.json"))

        for filepath in possible_files:
            if filepath and os.path.exists(filepath):
                try:
                    with open(filepath, "r", encoding="utf-8") as fp:
                        data = json.load(fp)

                    if isinstance(data, dict) and data.get("type") == "service_account":
                        creds = Credentials.from_service_account_file(filepath, scopes=scopes)
                        self.client = gspread.authorize(creds)
                        print(f"✅ Authenticated using Service Account key: '{filepath}'")
                        return
                    elif isinstance(data, dict) and ("installed" in data or "web" in data):
                        if not os.path.exists("authorized_user.json"):
                            print(f"🔑 Found OAuth Credentials '{filepath}'. Launching 1-time browser authorization...")
                            print("👉 Please CLICK or COPY the link below into your browser to authorize access to Google Sheets:\n")
                        self.client = gspread.oauth(
                            credentials_filename=filepath,
                            authorized_user_filename="authorized_user.json"
                        )
                        print(f"✅ Authenticated using OAuth Client Secret: '{filepath}'")
                        return
                except KeyboardInterrupt:
                    print("\n⚠️ Google Sheets authorization was skipped by user. Continuing with job evaluation & document generation...")
                    self.client = None
                    return
                except Exception as e:
                    print(f"⚠️ Failed to authenticate via '{filepath}': {e}")

        # Method 3: Default gspread service_account() fallback
        try:
            self.client = gspread.service_account()
            print("✅ Authenticated using default gspread service account.")
        except Exception as e:
            self.client = None


    def sync_job(
        self,
        job_title: str,
        company_name: str,
        match_score: float,
        interview_prep_topics: str,
        acceptance_chance: float,
        status: str = "Applied",
        app_date: str = None
    ) -> str:
        """
        Appends a new row or updates an existing row if Company Name & Job Title match.
        Returns 'updated' or 'created'.
        """
        if not self.client:
            raise RuntimeError("Google Sheets client is not authenticated. Please set GOOGLE_APPLICATION_CREDENTIALS or provide service_account.json.")

        if not app_date:
            app_date = datetime.date.today().strftime("%Y-%m-%d")

        sheet = self.client.open_by_key(self.spreadsheet_id)
        worksheet = sheet.sheet1

        all_values = worksheet.get_all_values()

        if not all_values:
            worksheet.append_row(HEADERS)
            all_values = [HEADERS]
        else:
            header_row = [h.strip() for h in all_values[0]]
            if "Job Title" not in header_row or "Company Name" not in header_row:
                worksheet.insert_row(HEADERS, index=1)
                all_values = [HEADERS] + all_values

        header_row = [h.strip() for h in all_values[0]]

        def get_col_idx(name: str, default: int) -> int:
            try:
                return header_row.index(name)
            except ValueError:
                return default

        col_title_idx = get_col_idx("Job Title", 0)
        col_company_idx = get_col_idx("Company Name", 1)

        # Format score and chance percentages
        if isinstance(match_score, (int, float)):
            val = float(match_score)
            match_score_str = f"{val:.0f}%" if val > 10 else f"{val * 10:.0f}%"
        else:
            match_score_str = str(match_score)

        if isinstance(acceptance_chance, (int, float)):
            val = float(acceptance_chance)
            acceptance_chance_str = f"{val:.0f}%" if val > 1 else f"{val * 100:.0f}%"
        else:
            acceptance_chance_str = str(acceptance_chance)

        target_title = str(job_title).strip().lower()
        target_company = str(company_name).strip().lower()

        found_row_idx = None
        for idx, row in enumerate(all_values[1:], start=2):  # row 1 is header
            row_title = row[col_title_idx].strip().lower() if len(row) > col_title_idx else ""
            row_company = row[col_company_idx].strip().lower() if len(row) > col_company_idx else ""
            if row_title == target_title and row_company == target_company:
                found_row_idx = idx
                break

        row_data = [
            str(job_title),
            str(company_name),
            match_score_str,
            str(interview_prep_topics),
            acceptance_chance_str,
            str(status),
            str(app_date)
        ]

        if found_row_idx:
            range_name = f"A{found_row_idx}:G{found_row_idx}"
            worksheet.update(range_name=range_name, values=[row_data])
            return "updated"
        else:
            worksheet.append_row(row_data)
            return "created"
