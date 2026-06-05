import streamlit as st
import requests
import xml.etree.ElementTree as ET

# --- CONFIGURATION ---
# Safely fetches the key from Streamlit's secure dashboard settings
try:
    HF_API_KEY = st.secrets["HF_API_KEY"]
except Exception:
    st.error("⚠️ Hugging Face API key not found. Please add it in Streamlit secrets.")
    HF_API_KEY = None

HF_API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-cnn"

# --- HELPER FUNCTIONS ---
@st.cache_data
def search_pubmed(query, max_results=3):
    """Searches PubMed for free full-text articles matching the query."""
    search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    search_params = {
        "db": "pubmed",
        "term": f"{query} AND free full text[sb]",
        "retmode": "json",
        "retmax": max_results
    }
    try:
        response = requests.get(search_url, params=search_params, timeout=10)
        response.raise_for_status()
        return response.json().get("esearchresult", {}).get("idlist", [])
    except Exception as e:
        st.error(f"⚠️ PubMed search failed: {e}")
        return []

@st.cache_data
def fetch_abstracts(id_list):
    """Fetches the title and abstract for a list of PubMed IDs via XML."""
    if not id_list:
        return []
        
    fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    fetch_params = {
        "db": "pubmed",
        "id": ",".join(id_list),
        "retmode": "xml"
    }
    
    try:
        response = requests.get(fetch_url, params=fetch_params, timeout=10)
        response.raise_for_status()
        papers = []
        root = ET.fromstring(response.content)
        for article in root.findall('.//PubmedArticle'):
            title = article.findtext('.//ArticleTitle')
            abstract_texts = article.findall('.//AbstractText')
            abstract = " ".join([elem.text for elem in abstract_texts if elem.text])
            if title and abstract:
                papers.append({"title": title, "abstract": abstract})
        return papers
    except ET.ParseError:
        st.error("⚠️ Could not parse PubMed response.")
        return []
    except Exception as e:
        st.error(f"⚠️ Error fetching abstracts: {e}")
        return []

def summarize_text(text):
    """Sends text to Hugging Face's BART model for summarization."""
    if not HF_API_KEY:
        return "⚠️ Missing API key. Cannot summarize."
    
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    payload = {
        "inputs": text[:2000],  # limit text size to avoid crashes
        "parameters": {"max_length": 150, "min_length": 40, "do_sample": False}
    }
    
    try:
        response = requests.post(HF_API_URL, headers=headers, json=payload, timeout=20)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list) and "summary_text" in data[0]:
                return data[0]["summary_text"]
            else:
                return "⚠️ Unexpected response format."
        elif response.status_code == 503:
            return "⏳ The AI model is warming up. Please wait 20 seconds and click search again."
        else:
            return f"⚠️ Error {response.status_code}: Could not summarize."
    except Exception as e:
        return f"⚠️ Summarization failed: {e}"

# --- STREAMLIT UI ---
st.set_page_config(page_title="Baby Product Scientific Lookup", page_icon="👶")

st.title("👶 Baby Product Research")
st.write("Enter a baby product, ingredient, or brand (e.g., *talcum powder*, *melatonin*, *baby walker*). "
         "This app will search PubMed for open-access medical literature and summarize the findings.")

st.markdown("---")

product_name = st.text_input("**Enter a baby product or topic:**", placeholder="e.g., pacifiers")

if st.button("Search & Summarize", type="primary"):
    if not product_name.strip():
        st.warning("Please enter a product name to search.")
    else:
        with st.spinner(f"Searching PubMed for '{product_name}'..."):
            paper_ids = search_pubmed(product_name, max_results=3)
            
        if not paper_ids:
            st.error(f"No free open-access papers found for '{product_name}'. Try broadening your search terms.")
        else:
            with st.spinner("Fetching and summarizing abstracts..."):
                papers = fetch_abstracts(paper_ids)
                
                if not papers:
                    st.warning("Found papers, but they didn't have usable abstracts.")
                else:
                    progress = st.progress(0)
                    for i, paper in enumerate(papers):
                        st.subheader(f"Paper {i+1}: {paper['title']}")
                        summary = summarize_text(paper['abstract'])
                        st.info(f"**AI Summary:** {summary}")
                        with st.expander("Read Original Abstract"):
                            st.write(paper['abstract'])
                        st.markdown("---")
                        progress.progress((i+1)/len(papers))
