import json
import hashlib
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

JSON_URL = "https://downloads.gtnewhorizons.com/versions.json"
OUTPUT_FILE = Path("versions.json")

def sha256_from_url(url, position):
    h = hashlib.sha256()

    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        filename = url.split("/")[-1]

        with tqdm(
            total=total,
            unit="B",
            unit_scale=True,
            desc=filename,
            position=position,
            leave=True
        ) as pbar:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    h.update(chunk)
                    pbar.update(len(chunk))

    return h.hexdigest()

def load_existing():
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, "r") as f:
            return json.load(f)
    return {}

def main():
    data = requests.get(JSON_URL).json()
    output = load_existing()

    existing_versions = set(output.keys())

    for version, info in data.items():
        if info.get("title") != "Stable release":
            continue

        if version in existing_versions:
            print(f"skipping {version} (already processed)")
            continue

        print(f"\nnew version {version}")

        server = info.get("server", {})
        java8_url = server.get("java8Url", "")
        java17_url = server.get("java17_2XUrl", "")

        urls = [("java8", java8_url), ("java17_2X", java17_url)]
        checksums = {}

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {
                executor.submit(sha256_from_url, url, i): name
                for i, (name, url) in enumerate(urls) if url
            }

            for future in as_completed(futures):
                name = futures[future]
                checksums[name] = future.result()

        output[version] = {
            "javaVersion": info.get("maxJavaVersion"),
            "releaseDate": info.get("releaseDate"),
            "java8Url": java8_url,
            "java17_2XUrl": java17_url,
            "java8_checksum": checksums.get("java8", ""),
            "java17_2X_checksum": checksums.get("java17_2X", "")
        }

        with open(OUTPUT_FILE, "w") as f:
            json.dump(output, f, indent=4)

    print("\ndone")

if __name__ == "__main__":
    main()
