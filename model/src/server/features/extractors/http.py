# src/server/features/extractors/http.py

import os
from collections import defaultdict
from urllib.parse import urlparse
import json
import pandas as pd
from scipy.stats import entropy

JOB_SEARCH_DOMAINS = {
    "monster.com",
    "indeed.com",
    "careerbuilder.com",
    "dice.com"
}

FILE_SHARING_DOMAINS = {
    "dropbox.com",
    "box.com",
    "mediafire.com",
    "rapidshare.com"
}

SUSPICIOUS_DOMAINS = {
    "wikileaks.org",
    "dropbox.com",
    "mediafire.com",
    "rapidshare.com"
}


def extract_domain(url):
    try:
        domain = (
            urlparse(
                str(url)
            )
            .netloc
            .lower()
        )

        if domain.startswith(
            "www."
        ):
            domain = domain[4:]

        return domain

    except Exception:
        return ""


def extract_domain_fast(url):
    try:
        url_str = str(url)
        if "://" in url_str:
            host = url_str.split("://", 1)[1].split("/", 1)[0].split("?", 1)[0].split(":", 1)[0]
        else:
            host = url_str.split("/", 1)[0].split("?", 1)[0].split(":", 1)[0]
        host = host.lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def extract_http_features(
    cert_root
):
    print(
        "Extracting HTTP features (Optimized)..."
    )

    http_path = os.path.join(
        cert_root,
        "http.csv"
    )

    user_day_data = {}
    # Increased chunk size for better pandas vectorization efficiency
    CHUNK_SIZE = 100000
    chunk_id = 0

    # Detect column names from header
    header_df = pd.read_csv(http_path, nrows=0)
    col_names = header_df.columns.tolist()

    # Map raw log columns to expected names
    rename_map = {}
    if "timestamp" in col_names and "date" not in col_names:
        rename_map["timestamp"] = "date"
    if "user_id" in col_names and "user" not in col_names:
        rename_map["user_id"] = "user"

    # Determine which columns to read
    date_col = "timestamp" if "timestamp" in col_names else "date"
    user_col = "user_id" if "user_id" in col_names else "user"
    use_cols = [date_col, user_col, "url"]

    for chunk in pd.read_csv(
        http_path,
        usecols=use_cols,
        chunksize=CHUNK_SIZE
    ):
        if rename_map:
            chunk = chunk.rename(columns=rename_map)

        chunk_id += 1
        if chunk_id % 10 == 0 or chunk_id <= 5:
            print(
                f"HTTP chunk {chunk_id}"
            )

        chunk["date"] = pd.to_datetime(
            chunk["date"]
        )

        chunk["day"] = (
            chunk["date"]
            .dt.date
        )

        chunk["hour"] = (
            chunk["date"]
            .dt.hour
        )

        users = chunk["user"].values
        days = chunk["day"].values
        urls = chunk["url"].values
        hours = chunk["hour"].values

        after_hours = ((hours < 7) | (hours >= 18)).astype(int)
        domains = [extract_domain_fast(url) for url in urls]

        for user, day, url, domain, ah in zip(users, days, urls, domains, after_hours):
            key = (
                user,
                day
            )

            if key not in user_day_data:
                user_day_data[key] = {
                    "http_count": 0,
                    "urls": set(),
                    "domains": [],
                    "after_hours": 0,
                    "job_search": 0,
                    "file_sharing": 0,
                    "suspicious": 0
                }

            d = user_day_data[key]
            d["http_count"] += 1
            d["urls"].add(
                url
            )
            d["domains"].append(
                domain
            )

            if ah:
                d["after_hours"] += 1

            if domain in JOB_SEARCH_DOMAINS:
                d["job_search"] += 1

            if domain in FILE_SHARING_DOMAINS:
                d["file_sharing"] += 1

            if domain in SUSPICIOUS_DOMAINS:
                d["suspicious"] += 1

    print(
        "Building HTTP feature table..."
    )

    rows = []
    seen_domains = defaultdict(set)
    total_groups = len(
        user_day_data
    )

    for idx, (
        (user, day),
        d
    ) in enumerate(
        user_day_data.items()
    ):
        if idx % 10000 == 0:
            print(
                f"HTTP groups processed: "
                f"{idx}/{total_groups}"
            )

        unique_domains = set(
            d["domains"]
        )

        domain_counts = pd.Series(
            d["domains"]
        ).value_counts()

        entropy_value = 0.0

        if len(domain_counts) > 0:
            entropy_value = entropy(
                domain_counts.values
            )

        new_domains = (
            unique_domains
            -
            seen_domains[user]
        )

        seen_domains[user].update(
            unique_domains
        )

        external_domains = [
            x
            for x in unique_domains
            if x != ""
        ]

        external_ratio = (
            len(external_domains)
            /
            max(
                len(unique_domains),
                1
            )
        )

        rows.append({
            "user":
                user,
            "date":
                day,
            "http_count":
                d["http_count"],
            "daily_http_request_count":
                d["http_count"],
            "unique_url_count":
                len(
                    d["urls"]
                ),
            "suspicious_url_count":
                d["suspicious"],
            "file_sharing_site_visits":
                d["file_sharing"],
            "job_search_site_visits":
                d["job_search"],
            "http_after_hours":
                d["after_hours"],
            "daily_unique_domain_count":
                len(
                    unique_domains
                ),
            "daily_new_domain_count":
                len(
                    new_domains
                ),
            "daily_domain_access_entropy":
                entropy_value,
            "daily_external_domain_ratio":
                external_ratio
        })

    result = pd.DataFrame(
        rows
    )

    result = result.fillna(0)

    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.abspath(os.path.join(current_dir, "..", "..", "..", "..", "models", "feature_columns_IF.json"))
        with open(json_path, "r") as f:
            allowed_features = set(json.load(f))
        keep_cols = ["user", "date"] + [col for col in result.columns if col in allowed_features]
        seen = set()
        keep_cols = [x for x in keep_cols if not (x in seen or seen.add(x))]
        result = result[keep_cols]
    except Exception as e:
        print(f"Warning: Could not filter HTTP features using feature_columns_IF.json: {e}")

    print(
        "HTTP feature extraction complete"
    )

    return result