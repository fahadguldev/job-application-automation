import os
import re
import json
import urllib.parse
from pathlib import Path
from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()

EMAIL_REGEX = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
IGNORED_DOMAINS = {"example.com", "domain.com", "schema.org", "sentry.io", "w3.org", "github.com", "linkedin.com"}


class LinkedInJobFetcher:
    """
    Fetches recent jobs (posted in the last 24 hours) from specified company pages
    and target job titles, extracting recruiter emails into the Outreach Directory.
    """

    def __init__(self, tavily_api_key: str = None, config_path: str = "config.json", emails_path: str = None):
        self.api_key = tavily_api_key or os.getenv("TAVILY_API_KEY")
        if not self.api_key or self.api_key.startswith("tvly-YOUR_"):
            raise ValueError("TAVILY_API_KEY is not set or invalid in .env file.")
        self.client = TavilyClient(api_key=self.api_key)
        self.config_path = config_path
        if emails_path:
            self.emails_path = Path(emails_path)
        else:
            self.emails_path = Path("data/emails.txt") if os.path.exists("data/emails.txt") else Path("emails.txt")

    def load_config(self) -> dict:
        """Load target URLs, job titles, and locations from config.json."""
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {
            "job_titles": ["Full Stack Developer", "MERN Stack Developer", "Django Developer"],
            "target_urls": [],
            "locations": ["Pakistan", "Remote"]
        }

    def _extract_site_scope(self, url: str) -> str:
        """Convert a LinkedIn URL to a clean Tavily site: search query."""
        parsed = urllib.parse.urlparse(url)
        path = parsed.path.strip("/")
        return f"site:linkedin.com/{path}"

    def extract_emails_from_text(self, text: str) -> list:
        """Extracts valid email addresses from job posting content."""
        if not text:
            return []
        matches = re.findall(EMAIL_REGEX, text)
        valid_emails = []
        for em in matches:
            em_clean = em.lower().strip(".")
            domain = em_clean.split("@")[-1]
            if domain not in IGNORED_DOMAINS and not em_clean.endswith(".png") and not em_clean.endswith(".jpg"):
                if em_clean not in valid_emails:
                    valid_emails.append(em_clean)
        return valid_emails

    def append_to_emails_txt(self, email: str, company: str, person: str = "Hiring Manager"):
        """Appends a newly discovered email to emails.txt if not already present."""
        if not self.emails_path.exists():
            existing_text = ""
        else:
            existing_text = self.emails_path.read_text(encoding="utf-8")

        if email.lower() in existing_text.lower():
            return False  # Already exists

        new_entry = f"{email} | {company} | {person}\n"
        with open(self.emails_path, "a", encoding="utf-8") as f:
            f.write(new_entry)

        print(f"   📧 [NEW OUTREACH EMAIL DISCOVERED] Added to {self.emails_path.name}: '{email}' ({company})")
        return True

    def fetch_jobs_from_config(self, max_results_per_query: int = 5, time_range: str = "day") -> list:
        config = self.load_config()
        job_titles = config.get("job_titles", [])
        keywords = config.get("keywords_and_skills", [])
        target_urls = config.get("target_urls", [])
        locations = config.get("locations", [""])
        location_query = " OR ".join(f'"{loc}"' for loc in locations if loc)

        queries = []

        # 1. Scoped search for recent jobs (24h) from specific LinkedIn Page / Company / Profile URLs
        for page_url in target_urls:
            if not page_url.strip():
                continue
            site_scope = self._extract_site_scope(page_url)
            queries.append({
                "source": f"Page: {page_url}",
                "company_guess": page_url.split("/")[-1].replace("-", " ").capitalize(),
                "query": f'{site_scope} ("hiring" OR "apply" OR "send resume" OR "email" OR "opportunity" OR "developer" OR "engineer")'
            })

        # 2. Targeted search for specific Job Titles in LinkedIn Jobs section (24h)
        for title in job_titles:
            if not title.strip():
                continue
            loc_str = f" ({location_query})" if location_query else ""
            queries.append({
                "source": f"LinkedIn Jobs: {title}",
                "company_guess": "Target Listing",
                "query": f'site:linkedin.com/jobs "{title}"{loc_str}'
            })

        # 3. Search via Keywords, Tech Stack, and Skills provided in config
        if keywords:
            kw_str = " OR ".join(f'"{kw}"' for kw in keywords if kw.strip())
            loc_str = f" ({location_query})" if location_query else ""
            queries.append({
                "source": f"Skills & Keywords: {', '.join(keywords[:4])}",
                "company_guess": "Tech Target",
                "query": f'site:linkedin.com/jobs ({kw_str}){loc_str}'
            })

        print("==========================================================")
        print(f" 🌐 FETCHING RECENT JOBS (LAST 24 HOURS)")
        print(f" 📋 Target URLs: {len(target_urls)} | Target Titles: {len(job_titles)} | Keywords: {len(keywords)}")
        print("==========================================================")

        raw_results = []
        for q_item in queries:
            q_text = q_item["query"]
            try:
                # Use time_range="day" for 24 hours search filter in Tavily
                response = self.client.search(
                    query=q_text,
                    search_depth="advanced",
                    max_results=max_results_per_query,
                    time_range=time_range,
                    include_answer=False
                )
                for item in response.get("results", []):
                    item["_source_tag"] = q_item["source"]
                    item["_company_guess"] = q_item["company_guess"]
                    raw_results.append(item)
            except Exception as e:
                # If time_range is not supported on certain query types, fallback to default search
                try:
                    response = self.client.search(
                        query=q_text,
                        search_depth="advanced",
                        max_results=max_results_per_query,
                        include_answer=False
                    )
                    for item in response.get("results", []):
                        item["_source_tag"] = q_item["source"]
                        item["_company_guess"] = q_item["company_guess"]
                        raw_results.append(item)
                except Exception as ex:
                    print(f"⚠️ Query failed [{q_text[:50]}...]: {ex}")

        # Deduplicate results by URL and parse contact emails
        seen_urls = set()
        formatted_jobs = []
        new_emails_added = 0

        for idx, item in enumerate(raw_results, start=1):
            url = item.get("url", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            raw_title = item.get("title", "Software Developer Position")
            clean_title = raw_title.replace(" | LinkedIn", "").replace(" - LinkedIn", "").strip()
            snippet = item.get("content", "No job description snippet available.")
            source_tag = item.get("_source_tag", "LinkedIn")
            company_guess = item.get("_company_guess", "Target Company")

            # Extract any email mentioned in the job title or snippet content
            found_emails = self.extract_emails_from_text(f"{clean_title} {snippet}")
            primary_email = found_emails[0] if found_emails else None

            if primary_email:
                added = self.append_to_emails_txt(primary_email, company_guess)
                if added:
                    new_emails_added += 1

            # Determine job type: "email" if contact email is present, else "link"
            job_type = "email" if primary_email else "link"

            formatted_jobs.append({
                "id": f"LIVE-24H-{idx:03d}",
                "title": clean_title,
                "source": source_tag,
                "company": company_guess,
                "url": url,
                "contact_email": primary_email,
                "job_type": job_type,
                "description": snippet
            })

        print(f"\n✅ Scraped {len(formatted_jobs)} recent jobs (last 24h). Discovered {new_emails_added} new outreach email(s).\n")
        return formatted_jobs

    def fetch_and_save(self, output_path: str = "jobs.json") -> int:
        jobs = self.fetch_jobs_from_config()
        if not jobs:
            print("⚠️ No recent 24-hour jobs found matching specified URLs/Titles.")
            return 0

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(jobs, f, indent=2)

        print(f"✅ Saved {len(jobs)} recent jobs to {output_path}.\n")
        return len(jobs)


if __name__ == "__main__":
    fetcher = LinkedInJobFetcher()
    fetcher.fetch_and_save()
