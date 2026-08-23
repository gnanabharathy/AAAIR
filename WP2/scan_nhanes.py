import urllib.request, re

BASE = "https://wwwn.cdc.gov"

CATEGORY_URLS = [
    "https://wwwn.cdc.gov/nchs/nhanes/search/datapage.aspx?Component=Demographics",
    "https://wwwn.cdc.gov/nchs/nhanes/search/datapage.aspx?Component=Dietary",
    "https://wwwn.cdc.gov/nchs/nhanes/search/datapage.aspx?Component=Examination",
    "https://wwwn.cdc.gov/nchs/nhanes/search/datapage.aspx?Component=Laboratory",
    "https://wwwn.cdc.gov/nchs/nhanes/search/datapage.aspx?Component=Questionnaire",
]

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode("utf-8", errors="ignore")

all_links = []
for cat_url in CATEGORY_URLS:
    component = cat_url.split("Component=")[1]
    print(f"Scanning {component}...")
    html = fetch(cat_url)
    links = re.findall(
        r'href=["\'](/Nchs/Data/Nhanes/Public/\d+/DataFiles/[^"\']+\.htm)["\']',
        html, re.I
    )
    for link in links:
        full_url = BASE + link
        filename = link.split("/")[-1].replace(".htm", "").lower()
        year = re.search(r'/(\d{4})/', link)
        year = year.group(1) if year else "unknown"
        ds_id = f"nhanes-{component.lower()}-{filename}-{year}"
        all_links.append((ds_id, full_url, component))
    print(f"  Found {len(links)} datasets")

print(f"\nTotal: {len(all_links)} datasets")
print("\nFirst 10:")
for ds_id, url, comp in all_links[:10]:
    print(f"  {ds_id}: {url}")

with open("datasets_nhanes_full.csv", "w") as f:
    f.write("id,url\n")
    for ds_id, url, comp in all_links:
        f.write(f"{ds_id},{url}\n")
print(f"\nSaved to datasets_nhanes_full.csv")
