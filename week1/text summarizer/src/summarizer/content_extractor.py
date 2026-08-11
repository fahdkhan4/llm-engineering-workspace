import requests
from bs4 import BeautifulSoup


def extract_text(url: str) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/138.0.0.0 Safari/537.36"
        )
    }

    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Remove unwanted tags
    for tag in soup([
        "script",
        "style",
        "noscript",
        "svg",
        "img",
        "iframe",
        "header",
        "footer",
        "nav",
        "aside",
        "form"
    ]):
        tag.decompose()

    # Extract text
    text = soup.get_text(separator="\n")

    lines = [line.strip() for line in text.splitlines()]
    text = "\n".join(line for line in lines if line)

    return text


if __name__ == "__main__":
    url = input("Enter URL: ")
    raw_text = extract_text(url)

    print("=" * 80)
    print(raw_text)